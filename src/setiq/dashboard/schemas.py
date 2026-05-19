from pydantic import BaseModel


class KpiDelta(BaseModel):
    label: str
    tone: str  # 'pos' | 'neg' | 'warn' | 'neutral'


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
    value: int          # message count


class OverviewResponse(BaseModel):
    kpis: list[OverviewKpi]
    channel_distribution: list[ChannelSlice]
    channel_total: int
    top_growth_channel: str | None = None
