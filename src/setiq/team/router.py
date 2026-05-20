"""GET /team — members of the current tenant.

`tenant_users` and `users` are outside RLS (managed by the auth layer), so
this endpoint filters explicitly via `tu.tenant_id = current_tenant_id()`.
"""
import asyncpg
from fastapi import APIRouter, Depends

from setiq.auth.dependencies import get_tenant_db
from setiq.team.schemas import TeamMember, TeamResponse

router = APIRouter(prefix="/team", tags=["team"])


def _initials(name: str, email: str) -> str:
    """Two-character avatar initials."""
    parts = [p for p in (name or "").split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    if parts:
        return parts[0][:2].upper()
    if email:
        return email[:2].upper()
    return "··"


@router.get("", response_model=TeamResponse, response_model_exclude_none=True)
async def list_team(
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> TeamResponse:
    rows = await conn.fetch(
        """
        SELECT
            u.id, u.email, u.name, u.last_login_at, u.is_superadmin,
            tu.role, tu.created_at AS joined_at
        FROM tenant_users tu
        JOIN users u ON u.id = tu.user_id
        WHERE tu.tenant_id = current_tenant_id()
          AND u.deleted_at IS NULL
        ORDER BY tu.created_at
        """
    )
    members = [
        TeamMember(
            id=r["id"],
            email=r["email"],
            name=r["name"],
            role=r["role"],
            initials=_initials(r["name"], r["email"]),
            joined_at=r["joined_at"],
            last_login_at=r["last_login_at"],
            is_superadmin=r["is_superadmin"],
        )
        for r in rows
    ]
    counts: dict[str, int] = {}
    for m in members:
        counts[m.role] = counts.get(m.role, 0) + 1

    return TeamResponse(
        members=members,
        count_by_role=counts,
        total=len(members),
    )
