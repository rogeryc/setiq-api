"""Thin async client for Meta's Graph API v22.0.

Covers exactly what SETIQ needs in MVP write features:
  - OAuth token exchange (code → user token → long-lived → page tokens)
  - Page + IG Business account lookups
  - Reply to comments (IG + FB)
  - Send DMs (Messenger + IG)
  - Subscribe a Page to our webhook so events start flowing

No retry logic, no caching, no batch — those are easy to add when needed.
Each method handles Meta's standard error envelope and raises MetaApiError
on non-2xx with code/message/type so callers can branch on real errors.

All methods are async + per-call httpx clients (no shared session). For a
high-throughput worker we'd want connection pooling, but the current call
volume is operator-driven (1 reply at a time) so this is fine.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


BASE_URL = "https://graph.facebook.com/v22.0"
DEFAULT_TIMEOUT = 12.0


@dataclass
class MetaApiError(Exception):
    """Standard Meta error envelope.

    Meta returns:
        {"error": {"message": "...", "type": "...", "code": 100, "fbtrace_id": "..."}}
    """
    code: int | None
    message: str
    type: str | None
    http_status: int

    def __str__(self) -> str:
        return f"Meta API error [{self.http_status} / code={self.code}]: {self.message}"


class MetaClient:
    def __init__(self, app_id: str, app_secret: str, base_url: str = BASE_URL) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------ HTTP

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        q = dict(params or {})
        if token:
            q["access_token"] = token
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.request(method, url, params=q, data=data)
        try:
            body = resp.json()
        except ValueError:
            body = {"_raw": resp.text}
        if resp.status_code >= 400 or "error" in body:
            err = body.get("error") or {}
            raise MetaApiError(
                code=err.get("code"),
                message=err.get("message") or f"HTTP {resp.status_code}",
                type=err.get("type"),
                http_status=resp.status_code,
            )
        return body

    # ------------------------------------------------------------------ OAuth

    async def exchange_code_for_user_token(
        self, code: str, redirect_uri: str
    ) -> dict[str, Any]:
        """Step 1 of OAuth: exchange the `code` from the redirect for a short-
        lived user access token. Response: {access_token, token_type, expires_in}.
        """
        return await self._request(
            "GET",
            "/oauth/access_token",
            params={
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )

    async def exchange_short_for_long_user_token(
        self, short_token: str
    ) -> dict[str, Any]:
        """Step 2 of OAuth: upgrade a short-lived user token (~1h) to a
        long-lived one (~60d). Response: {access_token, token_type, expires_in}.
        """
        return await self._request(
            "GET",
            "/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "fb_exchange_token": short_token,
            },
        )

    # -------------------------------------------------------- User identity

    async def get_me_id(self, user_token: str) -> str:
        """Returns the FB user ID for the holder of this token. Used during
        OAuth to record who connected each page (so a deauth callback knows
        which pages to clean up).
        """
        body = await self._request(
            "GET",
            "/me",
            params={"fields": "id"},
            token=user_token,
        )
        return str(body["id"])

    # -------------------------------------------------------- Page discovery

    async def list_user_pages(self, user_long_token: str) -> list[dict[str, Any]]:
        """GET /me/accounts — returns the Pages the user manages, each with
        its own non-expiring `access_token` (page token). The page tokens are
        what we store per-tenant for all subsequent Page-scoped calls.
        """
        body = await self._request("GET", "/me/accounts", token=user_long_token)
        return body.get("data", [])

    async def get_page(self, page_id: str, page_token: str) -> dict[str, Any]:
        """Basic page info — name, category, etc. Useful to verify a token
        works and to display the connected account in the UI."""
        return await self._request(
            "GET",
            f"/{page_id}",
            params={"fields": "id,name,category,username"},
            token=page_token,
        )

    async def get_page_instagram_account(
        self, page_id: str, page_token: str
    ) -> dict[str, Any] | None:
        """Each FB Page can be linked to one IG Business account. Returns the
        IG Business id (+ username) if linked, else None.
        """
        body = await self._request(
            "GET",
            f"/{page_id}",
            params={"fields": "instagram_business_account{id,username,name}"},
            token=page_token,
        )
        return body.get("instagram_business_account")

    # ------------------------------------------------ Webhook subscription

    async def subscribe_page_webhooks(
        self,
        page_id: str,
        page_token: str,
        fields: list[str],
    ) -> dict[str, Any]:
        """Subscribe our app to the given fields for a Page. Once done, Meta
        starts POSTing events for that page to our webhook URL. `fields` is
        a list like ['messages', 'feed', 'comments']."""
        return await self._request(
            "POST",
            f"/{page_id}/subscribed_apps",
            data={"subscribed_fields": ",".join(fields)},
            token=page_token,
        )

    # --------------------------------------------------- Comment replies

    async def reply_to_fb_comment(
        self, comment_id: str, message: str, page_token: str
    ) -> dict[str, Any]:
        """Reply to a Facebook Page comment. Returns {id} of the new reply."""
        return await self._request(
            "POST",
            f"/{comment_id}/comments",
            data={"message": message},
            token=page_token,
        )

    async def reply_to_ig_comment(
        self, comment_id: str, message: str, ig_token: str
    ) -> dict[str, Any]:
        """Reply to an Instagram comment. Returns {id} of the new reply."""
        return await self._request(
            "POST",
            f"/{comment_id}/replies",
            data={"message": message},
            token=ig_token,
        )

    # ------------------------------------------------------ Direct messages

    async def send_messenger_message(
        self, recipient_id: str, text: str, page_token: str
    ) -> dict[str, Any]:
        """Send a DM via FB Messenger from a Page. recipient_id is the
        PSID (Page-Scoped ID) Meta provides in the webhook event."""
        return await self._request(
            "POST",
            "/me/messages",
            data={
                "recipient": '{"id":"' + recipient_id + '"}',
                "message": '{"text":' + _json_string(text) + "}",
                "messaging_type": "RESPONSE",
            },
            token=page_token,
        )

    async def send_ig_dm(
        self, recipient_id: str, text: str, ig_token: str
    ) -> dict[str, Any]:
        """Send an Instagram DM from a Business account. recipient_id is the
        IGSID Meta provides in the webhook event."""
        return await self._request(
            "POST",
            "/me/messages",
            data={
                "recipient": '{"id":"' + recipient_id + '"}',
                "message": '{"text":' + _json_string(text) + "}",
            },
            token=ig_token,
        )


def _json_string(s: str) -> str:
    """Tiny helper: properly JSON-encode a string (Meta's messaging endpoints
    take stringified JSON for the `message` and `recipient` body params)."""
    import json
    return json.dumps(s, ensure_ascii=False)


# ---------------------------------------------------------------------------
# signed_request — used by Meta's deauthorize + data-deletion callbacks.
# Format: <base64url(hmac_sha256_signature)>.<base64url(payload_json)>
# We verify the signature with our App Secret before trusting the payload.
# Docs: https://developers.facebook.com/docs/facebook-login/guides/advanced/manual-flow/#parsingsr
# ---------------------------------------------------------------------------

class SignedRequestError(ValueError):
    """Raised when the signed_request from Meta is malformed or has a bad signature."""


def parse_signed_request(signed_request: str, app_secret: str) -> dict[str, Any]:
    """Verify and decode Meta's signed_request format.

    Returns the decoded JSON payload (typically contains user_id, algorithm,
    issued_at). Raises SignedRequestError if the format is wrong or the
    signature doesn't match.
    """
    import base64
    import hashlib
    import hmac as _hmac
    import json

    try:
        encoded_sig, payload = signed_request.split(".", 1)
    except ValueError as e:
        raise SignedRequestError("signed_request must be '<sig>.<payload>'") from e

    # base64url with no padding — Meta strips it
    def _pad(s: str) -> bytes:
        return (s + "=" * (-len(s) % 4)).encode()

    try:
        sig = base64.urlsafe_b64decode(_pad(encoded_sig))
        data = json.loads(base64.urlsafe_b64decode(_pad(payload)))
    except (ValueError, json.JSONDecodeError) as e:
        raise SignedRequestError(f"failed to decode: {e}") from e

    if data.get("algorithm", "").upper() != "HMAC-SHA256":
        raise SignedRequestError(f"unexpected algorithm: {data.get('algorithm')}")

    expected = _hmac.new(app_secret.encode(), payload.encode(), hashlib.sha256).digest()
    if not _hmac.compare_digest(sig, expected):
        raise SignedRequestError("signature mismatch")

    return data
