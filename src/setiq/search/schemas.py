from uuid import UUID

from pydantic import BaseModel


class SearchHit(BaseModel):
    type: str
    id: UUID
    title: str
    subtitle: str | None = None


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]
