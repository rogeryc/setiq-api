import asyncpg
from fastapi import APIRouter, Depends, Query

from setiq.auth.dependencies import get_tenant_db
from setiq.search.schemas import SearchHit, SearchResponse

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse, response_model_exclude_none=True)
async def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=20),
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> SearchResponse:
    term = q.strip()
    if not term:
        return SearchResponse(query=q, hits=[])

    hits: list[SearchHit] = []

    contacts = await conn.fetch(
        """
        SELECT id, display_name
        FROM contacts
        WHERE tenant_id = current_tenant_id() AND deleted_at IS NULL
          AND display_name ILIKE '%' || $1 || '%'
        ORDER BY last_seen_at DESC NULLS LAST
        LIMIT $2
        """,
        term, limit,
    )
    for r in contacts:
        hits.append(SearchHit(
            type="contact",
            id=r["id"],
            title=r["display_name"] or "Contacto",
            subtitle="Contacto",
        ))

    subjects = await conn.fetch(
        """
        SELECT id, label, kind
        FROM tracked_subjects
        WHERE tenant_id = current_tenant_id() AND deleted_at IS NULL
          AND (
            label ILIKE '%' || $1 || '%'
            OR EXISTS (SELECT 1 FROM unnest(keywords) k WHERE k ILIKE '%' || $1 || '%')
            OR EXISTS (SELECT 1 FROM unnest(hashtags) h WHERE h ILIKE '%' || $1 || '%')
          )
        ORDER BY label
        LIMIT $2
        """,
        term, limit,
    )
    for r in subjects:
        hits.append(SearchHit(
            type="tracked_subject",
            id=r["id"],
            title=r["label"],
            subtitle=r["kind"],
        ))

    conversations = await conn.fetch(
        """
        SELECT DISTINCT ON (c.id) c.id, ct.display_name, m.content_text
        FROM messages m
        JOIN conversations c ON c.id = m.conversation_id
        LEFT JOIN contacts ct ON ct.id = c.contact_id
        WHERE m.tenant_id = current_tenant_id()
          AND m.content_text ILIKE '%' || $1 || '%'
        ORDER BY c.id, m.sent_at DESC
        LIMIT $2
        """,
        term, limit,
    )
    for r in conversations:
        snippet = (r["content_text"] or "").strip()
        hits.append(SearchHit(
            type="conversation",
            id=r["id"],
            title=r["display_name"] or "Conversación",
            subtitle=snippet[:80] or None,
        ))

    return SearchResponse(query=q, hits=hits)
