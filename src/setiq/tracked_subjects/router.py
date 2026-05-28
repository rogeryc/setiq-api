from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from setiq.auth.dependencies import get_tenant_db
from setiq.tracked_subjects.schemas import (
    MentionPreview,
    OverlapContact,
    SentimentBreakdown,
    TrackedSubjectCreate,
    TrackedSubjectDetail,
    TrackedSubjectResponse,
    TrackedSubjectUpdate,
)

router = APIRouter(prefix="/tracked-subjects", tags=["tracked-subjects"])


def _row_to_response(row: asyncpg.Record) -> TrackedSubjectResponse:
    return TrackedSubjectResponse(
        id=row["id"],
        kind=row["kind"],
        label=row["label"],
        handles=row["handles"] or {},
        keywords=list(row["keywords"] or []),
        hashtags=list(row["hashtags"] or []),
        enabled=row["enabled"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        mention_count=int(row["mention_count"] or 0) if "mention_count" in row else 0,
        last_mention_at=row.get("last_mention_at"),
    )


@router.get("", response_model=list[TrackedSubjectResponse], response_model_exclude_none=True)
async def list_subjects(
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> list[TrackedSubjectResponse]:
    rows = await conn.fetch(
        """
        SELECT
            ts.id, ts.kind, ts.label, ts.handles, ts.keywords, ts.hashtags,
            ts.enabled, ts.created_at, ts.updated_at,
            (SELECT COUNT(*) FROM mentions m WHERE m.tracked_subject_id = ts.id) AS mention_count,
            (SELECT MAX(content_published_at) FROM mentions m WHERE m.tracked_subject_id = ts.id) AS last_mention_at
        FROM tracked_subjects ts
        WHERE ts.deleted_at IS NULL
        ORDER BY ts.created_at DESC
        """
    )
    return [_row_to_response(r) for r in rows]


@router.get(
    "/{subject_id}/detail",
    response_model=TrackedSubjectDetail,
    response_model_exclude_none=True,
)
async def subject_detail(
    subject_id: UUID,
    limit: int = Query(10, ge=1, le=50),
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> TrackedSubjectDetail:
    subj = await conn.fetchrow(
        "SELECT id, kind, label FROM tracked_subjects "
        "WHERE id = $1 AND deleted_at IS NULL",
        subject_id,
    )
    if subj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tracked subject not found")

    total = await conn.fetchval(
        "SELECT COUNT(*) FROM mentions WHERE tracked_subject_id = $1", subject_id
    )

    sentiment_rows = await conn.fetch(
        """
        SELECT sc.label, COUNT(*) AS cnt
        FROM mentions m
        JOIN LATERAL (
            SELECT label FROM mention_classifications mc
            WHERE mc.mention_id = m.id AND mc.kind = 'sentiment'
            ORDER BY confidence DESC NULLS LAST
            LIMIT 1
        ) sc ON true
        WHERE m.tracked_subject_id = $1
        GROUP BY sc.label
        """,
        subject_id,
    )
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    for r in sentiment_rows:
        if r["label"] in counts:
            counts[r["label"]] = int(r["cnt"])
    breakdown = SentimentBreakdown(**counts)

    recent_rows = await conn.fetch(
        """
        SELECT m.id, m.platform, m.author_display_name, m.author_handle,
               m.content_text, m.content_url, m.content_published_at,
               sc.label AS sentiment
        FROM mentions m
        LEFT JOIN LATERAL (
            SELECT label FROM mention_classifications mc
            WHERE mc.mention_id = m.id AND mc.kind = 'sentiment'
            ORDER BY confidence DESC NULLS LAST
            LIMIT 1
        ) sc ON true
        WHERE m.tracked_subject_id = $1
        ORDER BY m.content_published_at DESC NULLS LAST
        LIMIT $2
        """,
        subject_id, limit,
    )
    recent = [
        MentionPreview(
            id=r["id"],
            platform=r["platform"],
            author_display_name=r["author_display_name"],
            author_handle=r["author_handle"],
            content_text=r["content_text"],
            content_url=r["content_url"],
            published_at=r["content_published_at"],
            sentiment=r["sentiment"],
        )
        for r in recent_rows
    ]

    overlap_rows = await conn.fetch(
        """
        SELECT DISTINCT c.id, c.display_name
        FROM contacts c
        JOIN channel_identities ci ON ci.contact_id = c.id
        WHERE c.deleted_at IS NULL
          AND EXISTS (
            SELECT 1 FROM mentions m
            WHERE m.tracked_subject_id = $1
              AND lower(ltrim(m.author_handle, '@')) = lower(ltrim(ci.external_id, '@'))
          )
        LIMIT 20
        """,
        subject_id,
    )
    overlap = [OverlapContact(id=r["id"], display_name=r["display_name"]) for r in overlap_rows]

    return TrackedSubjectDetail(
        id=subj["id"],
        kind=subj["kind"],
        label=subj["label"],
        mention_count=int(total or 0),
        sentiment_breakdown=breakdown,
        recent_mentions=recent,
        audience_overlap=overlap,
    )


@router.post("", response_model=TrackedSubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    body: TrackedSubjectCreate,
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> TrackedSubjectResponse:
    row = await conn.fetchrow(
        """
        INSERT INTO tracked_subjects (
            tenant_id, kind, label, handles, keywords, hashtags, enabled
        ) VALUES (current_tenant_id(), $1, $2, $3, $4, $5, $6)
        RETURNING id, kind, label, handles, keywords, hashtags, enabled,
                  created_at, updated_at
        """,
        body.kind,
        body.label,
        body.handles,
        body.keywords,
        body.hashtags,
        body.enabled,
    )
    return _row_to_response(row)


@router.patch("/{subject_id}", response_model=TrackedSubjectResponse)
async def update_subject(
    subject_id: UUID,
    body: TrackedSubjectUpdate,
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> TrackedSubjectResponse:
    row = await conn.fetchrow(
        """
        UPDATE tracked_subjects SET
            label    = COALESCE($1, label),
            handles  = COALESCE($2, handles),
            keywords = COALESCE($3, keywords),
            hashtags = COALESCE($4, hashtags),
            enabled  = COALESCE($5, enabled)
        WHERE id = $6 AND deleted_at IS NULL
        RETURNING id, kind, label, handles, keywords, hashtags, enabled,
                  created_at, updated_at
        """,
        body.label,
        body.handles,
        body.keywords,
        body.hashtags,
        body.enabled,
        subject_id,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tracked subject not found")
    return _row_to_response(row)


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject_id: UUID,
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> None:
    result = await conn.execute(
        "UPDATE tracked_subjects SET deleted_at = NOW() "
        "WHERE id = $1 AND deleted_at IS NULL",
        subject_id,
    )
    if result == "UPDATE 0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tracked subject not found")
