"""Meta OAuth endpoints.

Flow (when running against a real, publicly-reachable callback URL):

  1. Admin clicks "Conectar canal" in /canales → frontend GETs
     /auth/meta/connect (with their session JWT).
  2. Backend builds the Meta OAuth dialog URL with our app_id + scopes +
     a signed `state` that binds this attempt to the calling tenant +
     user. Returns {url}.
  3. Frontend `window.location` to that URL. User consents on Meta.
  4. Meta redirects to /auth/meta/callback?code=...&state=...
     (this endpoint is PUBLIC — Meta hits it without our JWT).
  5. Backend validates state, exchanges code → short user token → long
     user token, lists the user's Pages with their per-page access
     tokens, subscribes the relevant webhook fields, and persists each
     connected page + token into `tenants.settings.meta.connected_pages`.
  6. Backend 302-redirects the browser back to {web_origin}/canales
     with ?meta_connected=1 (or ?meta_error=... on failure).

Until the deploy lands with HTTPS + a real domain registered as a Valid
OAuth Redirect URI in the Meta App dashboard, step 4 won't actually
reach this endpoint. The flow is wired and unit-testable; only the
"real round-trip" depends on infrastructure.
"""
import json
import logging
import secrets
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from setiq import db
from setiq.auth.dependencies import CurrentUser, require_admin
from setiq.config import settings
from setiq.integrations.meta import (
    MetaApiError,
    MetaClient,
    SignedRequestError,
    parse_signed_request,
)
from setiq.integrations.secrets import encrypt_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/meta", tags=["meta-oauth"])


# Scopes the OAuth dialog requests. These are the same permissions our
# Use Cases asked for (Instagram messaging + Pages management + Messenger),
# expressed as the underlying scope strings Meta wants here.
OAUTH_SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "pages_messaging",
    "pages_messaging_subscriptions",
    "pages_manage_engagement",
    "pages_manage_metadata",
    "instagram_basic",
    "instagram_manage_comments",
    "instagram_manage_messages",
    "business_management",
]

# Webhook fields to subscribe per Page once OAuth completes.
PAGE_WEBHOOK_FIELDS = ["feed", "messages", "message_deliveries", "message_reads"]

STATE_TTL_SECONDS = 600  # 10 minutes — long enough for the consent dialog


class ConnectResponse(BaseModel):
    url: str


def _sign_state(user_id: str, tenant_id: str) -> str:
    """Bind this connect attempt to (user, tenant) so the callback can
    verify the OAuth round-trip wasn't tampered with or replayed."""
    payload = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "nonce": secrets.token_urlsafe(8),
        "purpose": "meta_oauth",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _verify_state(state: str) -> dict[str, Any]:
    try:
        decoded = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.InvalidTokenError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid state: {e}") from e
    if decoded.get("purpose") != "meta_oauth":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid state purpose")
    return decoded


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/connect", response_model=ConnectResponse)
async def connect(
    current_user: CurrentUser = Depends(require_admin),
) -> ConnectResponse:
    """Build the Meta OAuth dialog URL for the current tenant. Frontend
    redirects the browser to the returned `url`."""
    if not settings.meta_app_id:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Meta integration is not configured (missing META_APP_ID).",
        )

    state = _sign_state(str(current_user.user_id), str(current_user.tenant_id))
    qs = urlencode({
        "client_id": settings.meta_app_id,
        "redirect_uri": settings.meta_oauth_redirect_uri,
        "scope": ",".join(OAUTH_SCOPES),
        "state": state,
        "response_type": "code",
    })
    return ConnectResponse(url=f"https://www.facebook.com/v22.0/dialog/oauth?{qs}")


@router.get("/callback")
async def callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> Response:
    """PUBLIC — Meta redirects browsers here after the OAuth dialog. We
    finish the exchange, persist the page tokens, subscribe webhooks, and
    bounce the user back to the frontend with a status flag."""
    front = settings.web_origin.rstrip("/")

    if error:
        msg = error_description or error
        return RedirectResponse(f"{front}/canales?meta_error={msg}", status_code=302)
    if not code or not state:
        return RedirectResponse(f"{front}/canales?meta_error=missing_code_or_state", status_code=302)

    try:
        verified = _verify_state(state)
    except HTTPException as e:
        return RedirectResponse(f"{front}/canales?meta_error={e.detail}", status_code=302)

    tenant_id = verified["tenant_id"]
    client = MetaClient(settings.meta_app_id, settings.meta_app_secret)

    try:
        # Step 1: code → short-lived user token
        short = await client.exchange_code_for_user_token(
            code=code, redirect_uri=settings.meta_oauth_redirect_uri
        )
        # Step 2: → long-lived user token (~60d)
        long = await client.exchange_short_for_long_user_token(short["access_token"])
        # Step 3: identify the connecting FB user (so a future deauth callback
        # knows which pages to clean up).
        fb_user_id = await client.get_me_id(long["access_token"])
        # Step 4: list pages the user manages — each row has a non-expiring page token
        pages = await client.list_user_pages(long["access_token"])
    except MetaApiError as e:
        logger.warning("Meta OAuth exchange failed: %s", e)
        return RedirectResponse(
            f"{front}/canales?meta_error=oauth_exchange_failed",
            status_code=302,
        )

    # Step 4: per page — best-effort subscribe + fetch linked IG + persist
    connected: list[dict[str, Any]] = []
    for p in pages:
        page_id = p.get("id")
        page_token = p.get("access_token")
        if not page_id or not page_token:
            continue
        ig_info: dict[str, Any] | None = None
        try:
            ig_info = await client.get_page_instagram_account(page_id, page_token)
        except MetaApiError as e:
            logger.info("page %s has no IG linked or fetch failed: %s", page_id, e)
        try:
            await client.subscribe_page_webhooks(page_id, page_token, PAGE_WEBHOOK_FIELDS)
        except MetaApiError as e:
            logger.warning("webhook subscribe failed for page %s: %s", page_id, e)
        connected.append({
            "page_id": page_id,
            "page_name": p.get("name"),
            "category": p.get("category"),
            # Stored encrypted via Fernet; decrypt at use site (Graph calls).
            "page_token": encrypt_token(page_token),
            "instagram_business_account": ig_info,
            "connected_by_user_id": fb_user_id,
        })

    # Persist into tenants.settings.meta.connected_pages — JSONB merge.
    # NOTE: page tokens are sensitive. For MVP we accept storing them in
    # tenants.settings; long-term they should move to a dedicated
    # connected_channels table with encryption-at-rest (TODO item).
    patch = {"meta": {"connected_pages": connected}}
    async with db.acquire() as conn:
        # Pool registers a JSONB codec, so dicts are auto-encoded; no manual
        # json.dumps (would double-encode).
        await conn.execute(
            """
            UPDATE tenants SET settings = settings || $1::jsonb, updated_at = NOW()
            WHERE id = $2
            """,
            patch,
            UUID(tenant_id),
        )

    return RedirectResponse(
        f"{front}/canales?meta_connected={len(connected)}",
        status_code=302,
    )


async def _purge_user_pages(fb_user_id: str) -> tuple[list[str], list[UUID]]:
    """Strip all connected_pages authorized by this FB user across every tenant.

    Returns (removed_page_ids, affected_tenant_ids). Used by both the
    deauthorize and data-deletion-callback endpoints — the same removal
    behavior applies.
    """
    removed_pages: list[str] = []
    affected_tenants: list[UUID] = []

    async with db.acquire() as conn:
        # Tenant count is small (< 100 foreseeable). Plain iteration is
        # simpler than a JSONB path query and lets us log granularly.
        rows = await conn.fetch(
            """
            SELECT id, settings
            FROM tenants
            WHERE settings -> 'meta' -> 'connected_pages' IS NOT NULL
            """
        )
        for row in rows:
            raw_settings = row["settings"]
            current_settings = (
                raw_settings if isinstance(raw_settings, dict)
                else json.loads(raw_settings or "{}")
            )
            meta_block = current_settings.get("meta", {}) or {}
            pages = meta_block.get("connected_pages") or []
            kept = [p for p in pages if p.get("connected_by_user_id") != fb_user_id]
            if len(kept) == len(pages):
                continue
            for p in pages:
                if p.get("connected_by_user_id") == fb_user_id:
                    removed_pages.append(p.get("page_id", "?"))
            new_meta = {**meta_block, "connected_pages": kept}
            await conn.execute(
                "UPDATE tenants SET settings = jsonb_set(settings, '{meta}', $1::jsonb), updated_at = NOW() WHERE id = $2",
                new_meta,
                row["id"],
            )
            affected_tenants.append(row["id"])

    return removed_pages, affected_tenants


def _callback_response(kind: str, fb_user_id: str) -> dict[str, str]:
    """Standard {url, confirmation_code} envelope Meta expects on both
    callback URLs. `kind` is a prefix for the confirmation code so we can
    distinguish deauthorize vs deletion in support tickets."""
    code = f"{kind}_{fb_user_id}_{secrets.token_hex(4)}"
    front = settings.web_origin.rstrip("/")
    return {
        "url": f"{front}/assets/legal/data-deletion.html",
        "confirmation_code": code,
    }


def _user_id_from_signed_request(signed_request: str) -> str:
    """Verify Meta's signed_request and extract the FB user_id. Raises
    HTTPException(400) on any failure."""
    try:
        payload = parse_signed_request(signed_request, settings.meta_app_secret)
    except SignedRequestError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    fb_user_id = str(payload.get("user_id", ""))
    if not fb_user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "missing user_id in payload")
    return fb_user_id


@router.post("/deauthorize")
async def deauthorize(
    signed_request: str = Form(...),
) -> dict[str, str]:
    """PUBLIC — Meta POSTs here when a user revokes the SETIQ app from
    their Facebook account (Settings → Apps and websites → SETIQ → Remove).

    Removes any pages the user authorized from
    `tenants.settings.meta.connected_pages` (matched via the
    `connected_by_user_id` recorded during OAuth). Historical messages /
    comments persisted by SETIQ are NOT removed by this endpoint — they
    belong to the tenant who owns the page; the data-deletion-callback
    is what handles deletion of user-authored data.
    """
    fb_user_id = _user_id_from_signed_request(signed_request)
    removed, tenants_touched = await _purge_user_pages(fb_user_id)
    logger.info(
        "deauthorize: fb_user_id=%s removed %d pages across %d tenant(s)",
        fb_user_id, len(removed), len(tenants_touched),
    )
    return _callback_response("deauth", fb_user_id)


@router.post("/data-deletion-callback")
async def data_deletion_callback(
    signed_request: str = Form(...),
) -> dict[str, str]:
    """PUBLIC — Meta POSTs here when a user explicitly requests deletion of
    their data via Facebook's privacy controls.

    Today we mirror the deauthorize behavior: remove page tokens the user
    authorized so SETIQ stops receiving events for those pages. Granular
    deletion of user-authored content (their comments / DMs within other
    tenants' inboxes) happens out-of-band via privacy@setiq.bo and the
    process documented in /assets/legal/data-deletion.html — both for
    practical reasons (PSIDs in webhook payloads aren't trivially
    reversible to a FB user_id) and to give a human a chance to verify
    the request before destructive deletion.
    """
    fb_user_id = _user_id_from_signed_request(signed_request)
    removed, tenants_touched = await _purge_user_pages(fb_user_id)
    logger.info(
        "data_deletion: fb_user_id=%s removed %d pages across %d tenant(s)",
        fb_user_id, len(removed), len(tenants_touched),
    )
    return _callback_response("deletion", fb_user_id)


@router.post("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(
    page_id: str = Query(..., min_length=1),
    current_user: CurrentUser = Depends(require_admin),
) -> Response:
    """Remove a connected page from the tenant's settings. Doesn't tell
    Meta — that happens through the app's removal flow (user revokes the
    app from their FB account settings)."""
    async with db.acquire() as raw:
        row = await raw.fetchrow(
            "SELECT settings FROM tenants WHERE id = $1",
            current_user.tenant_id,
        )
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "tenant not found")
        raw_settings = row["settings"]
        current_settings = (
            raw_settings if isinstance(raw_settings, dict)
            else json.loads(raw_settings or "{}")
        )
        meta_block = current_settings.get("meta", {}) or {}
        new_pages = [p for p in (meta_block.get("connected_pages") or []) if p.get("page_id") != page_id]
        new_meta = {**meta_block, "connected_pages": new_pages}
        await raw.execute(
            "UPDATE tenants SET settings = jsonb_set(settings, '{meta}', $1::jsonb), updated_at = NOW() WHERE id = $2",
            new_meta,
            current_user.tenant_id,
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
