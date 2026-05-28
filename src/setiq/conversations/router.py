"""Read-only conversations endpoints for the Inbox.

GET /conversations?group_by=intent|channel|sentiment|thread  → grouped list
GET /conversations/{id}                                       → detail
GET /conversations/{id}?as_thread=true                        → thread detail
                                                                (all messages
                                                                 from all
                                                                 commenters on
                                                                 the post)
"""
from typing import Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from setiq.auth.dependencies import get_tenant_db
from setiq.conversations.schemas import (
    ConversationDetail,
    ConversationGroup,
    ConversationMutation,
    ConversationSummary,
    ConversationsResponse,
    ConversationUpdate,
    MessageDetail,
)

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
