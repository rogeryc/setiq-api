from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

SubjectKind = Literal["competitor", "brand", "keyword", "hashtag"]


class TrackedSubjectCreate(BaseModel):
    kind: SubjectKind
    label: str = Field(..., min_length=1, max_length=200)
    handles: dict[str, str] = Field(default_factory=dict)
    keywords: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    enabled: bool = True


class TrackedSubjectUpdate(BaseModel):
    label: str | None = Field(None, min_length=1, max_length=200)
    handles: dict[str, str] | None = None
    keywords: list[str] | None = None
    hashtags: list[str] | None = None
    enabled: bool | None = None


class TrackedSubjectResponse(BaseModel):
    id: UUID
    kind: SubjectKind
    label: str
    handles: dict[str, str]
    keywords: list[str]
    hashtags: list[str]
    enabled: bool
    created_at: datetime
    updated_at: datetime
    # Number of mentions ingested for this subject (off-property mentions
    # from Apify / IG Business Discovery / etc.).
    mention_count: int = 0
    last_mention_at: datetime | None = None


class MentionPreview(BaseModel):
    id: UUID
    platform: str
    author_display_name: str | None = None
    author_handle: str | None = None
    content_text: str | None = None
    content_url: str | None = None
    published_at: datetime | None = None
    sentiment: str | None = None


class SentimentBreakdown(BaseModel):
    positive: int = 0
    neutral: int = 0
    negative: int = 0


class OverlapContact(BaseModel):
    id: UUID
    display_name: str | None = None


class TrackedSubjectDetail(BaseModel):
    id: UUID
    kind: SubjectKind
    label: str
    mention_count: int
    sentiment_breakdown: SentimentBreakdown
    recent_mentions: list[MentionPreview]
    audience_overlap: list[OverlapContact]
