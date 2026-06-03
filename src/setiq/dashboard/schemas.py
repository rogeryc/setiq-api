from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class KpiDelta(BaseModel):
    label: str
    tone: str  # 'pos' | 'neg' | 'warn' | 'neutral'


class CompetitorActivity(BaseModel):
    id: UUID
    label: str
    mentions: int
    previous: int
    delta: int
    sentiment_score: float | None = None


class CompetitorActivityResponse(BaseModel):
    period_days: int
    competitors: list[CompetitorActivity]
    generated_at: datetime


class OverviewKpi(BaseModel):
    label: str
    value: str
    unit: str | None = None
    delta: KpiDelta | None = None
    sub: str | None = None
    spark: list[float] | None = None
    spark_tone: str | None = None


class ChannelSlice(BaseModel):
    key: str            # 'instagram' | 'facebook' | 'tiktok' | 'email' | ...
    label: str          # 'Instagram'
    value: int


class InsightAction(BaseModel):
    label: str
    route: str | None = None
    variant: str | None = None  # 'acc' | 'ghost' | None


class LeadCopy(BaseModel):
    title: str
    title_em: str | None = None
    body: str


class FeaturedRecommendation(BaseModel):
    title: str
    title_em: str | None = None
    title_tail: str | None = None
    body: str
    confidence: str | None = None
    age: str | None = None
    impact: str | None = None
    actions: list[InsightAction] = []


class Memo(BaseModel):
    severity: str  # 'low' | 'med' | 'high'
    tag: str
    confidence: str | None = None
    title: str
    title_em: str | None = None
    body: str
    actions: list[InsightAction] = []
    footnote: str | None = None


class OverviewResponse(BaseModel):
    kpis: list[OverviewKpi]
    channel_distribution: list[ChannelSlice]
    channel_total: int
    top_growth_channel: str | None = None
    lead: LeadCopy | None = None
    featured_recommendation: FeaturedRecommendation | None = None
    memos: list[Memo] = []
    generated_at: datetime
