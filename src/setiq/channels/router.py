"""GET /channels — connection status of every platform for the current tenant.

Derives "connected" from `tenants.settings`. Account labels and warnings come
from the same JSONB blob. Status / last_sync_at are hardcoded placeholders
until we add a real `connected_channels` table tracking OAuth tokens and
sync history.
"""
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from setiq.auth.dependencies import CurrentUser, get_tenant_db, require_admin
from setiq.channels.schemas import (
    ChannelModulesPatch,
    ChannelStatus,
    ChannelsResponse,
    ModuleToggles,
)

router = APIRouter(prefix="/channels", tags=["channels"])


# Ordered list of platforms SETIQ can ingest from. Each entry describes how to
# decide "connected" for that platform from the tenant's settings JSONB.
SUPPORTED = [
    ("instagram", "Instagram"),
    ("facebook",  "Facebook"),
    ("tiktok",    "TikTok"),
    ("email",     "Email"),
    ("whatsapp",  "WhatsApp Business"),
    ("phone",     "0800 / Teléfono"),
]


@router.get("", response_model=ChannelsResponse, response_model_exclude_none=True)
async def list_channels(
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> ChannelsResponse:
    return await _build_response(conn)


@router.patch("/{key}", response_model=ChannelsResponse, response_model_exclude_none=True)
async def patch_channel(
    key: str,
    patch: ChannelModulesPatch,
    _admin: CurrentUser = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> ChannelsResponse:
    if key not in {k for k, _ in SUPPORTED}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown channel")

    row = await conn.fetchrow("SELECT settings FROM tenants WHERE id = current_tenant_id()")
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    settings: dict[str, Any] = row["settings"] or {}

    channel_modules = dict(settings.get("channel_modules") or {})
    current = dict(channel_modules.get(key) or {})
    if patch.setiq is not None:
        current["setiq"] = patch.setiq
    if patch.kaizen is not None:
        current["kaizen"] = patch.kaizen
    channel_modules[key] = current

    await conn.execute(
        """
        UPDATE tenants
        SET settings = jsonb_set(settings, '{channel_modules}', $1::jsonb, true),
            updated_at = NOW()
        WHERE id = current_tenant_id()
        """,
        channel_modules,
    )
    return await _build_response(conn)


async def _build_response(conn: asyncpg.Connection) -> ChannelsResponse:
    row = await conn.fetchrow(
        "SELECT settings, modules FROM tenants WHERE id = current_tenant_id()"
    )
    settings: dict[str, Any] = (row["settings"] if row else None) or {}
    modules: dict[str, Any] = (row["modules"] if row else None) or {}

    meta = settings.get("meta", {}) or {}
    labels = settings.get("channel_labels", {}) or {}
    overrides = settings.get("channel_modules", {}) or {}

    kaizen_on = bool((modules.get("kaizen") or {}).get("enabled"))
    setiq_on = bool((modules.get("setiq") or {}).get("tier"))

    now = datetime.now(timezone.utc)

    channels: list[ChannelStatus] = []
    for key, label in SUPPORTED:
        connected, account_label, warning, status = _platform_status(
            key, meta, settings, labels,
        )
        ov = overrides.get(key) or {}
        channels.append(ChannelStatus(
            key=key,
            label=label,
            connected=connected,
            account_label=account_label,
            status=status,
            last_sync_at=(now - timedelta(minutes=_recent_minutes(key)))
                         if connected else None,
            modules=ModuleToggles(
                setiq=setiq_on and connected and ov.get("setiq", True),
                kaizen=kaizen_on and connected and ov.get("kaizen", True),
            ),
            warning=warning,
        ))

    return ChannelsResponse(
        channels=channels,
        connected_count=sum(1 for c in channels if c.connected),
        warning_count=sum(1 for c in channels if c.status == "warning"),
    )


def _platform_status(
    key: str,
    meta: dict[str, Any],
    settings: dict[str, Any],
    labels: dict[str, str],
) -> tuple[bool, str | None, str | None, str]:
    """Returns (connected, account_label, warning, status)."""
    if key == "instagram":
        ids = meta.get("instagram_business_ids") or []
        if not ids:
            return False, None, None, "disconnected"
        return True, labels.get("instagram"), None, "active"

    if key == "facebook":
        ids = meta.get("page_ids") or []
        if not ids:
            return False, None, None, "disconnected"
        return True, labels.get("facebook"), None, "active"

    if key == "tiktok":
        handle = (settings.get("tiktok") or {}).get("handle")
        if not handle:
            return False, None, None, "disconnected"
        return True, handle, None, "active"

    if key == "email":
        addr = (settings.get("email") or {}).get("address")
        if not addr:
            return False, None, None, "disconnected"
        return True, addr, None, "active"

    if key == "whatsapp":
        wa = (settings.get("whatsapp") or {})
        number = wa.get("number")
        if not number:
            return False, None, None, "disconnected"
        return True, number, None, "active"

    if key == "phone":
        number = (settings.get("phone") or {}).get("number")
        if not number:
            return False, None, None, "disconnected"
        return True, number, None, "active"

    return False, None, None, "disconnected"


def _recent_minutes(key: str) -> int:
    # Different "last sync" stagger so the demo doesn't show everything at the
    # same minute. Stable per key.
    return {
        "instagram": 2,
        "facebook":  3,
        "tiktok":    240,
        "email":     1,
        "whatsapp":  15,
        "phone":     60,
    }.get(key, 60)
