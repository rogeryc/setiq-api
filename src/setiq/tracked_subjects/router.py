from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from setiq.auth.dependencies import get_tenant_db
from setiq.tracked_subjects.schemas import (
    TrackedSubjectCreate,
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
        last_mention_at=row["last_mention_at"] if "last_mention_at" in row else None,
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
