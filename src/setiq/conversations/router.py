"""Read-only conversations endpoints for the Inbox.

GET /conversations?group_by=intent|channel|sentiment|thread  → grouped list
GET /conversations/{id}                                       → detail
"""
from typing import Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from setiq.auth.dependencies import get_tenant_db
from setiq.conversations.schemas import (
    ConversationDetail,
    ConversationGroup,
    ConversationSummary,
    ConversationsResponse,
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

# Order in which groups should appear in the response (stable per group_by).
INTENT_ORDER = list(INTENT_LABELS.keys())
SENTIMENT_ORDER = ["negative", "neutral", "positive"]


_SUMMARY_QUERY = """
WITH last_msg AS (
    SELECT DISTINCT ON (conversation_id)
        conversation_id,
        content_text,
        sent_at
    FROM messages
    ORDER BY conversation_id, sent_at DESC
),
last_class AS (
    SELECT DISTINCT ON (m.conversation_id, mc.kind)
        m.conversation_id,
        mc.kind,
        mc.label
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
    c.id,
    c.channel,
    c.status,
    c.subject,
    c.last_message_at,
    co.display_name           AS contact_name,
    ci.external_id            AS contact_handle,
    lm.content_text           AS last_message_preview,
    (SELECT COUNT(*) FROM messages mm WHERE mm.conversation_id = c.id) AS message_count,
    p.sentiment,
    p.intent,
    p.priority
FROM conversations c
JOIN contacts          co ON co.id = c.contact_id
JOIN channel_identities ci ON ci.id = c.channel_identity_id
LEFT JOIN last_msg     lm ON lm.conversation_id = c.id
LEFT JOIN pivot        p  ON p.conversation_id = c.id
ORDER BY c.last_message_at DESC NULLS LAST
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
    rows = await conn.fetch(_SUMMARY_QUERY)
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
    return ConversationsResponse(
        group_by=group_by,
        total=len(summaries),
        groups=groups,
    )


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
        # channel / thread → biggest first
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
    if group_by == "thread":
        return s.subject or "Sin asunto"
    return "other"


def _bucket_label(key: str, group_by: GroupBy) -> str:
    if group_by == "intent":
        return INTENT_LABELS.get(key, key.title())
    if group_by == "sentiment":
        return SENTIMENT_LABELS.get(key, key.title())
    if group_by == "channel":
        return CHANNEL_LABELS.get(key, key)
    return key  # thread: subject is already human-readable


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
    response_model_exclude_none=True,
)
async def get_conversation(
    conversation_id: UUID,
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> ConversationDetail:
    row = await conn.fetchrow(
        """
        WITH last_class AS (
            SELECT DISTINCT ON (m.conversation_id, mc.kind)
                m.conversation_id,
                mc.kind,
                mc.label
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
