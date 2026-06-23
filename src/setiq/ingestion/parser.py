"""Parse webhook_events into contacts / channel_identities / conversations / messages.

Runs as a FastAPI BackgroundTask (or, later, an Arq worker). Uses the admin
pool so RLS is bypassed — webhook_events rows have NULL tenant_id until the
parser resolves it, and the parser writes across tenant boundaries during
dispatch. Tenant_id is still explicitly set on every insert.

Handles:
- Instagram comments (`object='instagram'`, `changes[].field='comments'`)
- Instagram DMs (`object='instagram'`, `entry[].messaging[]`)
- Facebook Page comments (`object='page'`, `changes[].field='feed'`)
- Facebook Messenger DMs (`object='page'`, `entry[].messaging[]`)
"""
import logging
from typing import Any
from uuid import UUID

import asyncpg

from setiq import db, queue

logger = logging.getLogger(__name__)


async def process_event(event_id: UUID) -> None:
    """Process one webhook_events row. Marks it processed or failed."""
    async with db.admin_acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, source, payload, status FROM webhook_events WHERE id = $1",
            event_id,
        )
        if row is None or row["status"] != "pending":
            return

        try:
            if row["source"] != "meta":
                await _mark(conn, event_id, "skipped", error=f"non-meta source: {row['source']}")
                return

            payload = row["payload"]
            obj = payload.get("object")
            if obj == "instagram":
                await _process_instagram(conn, payload)
            elif obj == "page":
                await _process_facebook(conn, payload)
            else:
                await _mark(conn, event_id, "skipped", error=f"unknown object: {obj}")
                return

            await _mark(conn, event_id, "processed")
        except Exception as e:
            logger.exception("webhook event %s failed", event_id)
            await _mark(conn, event_id, "failed", error=str(e))


async def _mark(
    conn: asyncpg.Connection,
    event_id: UUID,
    status: str,
    error: str | None = None,
) -> None:
    await conn.execute(
        "UPDATE webhook_events SET status = $1, processed_at = NOW(), error = $2 WHERE id = $3",
        status, error, event_id,
    )


async def _find_tenant_by_meta_id(conn: asyncpg.Connection, meta_id: str) -> UUID | None:
    """Find the tenant that owns a Meta Page or IG Business account ID."""
    row = await conn.fetchrow(
        """
        SELECT id FROM tenants
        WHERE (settings->'meta'->'page_ids' ? $1)
           OR (settings->'meta'->'instagram_business_ids' ? $1)
        LIMIT 1
        """,
        meta_id,
    )
    return row["id"] if row else None


async def _process_instagram(conn: asyncpg.Connection, payload: dict[str, Any]) -> None:
    for entry in payload.get("entry", []):
        ig_id = entry.get("id")
        if not ig_id:
            continue
        tenant_id = await _find_tenant_by_meta_id(conn, ig_id)
        if tenant_id is None:
            logger.warning("no tenant for IG id %s; skipping entry", ig_id)
            continue
        for change in entry.get("changes", []) or []:
            if change.get("field") == "comments":
                await _store_ig_comment(conn, tenant_id, ig_id, change.get("value") or {})
        for event in entry.get("messaging", []) or []:
            await _store_dm(conn, tenant_id, "instagram", "instagram_dm", ig_id, event)


async def _process_facebook(conn: asyncpg.Connection, payload: dict[str, Any]) -> None:
    for entry in payload.get("entry", []):
        page_id = entry.get("id")
        if not page_id:
            continue
        tenant_id = await _find_tenant_by_meta_id(conn, page_id)
        if tenant_id is None:
            logger.warning("no tenant for FB page %s; skipping entry", page_id)
            continue
        for change in entry.get("changes", []) or []:
            if change.get("field") == "feed":
                await _store_fb_comment(conn, tenant_id, page_id, change.get("value") or {})
        for event in entry.get("messaging", []) or []:
            await _store_dm(conn, tenant_id, "facebook", "facebook_dm", page_id, event)


async def _store_dm(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    identity_channel: str,
    conversation_channel: str,
    self_id: str,
    event: dict[str, Any],
) -> None:
    message = event.get("message")
    if not message or message.get("is_echo"):
        return
    sender = event.get("sender") or {}
    sender_id = sender.get("id")
    if not sender_id or sender_id == self_id:
        return

    text = message.get("text") or ""
    external_id = message.get("mid")

    identity_id, contact_id = await _upsert_identity(
        conn, tenant_id, identity_channel, sender_id, None,
    )
    conv_id = await _upsert_conversation(
        conn, tenant_id, contact_id, identity_id, conversation_channel, None, self_id,
    )
    msg_id = await _insert_message(
        conn, tenant_id, conv_id, text, external_id, event,
    )
    if msg_id is not None:
        await queue.enqueue_classify_message(msg_id)


async def _store_fb_comment(
    conn: asyncpg.Connection, tenant_id: UUID, page_id: str, value: dict[str, Any]
) -> None:
    if value.get("item") != "comment" or value.get("verb") != "add":
        return
    sender = value.get("from") or {}
    sender_id = sender.get("id")
    display_name = sender.get("name")
    if not sender_id or sender_id == page_id:
        return

    post_id = value.get("post_id")
    text = value.get("message") or ""
    external_id = value.get("comment_id")

    identity_id, contact_id = await _upsert_identity(
        conn, tenant_id, "facebook", sender_id, display_name,
    )
    conv_id = await _upsert_conversation(
        conn, tenant_id, contact_id, identity_id, "facebook_comment", post_id, page_id,
    )
    msg_id = await _insert_message(
        conn, tenant_id, conv_id, text, external_id, value,
    )
    if msg_id is not None:
        await queue.enqueue_classify_message(msg_id)


async def _upsert_identity(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    channel: str,
    external_id: str,
    display_name: str | None,
) -> tuple[UUID, UUID]:
    """Return (channel_identity_id, contact_id), creating both if needed."""
    row = await conn.fetchrow(
        """
        SELECT id, contact_id FROM channel_identities
        WHERE tenant_id = $1 AND channel = $2 AND external_id = $3
        """,
        tenant_id, channel, external_id,
    )
    if row is not None:
        await conn.execute(
            "UPDATE contacts SET last_seen_at = NOW() WHERE id = $1",
            row["contact_id"],
        )
        return row["id"], row["contact_id"]

    contact_id = await conn.fetchval(
        """
        INSERT INTO contacts (tenant_id, display_name, first_seen_at, last_seen_at)
        VALUES ($1, $2, NOW(), NOW())
        RETURNING id
        """,
        tenant_id, display_name,
    )
    identity_id = await conn.fetchval(
        """
        INSERT INTO channel_identities (tenant_id, contact_id, channel, external_id, display_name)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        tenant_id, contact_id, channel, external_id, display_name,
    )
    return identity_id, contact_id


async def _upsert_conversation(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    contact_id: UUID,
    identity_id: UUID,
    channel: str,
    external_thread_id: str | None,
    received_by_page_id: str | None,
) -> UUID:
    row = await conn.fetchrow(
        """
        SELECT id FROM conversations
        WHERE tenant_id = $1 AND channel = $2 AND contact_id = $3
          AND external_thread_id IS NOT DISTINCT FROM $4
        """,
        tenant_id, channel, contact_id, external_thread_id,
    )
    if row is not None:
        await conn.execute(
            """
            UPDATE conversations
            SET last_message_at = NOW(),
                received_by_page_id = COALESCE(received_by_page_id, $2)
            WHERE id = $1
            """,
            row["id"], received_by_page_id,
        )
        existing_id: UUID = row["id"]
        return existing_id

    new_id: UUID = await conn.fetchval(
        """
        INSERT INTO conversations (
            tenant_id, contact_id, channel, channel_identity_id,
            external_thread_id, received_by_page_id, last_message_at, status
        ) VALUES ($1, $2, $3, $4, $5, $6, NOW(), 'open')
        RETURNING id
        """,
        tenant_id, contact_id, channel, identity_id, external_thread_id,
        received_by_page_id,
    )
    return new_id


async def _insert_message(
    conn: asyncpg.Connection,
    tenant_id: UUID,
    conversation_id: UUID,
    content_text: str,
    external_id: str | None,
    raw_payload: dict[str, Any],
) -> UUID | None:
    """Insert a message idempotently (unique on external_id). Returns the
    new message id, or None if the message was already ingested."""
    try:
        msg_id: UUID | None = await conn.fetchval(
            """
            INSERT INTO messages (
                tenant_id, conversation_id, direction, sender_type,
                content_type, content_text, external_id, sent_at, raw_payload
            ) VALUES ($1, $2, 'inbound', 'contact', 'text', $3, $4, NOW(), $5)
            RETURNING id
            """,
            tenant_id, conversation_id, content_text, external_id, raw_payload,
        )
        return msg_id
    except asyncpg.UniqueViolationError:
        return None


async def _store_ig_comment(
    conn: asyncpg.Connection, tenant_id: UUID, ig_id: str, value: dict[str, Any]
) -> None:
    sender = value.get("from") or {}
    contact_handle = sender.get("id")
    display_name = sender.get("username")
    media_id = (value.get("media") or {}).get("id")
    text = value.get("text") or ""
    external_id = value.get("id")  # Meta's comment id

    if not contact_handle:
        logger.warning("IG comment with no sender.id; skipping: %s", value)
        return

    identity_id, contact_id = await _upsert_identity(
        conn, tenant_id, "instagram", contact_handle, display_name,
    )
    conv_id = await _upsert_conversation(
        conn, tenant_id, contact_id, identity_id, "instagram_comment", media_id, ig_id,
    )
    msg_id = await _insert_message(
        conn, tenant_id, conv_id, text, external_id, value,
    )
    if msg_id is not None:
        await queue.enqueue_classify_message(msg_id)
