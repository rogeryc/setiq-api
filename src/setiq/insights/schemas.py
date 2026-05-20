from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

InsightKind = Literal["lead", "featured", "memo"]


class InsightAction(BaseModel):
    label: str
    route: str | None = None
    variant: str | None = None


class Insight(BaseModel):
    """Unified shape that covers all insight kinds. Nullable fields are
    populated only for the kinds that use them — frontend renders
    differently per `kind`."""
    id: UUID
    kind: InsightKind
    severity: str | None = None  # memos: low / med / high
    tag: str | None = None        # memos: e.g. "Memo 02 · Oportunidad"
    title: str
    title_em: str | None = None
    title_tail: str | None = None  # featured only
    body: str
    confidence: str | None = None
    age: str | None = None         # featured only
    impact: str | None = None      # featured only
    footnote: str | None = None    # memos only
    actions: list[InsightAction] = []
    rank: int
    created_at: datetime


class InsightsResponse(BaseModel):
    insights: list[Insight]
    total: int
    counts: dict[str, int]  # { 'lead': 1, 'featured': 1, 'memo': 3 }
