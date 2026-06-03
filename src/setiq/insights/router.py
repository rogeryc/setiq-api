"""GET /insights — paginated feed of all tenant insights.

Powers the Recomendaciones page. The dashboard endpoint already returns the
top lead/featured/memos; this endpoint is for the dedicated full-list view.
"""
from typing import Literal

import asyncpg
from fastapi import APIRouter, Depends, Query

from setiq.auth.dependencies import get_tenant_db
from setiq.insights.schemas import (
    Insight,
    InsightAction,
    InsightsResponse,
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
    where_kind = "" if kind == "all" else "AND kind = $3"
    params: list[int | str] = [limit, offset]
    if kind != "all":
        params.append(kind)

    rows = await conn.fetch(
        f"""
        SELECT id, kind, severity, tag, title, title_em, title_tail,
               body, confidence, age, impact, footnote, actions, rank, created_at
        FROM insights
        WHERE deleted_at IS NULL
          AND enabled
          AND (valid_until IS NULL OR valid_until > NOW())
          {where_kind}
        ORDER BY
          CASE kind WHEN 'lead' THEN 0 WHEN 'featured' THEN 1 ELSE 2 END,
          rank,
          created_at DESC
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
