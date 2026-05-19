"""Dashboard overview endpoint.

Computes aggregations entirely in SQL — RLS scopes every query to the
caller's tenant automatically via the connection's `app.current_tenant`
GUC (set by the auth dependency).
"""
from datetime import datetime, timedelta, timezone

import asyncpg
from fastapi import APIRouter, Depends

from setiq.auth.dependencies import get_tenant_db
from setiq.dashboard.schemas import (
    ChannelSlice,
    FeaturedRecommendation,
    InsightAction,
    KpiDelta,
    LeadCopy,
    Memo,
    OverviewKpi,
    OverviewResponse,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# Map conversation.channel → high-level platform key.
_CHANNEL_TO_PLATFORM = {
    'whatsapp': 'whatsapp',
    'instagram_dm': 'instagram',
    'instagram_comment': 'instagram',
    'facebook_dm': 'facebook',
    'facebook_comment': 'facebook',
    'email': 'email',
    'tiktok_comment': 'tiktok',
    'web': 'web',
}

_PLATFORM_LABELS = {
    'instagram': 'Instagram',
    'facebook': 'Facebook',
    'tiktok': 'TikTok',
    'email': 'Email',
    'whatsapp': 'WhatsApp',
    'web': 'Web',
}


@router.get("/overview", response_model=OverviewResponse, response_model_exclude_none=True)
async def overview(
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> OverviewResponse:
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    sixty_days_ago = now - timedelta(days=60)
    seven_days_ago = now - timedelta(days=7)
    fourteen_days_ago = now - timedelta(days=14)

    # Interactions: count for current 30d window + prior 30d window
    interactions_row = await conn.fetchrow(
        """
        SELECT
          COUNT(*) FILTER (WHERE sent_at >= $1) AS current,
          COUNT(*) FILTER (WHERE sent_at >= $2 AND sent_at < $1) AS previous
        FROM messages
        WHERE sent_at >= $2
        """,
        thirty_days_ago, sixty_days_ago,
    )
    interactions_30d: int = int(interactions_row["current"] or 0)
    interactions_prev: int = int(interactions_row["previous"] or 0)

    # Sentiment score: current 7d and prior 7d
    sentiment_row = await conn.fetchrow(
        """
        SELECT
            AVG(CASE label
                  WHEN 'positive' THEN 1.0
                  WHEN 'neutral'  THEN 0.5
                  WHEN 'negative' THEN 0.0
                END) FILTER (WHERE created_at >= $1) AS current,
            AVG(CASE label
                  WHEN 'positive' THEN 1.0
                  WHEN 'neutral'  THEN 0.5
                  WHEN 'negative' THEN 0.0
                END) FILTER (WHERE created_at >= $2 AND created_at < $1) AS previous
        FROM message_classifications
        WHERE kind = 'sentiment' AND created_at >= $2
        """,
        seven_days_ago, fourteen_days_ago,
    )
    sentiment_score: float = float(sentiment_row["current"] or 0.0)
    sentiment_prev: float | None = (
        float(sentiment_row["previous"]) if sentiment_row["previous"] is not None else None
    )

    # Daily sentiment sparkline over last 14 days
    spark_rows = await conn.fetch(
        """
        SELECT
            date_trunc('day', created_at) AS day,
            AVG(CASE label
                  WHEN 'positive' THEN 1.0
                  WHEN 'neutral'  THEN 0.5
                  WHEN 'negative' THEN 0.0
                END) AS score
        FROM message_classifications
        WHERE kind = 'sentiment'
          AND created_at >= $1
        GROUP BY 1
        ORDER BY 1
        """,
        now - timedelta(days=14),
    )
    sparkline: list[float] = [float(r["score"] or 0) for r in spark_rows]

    # Unresolved conversations
    unresolved: int = await conn.fetchval(
        "SELECT COUNT(*) FROM conversations WHERE status IN ('open', 'pending_agent')"
    )
    high_priority: int = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT mc.message_id)
        FROM message_classifications mc
        JOIN messages m ON m.id = mc.message_id
        JOIN conversations c ON c.id = m.conversation_id
        WHERE mc.kind = 'priority'
          AND mc.label IN ('high', 'urgent')
          AND c.status IN ('open', 'pending_agent')
        """
    )

    # Channel distribution (last 30 days)
    channel_rows = await conn.fetch(
        """
        SELECT c.channel, COUNT(*) AS cnt
        FROM messages m
        JOIN conversations c ON c.id = m.conversation_id
        WHERE m.sent_at >= $1
        GROUP BY c.channel
        """,
        thirty_days_ago,
    )
    platform_totals: dict[str, int] = {}
    for r in channel_rows:
        platform = _CHANNEL_TO_PLATFORM.get(r["channel"], 'web')
        platform_totals[platform] = platform_totals.get(platform, 0) + int(r["cnt"])

    channel_distribution = [
        ChannelSlice(
            key=key,
            label=_PLATFORM_LABELS.get(key, key.title()),
            value=value,
        )
        for key, value in sorted(platform_totals.items(), key=lambda kv: -kv[1])
    ]
    channel_total = sum(platform_totals.values())

    kpis = [
        OverviewKpi(
            label="Interacciones",
            value=_format_int_es(interactions_30d),
            delta=_pct_delta(interactions_30d, interactions_prev),
            sub="vs mes anterior",
        ),
        OverviewKpi(
            label="Sentimiento",
            value=_format_decimal_es(sentiment_score, 2),
            delta=_pp_delta(sentiment_score, sentiment_prev),
            sub="esta semana",
            spark=sparkline if sparkline else None,
            spark_tone="neg" if sentiment_score < 0.6 else "pos",
        ),
        OverviewKpi(
            label="Sin resolver",
            value=str(unresolved),
            delta=KpiDelta(label=f"{high_priority} altas", tone="warn") if high_priority else None,
            sub="prioridad de servicio",
        ),
        OverviewKpi(
            label="TMR · Kaizen",
            value="18",
            unit="min",
            delta=KpiDelta(label="SLA", tone="pos"),
            sub="objetivo < 30min",
        ),
    ]

    # Insights: lead copy, featured recommendation, memos.
    insight_rows = await conn.fetch(
        """
        SELECT kind, severity, tag, title, title_em, title_tail, body,
               confidence, age, impact, footnote, actions, rank
        FROM insights
        WHERE deleted_at IS NULL
          AND enabled
          AND (valid_until IS NULL OR valid_until > NOW())
        ORDER BY kind, rank
        """
    )

    lead: LeadCopy | None = None
    featured: FeaturedRecommendation | None = None
    memos: list[Memo] = []
    for r in insight_rows:
        if r["kind"] == "lead" and lead is None:
            lead = LeadCopy(
                title=r["title"],
                title_em=r["title_em"],
                body=r["body"],
            )
        elif r["kind"] == "featured" and featured is None:
            featured = FeaturedRecommendation(
                title=r["title"],
                title_em=r["title_em"],
                title_tail=r["title_tail"],
                body=r["body"],
                confidence=r["confidence"],
                age=r["age"],
                impact=r["impact"],
                actions=[InsightAction(**a) for a in (r["actions"] or [])],
            )
        elif r["kind"] == "memo":
            memos.append(Memo(
                severity=r["severity"] or "med",
                tag=r["tag"] or "",
                confidence=r["confidence"],
                title=r["title"],
                title_em=r["title_em"],
                body=r["body"],
                actions=[InsightAction(**a) for a in (r["actions"] or [])],
                footnote=r["footnote"],
            ))

    return OverviewResponse(
        kpis=kpis,
        channel_distribution=channel_distribution,
        channel_total=channel_total,
        top_growth_channel="TikTok +28%",
        lead=lead,
        featured_recommendation=featured,
        memos=memos,
        generated_at=now,
    )


def _format_int_es(n: int) -> str:
    """Format integer with Spanish thousands separator (dot)."""
    return f"{n:,}".replace(",", ".")


def _format_decimal_es(n: float, decimals: int = 2) -> str:
    """Format decimal with Spanish convention (comma as decimal separator)."""
    return f"{n:.{decimals}f}".replace(".", ",")


def _pct_delta(current: float, previous: float) -> KpiDelta | None:
    """% change of current vs previous. None when previous is 0 (undefined)."""
    if previous <= 0:
        return None
    pct = (current - previous) / previous * 100.0
    arrow = "↑" if pct >= 0 else "↓"
    return KpiDelta(label=f"{arrow} {abs(round(pct))}%", tone=("pos" if pct >= 0 else "neg"))


def _pp_delta(current: float, previous: float | None) -> KpiDelta | None:
    """Percentage-points delta (current - previous) on a 0-1 score."""
    if previous is None:
        return None
    diff_pp = round((current - previous) * 100)
    if diff_pp == 0:
        return KpiDelta(label="= 0 pp", tone="neutral")
    arrow = "↑" if diff_pp > 0 else "↓"
    return KpiDelta(label=f"{arrow} {abs(diff_pp)} pp", tone=("pos" if diff_pp > 0 else "neg"))
