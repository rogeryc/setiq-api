"""Read-only conversations endpoints for the Inbox.

GET /conversations?group_by=intent|channel|sentiment|thread  → grouped list
GET /conversations/{id}                                       → detail
GET /conversations/{id}?as_thread=true                        → thread detail
                                                                (all messages
                                                                 from all
                                                                 commenters on
                                                                 the post)
"""
import logging
from typing import Any, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from setiq.auth.dependencies import CurrentUser, get_current_user, get_tenant_db
from setiq.config import settings
from setiq.conversations.schemas import (
    ConversationDetail,
    ConversationGroup,
    ConversationMutation,
    ConversationsResponse,
    ConversationSummary,
    ConversationUpdate,
    MessageDetail,
    ReplyRequest,
    ReplyResponse,
)
from setiq.integrations.meta import MetaApiError, MetaClient
from setiq.integrations.secrets import decrypt_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])

GroupBy = Literal["intent", "channel", "sentiment", "thread"]

INTENT_LABELS: dict[str, str] = {
    "complaint":       "Quejas",
    "praise":          "Elogios",
    "question":        "Consultas",
    "purchase_intent": "Oportunidades",
    "support_request": "Soporte",
    "spam":            "Spam",
    "other":           "Otras",
}

SENTIMENT_LABELS: dict[str, str] = {
    "positive": "Positivos",
    "neutral":  "Neutrales",
    "negative": "Negativos",
}

CHANNEL_LABELS: dict[str, str] = {
    "instagram_comment": "Instagram · comentarios",
    "instagram_dm":      "Instagram · DMs",
    "facebook_comment":  "Facebook · comentarios",
    "facebook_dm":       "Facebook · Messenger",
    "tiktok_comment":    "TikTok · comentarios",
    "email":             "Email",
    "whatsapp":          "WhatsApp",
    "web":               "Web",
}

INTENT_ORDER = list(INTENT_LABELS.keys())
SENTIMENT_ORDER = ["negative", "neutral", "positive"]


_PER_CONVERSATION_QUERY = """
WITH last_msg AS (
    SELECT DISTINCT ON (conversation_id)
        conversation_id, content_text, sent_at
    FROM messages
    ORDER BY conversation_id, sent_at DESC
),
last_class AS (
    SELECT DISTINCT ON (m.conversation_id, mc.kind)
        m.conversation_id, mc.kind, mc.label
    FROM message_classifications mc
    JOIN messages m ON m.id = mc.message_id
    WHERE mc.kind IN ('sentiment', 'intent', 'priority')
    ORDER BY m.conversation_id, mc.kind, mc.created_at DESC
),
pivot AS (
    SELECT
        conversation_id,
        MAX(label) FILTER (WHERE kind = 'sentiment') AS sentiment,
        MAX(label) FILTER (WHERE kind = 'intent')    AS intent,
        MAX(label) FILTER (WHERE kind = 'priority')  AS priority
    FROM last_class
    GROUP BY conversation_id
)
SELECT
    c.id, c.channel, c.status, c.subject, c.last_message_at,
    co.display_name           AS contact_name,
    ci.external_id            AS contact_handle,
    lm.content_text           AS last_message_preview,
    (SELECT COUNT(*) FROM messages mm WHERE mm.conversation_id = c.id) AS message_count,
    p.sentiment, p.intent, p.priority
FROM conversations c
JOIN contacts          co ON co.id = c.contact_id
JOIN channel_identities ci ON ci.id = c.channel_identity_id
LEFT JOIN last_msg     lm ON lm.conversation_id = c.id
LEFT JOIN pivot        p  ON p.conversation_id = c.id
ORDER BY c.last_message_at DESC NULLS LAST
"""


# Thread-mode query: aggregate by (channel, external_thread_id). Each row
# represents a post; we pick the conversation with the latest message as the
# `id` so the frontend has a valid handle for the detail endpoint.
_THREAD_QUERY = """
WITH conv_with_msgs AS (
    SELECT
        c.id AS conversation_id,
        c.channel,
        c.external_thread_id,
        c.subject,
        c.contact_id,
        c.last_message_at,
        (SELECT COUNT(*) FROM messages mm WHERE mm.conversation_id = c.id) AS msg_count
    FROM conversations c
    WHERE c.external_thread_id IS NOT NULL
),
thread_pick AS (
    -- Pick the conversation with the most recent activity for each thread
    SELECT DISTINCT ON (channel, external_thread_id)
        channel, external_thread_id, conversation_id, last_message_at
    FROM conv_with_msgs
    ORDER BY channel, external_thread_id, last_message_at DESC NULLS LAST
),
last_msg_on_thread AS (
    SELECT DISTINCT ON (c.channel, c.external_thread_id)
        c.channel, c.external_thread_id,
        m.id AS message_id, m.content_text, m.sent_at,
        co.display_name AS contact_name,
        ci.external_id  AS contact_handle
    FROM messages m
    JOIN conversations c ON c.id = m.conversation_id
    JOIN contacts          co ON co.id = c.contact_id
    JOIN channel_identities ci ON ci.id = c.channel_identity_id
    WHERE c.external_thread_id IS NOT NULL
    ORDER BY c.channel, c.external_thread_id, m.sent_at DESC
),
last_class AS (
    SELECT DISTINCT ON (message_id, kind) message_id, kind, label
    FROM message_classifications
    WHERE kind IN ('sentiment', 'intent', 'priority')
    ORDER BY message_id, kind, created_at DESC
)
SELECT
    tp.conversation_id                                            AS id,
    cwm.channel                                                   AS channel,
    cwm.external_thread_id                                        AS external_thread_id,
    cwm.subject                                                   AS subject,
    'open'                                                        AS status,
    COUNT(DISTINCT cwm.contact_id)                                AS participant_count,
    SUM(cwm.msg_count)                                            AS message_count,
    lmot.sent_at                                                  AS last_message_at,
    lmot.content_text                                             AS last_message_preview,
    lmot.contact_name                                             AS contact_name,
    lmot.contact_handle                                           AS contact_handle,
    (SELECT label FROM last_class WHERE message_id = lmot.message_id AND kind = 'sentiment') AS sentiment,
    (SELECT label FROM last_class WHERE message_id = lmot.message_id AND kind = 'intent')    AS intent,
    (SELECT label FROM last_class WHERE message_id = lmot.message_id AND kind = 'priority')  AS priority
FROM conv_with_msgs cwm
JOIN thread_pick        tp   ON tp.channel = cwm.channel AND tp.external_thread_id = cwm.external_thread_id
JOIN last_msg_on_thread lmot ON lmot.channel = cwm.channel AND lmot.external_thread_id = cwm.external_thread_id
GROUP BY tp.conversation_id, cwm.channel, cwm.external_thread_id, cwm.subject,
         lmot.sent_at, lmot.content_text, lmot.contact_name, lmot.contact_handle, lmot.message_id
ORDER BY lmot.sent_at DESC NULLS LAST
"""


@router.get(
    "",
    response_model=ConversationsResponse,
    response_model_exclude_none=True,
)
async def list_conversations(
    group_by: GroupBy = Query("intent"),
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> ConversationsResponse:
    if group_by == "thread":
        return await _list_threads(conn)

    rows = await conn.fetch(_PER_CONVERSATION_QUERY)
    summaries = [
        ConversationSummary(
            id=r["id"],
            contact_name=r["contact_name"],
            contact_handle=r["contact_handle"],
            channel=r["channel"],
            last_message_at=r["last_message_at"],
            last_message_preview=(r["last_message_preview"] or "")[:140] or None,
            message_count=int(r["message_count"] or 0),
            status=r["status"],
            subject=r["subject"],
            sentiment=r["sentiment"],
            intent=r["intent"],
            priority=r["priority"],
        )
        for r in rows
    ]
    groups = _group(summaries, group_by)
    return ConversationsResponse(group_by=group_by, total=len(summaries), groups=groups)


async def _list_threads(conn: asyncpg.Connection) -> ConversationsResponse:
    rows = await conn.fetch(_THREAD_QUERY)
    summaries = [
        ConversationSummary(
            id=r["id"],
            contact_name=f"{int(r['participant_count'])} personas"
                         if int(r["participant_count"]) > 1 else r["contact_name"],
            contact_handle=r["contact_handle"],
            channel=r["channel"],
            last_message_at=r["last_message_at"],
            last_message_preview=(r["last_message_preview"] or "")[:140] or None,
            message_count=int(r["message_count"] or 0),
            status=r["status"],
            subject=r["subject"],
            sentiment=r["sentiment"],
            intent=r["intent"],
            priority=r["priority"],
            participant_count=int(r["participant_count"]),
        )
        for r in rows
    ]
    # One group per channel for clarity (sorted by row count).
    buckets: dict[str, list[ConversationSummary]] = {}
    for s in summaries:
        buckets.setdefault(s.channel, []).append(s)
    groups = [
        ConversationGroup(
            key=channel,
            label=CHANNEL_LABELS.get(channel, channel),
            count=len(rows),
            conversations=rows,
        )
        for channel, rows in sorted(buckets.items(), key=lambda kv: -len(kv[1]))
    ]
    return ConversationsResponse(group_by="thread", total=len(summaries), groups=groups)


def _group(summaries: list[ConversationSummary], group_by: GroupBy) -> list[ConversationGroup]:
    buckets: dict[str, list[ConversationSummary]] = {}
    for s in summaries:
        key = _bucket_key(s, group_by)
        buckets.setdefault(key, []).append(s)

    if group_by == "intent":
        order = INTENT_ORDER + [k for k in buckets if k not in INTENT_ORDER]
    elif group_by == "sentiment":
        order = SENTIMENT_ORDER + [k for k in buckets if k not in SENTIMENT_ORDER]
    else:
        order = sorted(buckets.keys(), key=lambda k: -len(buckets[k]))

    out: list[ConversationGroup] = []
    for key in order:
        if key not in buckets:
            continue
        out.append(ConversationGroup(
            key=key,
            label=_bucket_label(key, group_by),
            count=len(buckets[key]),
            conversations=buckets[key],
        ))
    return out


def _bucket_key(s: ConversationSummary, group_by: GroupBy) -> str:
    if group_by == "intent":
        return s.intent or "other"
    if group_by == "sentiment":
        return s.sentiment or "neutral"
    if group_by == "channel":
        return s.channel
    return "other"


def _bucket_label(key: str, group_by: GroupBy) -> str:
    if group_by == "intent":
        return INTENT_LABELS.get(key, key.title())
    if group_by == "sentiment":
        return SENTIMENT_LABELS.get(key, key.title())
    if group_by == "channel":
        return CHANNEL_LABELS.get(key, key)
    return key


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
    response_model_exclude_none=True,
)
async def get_conversation(
    conversation_id: UUID,
    as_thread: bool = Query(False),
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> ConversationDetail:
    if as_thread:
        return await _get_thread_detail(conn, conversation_id)
    return await _get_single_conversation(conn, conversation_id)


@router.patch("/{conversation_id}", response_model=ConversationMutation)
async def update_conversation(
    conversation_id: UUID,
    body: ConversationUpdate,
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> ConversationMutation:
    sets: list[str] = []
    args: list[object] = []
    if body.status is not None:
        args.append(body.status)
        sets.append(f"status = ${len(args)}")
        args.append(body.status)
        sets.append(
            f"closed_at = CASE WHEN ${len(args)} IN ('resolved', 'closed') "
            "THEN NOW() ELSE NULL END"
        )
    if body.assigned_user_id is not None:
        is_member = await conn.fetchval(
            "SELECT 1 FROM tenant_users "
            "WHERE tenant_id = current_tenant_id() AND user_id = $1",
            body.assigned_user_id,
        )
        if not is_member:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Assignee is not a member of this tenant",
            )
        args.append(body.assigned_user_id)
        sets.append(f"assigned_user_id = ${len(args)}")

    if not sets:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nothing to update")

    args.append(conversation_id)
    row = await conn.fetchrow(
        f"UPDATE conversations SET {', '.join(sets)} "
        f"WHERE id = ${len(args)} "
        "RETURNING id, status, assigned_user_id",
        *args,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return ConversationMutation(
        id=row["id"],
        status=row["status"],
        assigned_user_id=row["assigned_user_id"],
    )


async def _get_single_conversation(
    conn: asyncpg.Connection, conversation_id: UUID,
) -> ConversationDetail:
    row = await conn.fetchrow(
        """
        WITH last_class AS (
            SELECT DISTINCT ON (m.conversation_id, mc.kind)
                m.conversation_id, mc.kind, mc.label
            FROM message_classifications mc
            JOIN messages m ON m.id = mc.message_id
            WHERE m.conversation_id = $1
              AND mc.kind IN ('sentiment', 'intent', 'priority')
            ORDER BY m.conversation_id, mc.kind, mc.created_at DESC
        )
        SELECT
            c.id, c.channel, c.status, c.subject, c.created_at, c.last_message_at,
            co.display_name AS contact_name,
            ci.external_id  AS contact_handle,
            (SELECT label FROM last_class WHERE kind = 'sentiment') AS sentiment,
            (SELECT label FROM last_class WHERE kind = 'intent')    AS intent,
            (SELECT label FROM last_class WHERE kind = 'priority')  AS priority
        FROM conversations c
        JOIN contacts          co ON co.id = c.contact_id
        JOIN channel_identities ci ON ci.id = c.channel_identity_id
        WHERE c.id = $1
        """,
        conversation_id,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")

    msg_rows = await conn.fetch(
        """
        SELECT
            m.id, m.direction, m.sender_type, m.content_type, m.content_text, m.sent_at,
            (SELECT label FROM message_classifications
             WHERE message_id = m.id AND kind = 'sentiment'
             ORDER BY created_at DESC LIMIT 1) AS sentiment,
            (SELECT label FROM message_classifications
             WHERE message_id = m.id AND kind = 'intent'
             ORDER BY created_at DESC LIMIT 1) AS intent
        FROM messages m
        WHERE m.conversation_id = $1
        ORDER BY m.sent_at
        """,
        conversation_id,
    )

    return ConversationDetail(
        id=row["id"],
        contact_name=row["contact_name"],
        contact_handle=row["contact_handle"],
        channel=row["channel"],
        status=row["status"],
        subject=row["subject"],
        created_at=row["created_at"],
        last_message_at=row["last_message_at"],
        sentiment=row["sentiment"],
        intent=row["intent"],
        priority=row["priority"],
        messages=[
            MessageDetail(
                id=m["id"],
                direction=m["direction"],
                sender_type=m["sender_type"],
                content_type=m["content_type"],
                content_text=m["content_text"],
                sent_at=m["sent_at"],
                sentiment=m["sentiment"],
                intent=m["intent"],
            )
            for m in msg_rows
        ],
    )


async def _get_thread_detail(
    conn: asyncpg.Connection, conversation_id: UUID,
) -> ConversationDetail:
    """Look up the conversation, then return every message from every contact
    who posted on the same (channel, external_thread_id)."""
    seed = await conn.fetchrow(
        """
        SELECT id, channel, external_thread_id, subject, created_at
        FROM conversations
        WHERE id = $1
        """,
        conversation_id,
    )
    if seed is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    if seed["external_thread_id"] is None:
        # Falling back to single conversation if there's no thread to expand.
        return await _get_single_conversation(conn, conversation_id)

    msg_rows = await conn.fetch(
        """
        SELECT
            m.id, m.direction, m.sender_type, m.content_type, m.content_text, m.sent_at,
            co.display_name AS sender_name,
            ci.external_id  AS sender_handle,
            (SELECT label FROM message_classifications
             WHERE message_id = m.id AND kind = 'sentiment'
             ORDER BY created_at DESC LIMIT 1) AS sentiment,
            (SELECT label FROM message_classifications
             WHERE message_id = m.id AND kind = 'intent'
             ORDER BY created_at DESC LIMIT 1) AS intent
        FROM messages m
        JOIN conversations      c  ON c.id = m.conversation_id
        JOIN contacts           co ON co.id = c.contact_id
        JOIN channel_identities ci ON ci.id = c.channel_identity_id
        WHERE c.channel = $1
          AND c.external_thread_id = $2
        ORDER BY m.sent_at
        """,
        seed["channel"], seed["external_thread_id"],
    )

    participants = {(m["sender_handle"], m["sender_name"]) for m in msg_rows}
    last_at = max((m["sent_at"] for m in msg_rows), default=None)

    return ConversationDetail(
        id=seed["id"],
        contact_name=f"Hilo · {len(participants)} personas",
        contact_handle=seed["external_thread_id"],
        channel=seed["channel"],
        status="open",
        subject=seed["subject"],
        created_at=seed["created_at"],
        last_message_at=last_at,
        is_thread=True,
        participant_count=len(participants),
        messages=[
            MessageDetail(
                id=m["id"],
                direction=m["direction"],
                sender_type=m["sender_type"],
                content_type=m["content_type"],
                content_text=m["content_text"],
                sent_at=m["sent_at"],
                sentiment=m["sentiment"],
                intent=m["intent"],
                sender_name=m["sender_name"],
                sender_handle=m["sender_handle"],
            )
            for m in msg_rows
        ],
    )


# ---------------------------------------------------------------------------
# Reply — POST /conversations/{id}/reply
# ---------------------------------------------------------------------------

def _pick_connected_page(settings_obj: dict[str, Any], channel: str) -> dict[str, Any] | None:
    """Pick the page that owns this channel.

    MVP heuristic: take the first connected page in the tenant's
    settings.meta.connected_pages list. Multi-page tenants will need
    a `received_by_page_id` column on conversations to map back precisely;
    deferred until we have a tenant with > 1 page.
    """
    pages: list[dict[str, Any]] = ((settings_obj or {}).get("meta") or {}).get("connected_pages") or []
    if not pages:
        return None
    # For IG channels, prefer a page that has a linked IG account.
    if channel.startswith("instagram"):
        for p in pages:
            if p.get("instagram_business_account"):
                return p
        return None
    return pages[0]


@router.post(
    "/{conversation_id}/reply",
    response_model=ReplyResponse,
    response_model_exclude_none=True,
)
async def reply_to_conversation(
    conversation_id: UUID,
    body: ReplyRequest,
    current_user: CurrentUser = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> ReplyResponse:
    """Send a reply via Meta and persist it as an outbound message.

    What we do, per channel:
      - instagram_comment: reply on the comment (POST /{comment_id}/replies)
      - instagram_dm:      send DM to the contact's IGSID (POST /me/messages)
      - facebook_comment:  reply on the comment (POST /{comment_id}/comments)
      - facebook_dm:       send Messenger message to the contact's PSID
                           (POST /me/messages)

    Other channels (email, tiktok_comment, etc.) aren't wired yet — they
    return 501 Not Implemented.
    """
    # Resolve conversation + its last inbound message (we need the comment_id
    # for comment replies, or the contact's external_id for DMs).
    conv = await conn.fetchrow(
        """
        SELECT c.id, c.channel, c.status,
               ci.external_id AS contact_external_id
        FROM conversations c
        JOIN channel_identities ci ON ci.id = c.channel_identity_id
        WHERE c.id = $1
        """,
        conversation_id,
    )
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")

    channel = conv["channel"]
    if channel not in ("instagram_comment", "instagram_dm", "facebook_comment", "facebook_dm"):
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            f"Reply not implemented for channel '{channel}' yet",
        )

    # For comment channels we need the original comment's external_id (the
    # most recent inbound message in this conversation).
    last_inbound = await conn.fetchrow(
        """
        SELECT id, external_id FROM messages
        WHERE conversation_id = $1 AND direction = 'inbound'
        ORDER BY sent_at DESC LIMIT 1
        """,
        conversation_id,
    )
    if last_inbound is None and channel.endswith("_comment"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Cannot reply to a comment thread that has no inbound messages",
        )

    # Find the right page token. RLS already scoped us to the current tenant,
    # so an unqualified select on tenants returns this tenant's row.
    tenant_row = await conn.fetchrow(
        "SELECT settings FROM tenants WHERE id = current_tenant_id()"
    )
    if tenant_row is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Tenant resolution failed")

    page = _pick_connected_page(tenant_row["settings"] or {}, channel)
    if page is None:
        raise HTTPException(
            status.HTTP_412_PRECONDITION_FAILED,
            "No Meta page connected for this channel. Connect one in /canales first.",
        )

    try:
        page_token = decrypt_token(page["page_token"])
    except RuntimeError as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e)) from e

    client = MetaClient(settings.meta_app_id, settings.meta_app_secret)

    # Dispatch to the right Graph method.
    try:
        if channel == "instagram_comment":
            result = await client.reply_to_ig_comment(last_inbound["external_id"], body.text, page_token)
        elif channel == "facebook_comment":
            result = await client.reply_to_fb_comment(last_inbound["external_id"], body.text, page_token)
        elif channel == "instagram_dm":
            result = await client.send_ig_dm(conv["contact_external_id"], body.text, page_token)
        elif channel == "facebook_dm":
            result = await client.send_messenger_message(conv["contact_external_id"], body.text, page_token)
        else:
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"channel {channel}")
    except MetaApiError as e:
        logger.warning("reply failed: conv=%s channel=%s err=%s", conversation_id, channel, e)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Meta rejected the reply: {e.message}",
        ) from e

    meta_external_id = result.get("id") or result.get("message_id")

    # Persist the outbound message so the inbox reflects it immediately.
    msg_row = await conn.fetchrow(
        """
        INSERT INTO messages (
            tenant_id, conversation_id, direction, sender_type,
            sender_user_id, content_type, content_text,
            external_id, sent_at, raw_payload
        ) VALUES (
            current_tenant_id(), $1, 'outbound', 'agent', $2, 'text', $3, $4,
            NOW(), '{"source": "operator_reply"}'::jsonb
        )
        RETURNING id, direction, sender_type, content_type, content_text, sent_at
        """,
        conversation_id, current_user.user_id, body.text, meta_external_id,
    )
    await conn.execute(
        "UPDATE conversations SET last_message_at = NOW() WHERE id = $1",
        conversation_id,
    )

    return ReplyResponse(
        message=MessageDetail(
            id=msg_row["id"],
            direction=msg_row["direction"],
            sender_type=msg_row["sender_type"],
            content_type=msg_row["content_type"],
            content_text=msg_row["content_text"],
            sent_at=msg_row["sent_at"],
        ),
        external_id=meta_external_id,
    )
