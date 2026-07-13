"""GET /insights — paginated feed of all tenant insights.
PATCH /insights/{id} — assign / unassign the owner (currently the only
mutable field; keep the shape open for future fields like dismissal).

Powers the Recomendaciones page. The dashboard endpoint already returns the
top lead/featured/memos; this endpoint is for the dedicated full-list view.
"""
from typing import Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from setiq.auth.dependencies import get_tenant_db
from setiq.insights.schemas import (
    Insight,
    InsightAction,
    InsightMutation,
    InsightsResponse,
    InsightUpdate,
)

router = APIRouter(prefix="/insights", tags=["insights"])

KindFilter = Literal["all", "lead", "featured", "memo"]


@router.get("", response_model=InsightsResponse, response_model_exclude_none=True)
async def list_insights(
    kind: KindFilter = Query("all"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> InsightsResponse:
    where_kind = "" if kind == "all" else "AND i.kind = $3"
    params: list[int | str] = [limit, offset]
    if kind != "all":
        params.append(kind)

    rows = await conn.fetch(
        f"""
        SELECT i.id, i.kind, i.severity, i.tag, i.title, i.title_em, i.title_tail,
               i.body, i.confidence, i.age, i.impact, i.footnote, i.actions,
               i.rank, i.created_at, i.assigned_user_id,
               u.name AS assigned_user_name
        FROM insights i
        LEFT JOIN users u ON u.id = i.assigned_user_id
        WHERE i.deleted_at IS NULL
          AND i.enabled
          AND (i.valid_until IS NULL OR i.valid_until > NOW())
          {where_kind}
        ORDER BY
          CASE i.kind WHEN 'lead' THEN 0 WHEN 'featured' THEN 1 ELSE 2 END,
          i.rank,
          i.created_at DESC
        LIMIT $1 OFFSET $2
        """,
        *params,
    )

    insights = [
        Insight(
            id=r["id"],
            kind=r["kind"],
            severity=r["severity"],
            tag=r["tag"],
            title=r["title"],
            title_em=r["title_em"],
            title_tail=r["title_tail"],
            body=r["body"],
            confidence=r["confidence"],
            age=r["age"],
            impact=r["impact"],
            footnote=r["footnote"],
            actions=[InsightAction(**a) for a in (r["actions"] or [])],
            rank=r["rank"],
            created_at=r["created_at"],
            assigned_user_id=r["assigned_user_id"],
            assigned_user_name=r["assigned_user_name"],
        )
        for r in rows
    ]

    count_rows = await conn.fetch(
        """
        SELECT kind, COUNT(*) AS n
        FROM insights
        WHERE deleted_at IS NULL
          AND enabled
          AND (valid_until IS NULL OR valid_until > NOW())
        GROUP BY kind
        """
    )
    counts = {r["kind"]: int(r["n"]) for r in count_rows}
    total = sum(counts.values())

    return InsightsResponse(insights=insights, total=total, counts=counts)


@router.patch("/{insight_id}", response_model=InsightMutation)
async def update_insight(
    insight_id: UUID,
    body: InsightUpdate,
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> InsightMutation:
    """Assign or unassign the insight. `assigned_user_id=null` clears the
    assignee. Rejects users who aren't members of the current tenant so a
    caller can't assign to an outsider."""
    # If we're assigning to a real user (not clearing), verify tenant membership.
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

    row = await conn.fetchrow(
        """
        UPDATE insights SET assigned_user_id = $1
        WHERE id = $2
        RETURNING id, assigned_user_id
        """,
        body.assigned_user_id,
        insight_id,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Insight not found")

    # Fetch the human name so the client can render "Asignado a X" without
    # having to re-hit the team endpoint.
    name = None
    if row["assigned_user_id"] is not None:
        name = await conn.fetchval(
            "SELECT name FROM users WHERE id = $1", row["assigned_user_id"]
        )

    return InsightMutation(
        id=row["id"],
        assigned_user_id=row["assigned_user_id"],
        assigned_user_name=name,
    )
