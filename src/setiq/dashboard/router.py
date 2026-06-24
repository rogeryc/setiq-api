"""Dashboard overview endpoint.

Computes aggregations entirely in SQL — RLS scopes every query to the
caller's tenant automatically via the connection's `app.current_tenant`
GUC (set by the auth dependency).
"""
from datetime import UTC, datetime, timedelta

import asyncpg
from fastapi import APIRouter, Depends, Query

from setiq.auth.dependencies import get_tenant_db
from setiq.dashboard.schemas import (
    ChannelSlice,
    CompetitorActivity,
    CompetitorActivityResponse,
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
    now = datetime.now(UTC)
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

    # TMR · Kaizen — mean response time (outbound after inbound in same convo)
    tmr_minutes = await _compute_tmr_minutes(conn, seven_days_ago, now)
    tmr_prev = await _compute_tmr_minutes(conn, fourteen_days_ago, seven_days_ago)
    tmr_kpi = _build_tmr_kpi(tmr_minutes, tmr_prev)

    # Backlog trend for "Sin resolver" — uses a message-direction heuristic
    # since we don't track conversation-status history. Returns the count
    # of conversations whose most-recent message as of the cutoff was
    # inbound (= waiting on us).
    backlog_now = await _compute_backlog_at(conn, None)
    backlog_prev = await _compute_backlog_at(conn, seven_days_ago)
    backlog_delta = _build_backlog_delta(backlog_now, backlog_prev, high_priority)

    kpis = [
        OverviewKpi(
            label="Sin resolver",
            value=str(unresolved),
            delta=backlog_delta,
            sub=f"{high_priority} de alta prioridad" if high_priority else "prioridad de servicio",
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
            label="Interacciones",
            value=_format_int_es(interactions_30d),
            delta=_pct_delta(interactions_30d, interactions_prev),
            sub="vs mes anterior",
        ),
        tmr_kpi,
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


@router.get(
    "/competitor-activity",
    response_model=CompetitorActivityResponse,
    response_model_exclude_none=True,
)
async def competitor_activity(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(5, ge=1, le=20),
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> CompetitorActivityResponse:
    now = datetime.now(UTC)
    current_start = now - timedelta(days=days)
    previous_start = now - timedelta(days=days * 2)

    rows = await conn.fetch(
        """
        SELECT
            ts.id,
            ts.label,
            COUNT(m.id) FILTER (WHERE m.content_published_at >= $1) AS current,
            COUNT(m.id) FILTER (
                WHERE m.content_published_at >= $2 AND m.content_published_at < $1
            ) AS previous,
            AVG(CASE sc.label
                  WHEN 'positive' THEN 1.0
                  WHEN 'neutral'  THEN 0.5
                  WHEN 'negative' THEN 0.0
                END) FILTER (WHERE m.content_published_at >= $1) AS sentiment
        FROM tracked_subjects ts
        LEFT JOIN mentions m
            ON m.tracked_subject_id = ts.id
           AND m.content_published_at >= $2
        LEFT JOIN LATERAL (
            SELECT label
            FROM mention_classifications mc
            WHERE mc.mention_id = m.id AND mc.kind = 'sentiment'
            ORDER BY confidence DESC NULLS LAST
            LIMIT 1
        ) sc ON true
        WHERE ts.kind = 'competitor' AND ts.deleted_at IS NULL
        GROUP BY ts.id, ts.label
        ORDER BY current DESC, ts.label
        LIMIT $3
        """,
        current_start, previous_start, limit,
    )

    competitors = [
        CompetitorActivity(
            id=r["id"],
            label=r["label"],
            mentions=int(r["current"] or 0),
            previous=int(r["previous"] or 0),
            delta=int(r["current"] or 0) - int(r["previous"] or 0),
            sentiment_score=(
                round(float(r["sentiment"]), 3) if r["sentiment"] is not None else None
            ),
        )
        for r in rows
    ]

    return CompetitorActivityResponse(
        period_days=days,
        competitors=competitors,
        generated_at=now,
    )


async def _compute_backlog_at(
    conn: asyncpg.Connection,
    cutoff: datetime | None,
) -> int:
    """Count conversations whose most recent message at `cutoff` was inbound.

    Approximates the unresolved-conversation backlog without a status
    history table. When `cutoff` is None, returns the current backlog
    (using ALL messages). When it's a timestamp, considers only messages
    sent at-or-before that point.
    """
    if cutoff is None:
        query = """
            SELECT COUNT(*) FROM (
                SELECT DISTINCT ON (m.conversation_id) m.direction
                FROM messages m
                ORDER BY m.conversation_id, m.sent_at DESC
            ) latest
            WHERE direction = 'inbound'
        """
        return int(await conn.fetchval(query) or 0)

    query = """
        SELECT COUNT(*) FROM (
            SELECT DISTINCT ON (m.conversation_id) m.direction
            FROM messages m
            WHERE m.sent_at <= $1
            ORDER BY m.conversation_id, m.sent_at DESC
        ) latest
        WHERE direction = 'inbound'
    """
    return int(await conn.fetchval(query, cutoff) or 0)


def _build_backlog_delta(
    current: int,
    previous: int,
    high_priority: int,
) -> KpiDelta | None:
    """Render the WoW delta pill for the 'Sin resolver' KPI.

    `previous` is the backlog 7d ago (same heuristic as current). When the
    change is small (< 3), defaults to surfacing the high-priority count
    (if any) so the card doesn't look empty.
    """
    change = current - previous
    if abs(change) >= 3:
        sign = "↑" if change > 0 else "↓"
        return KpiDelta(
            label=f"{sign} {abs(change)} vs semana previa",
            tone="warn" if change > 0 else "pos",
        )
    if high_priority > 0:
        return KpiDelta(label=f"{high_priority} altas activas", tone="warn")
    return None


async def _compute_tmr_minutes(
    conn: asyncpg.Connection,
    start: datetime,
    end: datetime,
) -> float | None:
    """Mean response time in minutes for outbound messages in [start, end).

    For each outbound message (agent/AI reply) in the window, looks up the
    most recent inbound message in the same conversation that came before
    it, and uses the time delta. Returns None when there are no qualifying
    outbound messages (degenerate case — show '—' in the UI).
    """
    row = await conn.fetchrow(
        """
        SELECT AVG(EXTRACT(EPOCH FROM (out_msg.sent_at - in_msg.sent_at)) / 60.0) AS mean_min,
               COUNT(*) AS n
        FROM messages out_msg
        JOIN LATERAL (
            SELECT m.sent_at
            FROM messages m
            WHERE m.conversation_id = out_msg.conversation_id
              AND m.direction = 'inbound'
              AND m.sent_at < out_msg.sent_at
            ORDER BY m.sent_at DESC
            LIMIT 1
        ) in_msg ON TRUE
        WHERE out_msg.direction = 'outbound'
          AND out_msg.sender_type IN ('agent', 'ai')
          AND out_msg.sent_at >= $1
          AND out_msg.sent_at <  $2
        """,
        start,
        end,
    )
    if row is None or row["n"] == 0 or row["mean_min"] is None:
        return None
    return float(row["mean_min"])


def _build_tmr_kpi(current: float | None, previous: float | None) -> OverviewKpi:
    """Render the TMR card from raw current/previous means.

    SLA target is < 30 min; tone is `pos` under target, `warn` over.
    Delta vs previous week: lower is better, so a drop is `pos`.
    """
    if current is None:
        return OverviewKpi(
            label="TMR · Kaizen",
            value="—",
            unit="min",
            sub="Sin respuestas en la ventana",
        )

    value = f"{int(round(current))}"
    sla_pos = current < 30
    delta: KpiDelta | None = None
    if previous is not None and previous > 0:
        change = current - previous
        if abs(change) >= 1:  # ignore sub-minute jitter
            sign = "−" if change < 0 else "+"
            delta = KpiDelta(
                label=f"{sign}{abs(int(round(change)))}m vs semana previa",
                tone="pos" if change < 0 else "warn",
            )

    if delta is None:
        delta = KpiDelta(label="SLA", tone="pos" if sla_pos else "warn")

    return OverviewKpi(
        label="TMR · Kaizen",
        value=value,
        unit="min",
        delta=delta,
        sub="objetivo < 30min",
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
