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
