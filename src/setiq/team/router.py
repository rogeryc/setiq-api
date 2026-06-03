"""GET /team — members of the current tenant.

`tenant_users` and `users` are outside RLS (managed by the auth layer), so
this endpoint filters explicitly via `tu.tenant_id = current_tenant_id()`.
"""
import secrets

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from setiq.auth.dependencies import CurrentUser, get_tenant_db, require_admin
from setiq.auth.passwords import hash_password
from setiq.team.schemas import (
    InviteRequest,
    InviteResponse,
    TeamMember,
    TeamResponse,
)

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


@router.post("/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def invite(
    body: InviteRequest,
    _admin: CurrentUser = Depends(require_admin),
    conn: asyncpg.Connection = Depends(get_tenant_db),
) -> InviteResponse:
    """Add a person to the current tenant.

    - If a user with this email already exists → just add the tenant_users
      row (or no-op if they're already a member). temp_password is null.
    - If no such user → create them with a random temp password and add
      the membership. temp_password is returned exactly once so the admin
      can share it manually (no email delivery yet).
    """
    email = body.email.lower()
    fallback_name = (body.name or email.split("@", 1)[0]).strip() or email
    temp_password: str | None = None
    created_user = False

    async with conn.transaction():
        existing = await conn.fetchrow(
            "SELECT id, name FROM users WHERE email = $1 AND deleted_at IS NULL",
            email,
        )
        if existing is None:
            temp_password = secrets.token_urlsafe(12)
            user_row = await conn.fetchrow(
                """
                INSERT INTO users (email, name, password_hash)
                VALUES ($1, $2, $3)
                RETURNING id, email, name, last_login_at, is_superadmin
                """,
                email,
                fallback_name,
                hash_password(temp_password),
            )
            created_user = True
        else:
            user_row = await conn.fetchrow(
                """
                SELECT id, email, name, last_login_at, is_superadmin
                FROM users WHERE id = $1
                """,
                existing["id"],
            )

        membership = await conn.fetchrow(
            """
            INSERT INTO tenant_users (tenant_id, user_id, role)
            VALUES (current_tenant_id(), $1, $2)
            ON CONFLICT (tenant_id, user_id) DO UPDATE SET role = EXCLUDED.role
            RETURNING role, created_at
            """,
            user_row["id"],
            body.role,
        )

    if user_row is None or membership is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Invite failed")

    member = TeamMember(
        id=user_row["id"],
        email=user_row["email"],
        name=user_row["name"],
        role=membership["role"],
        initials=_initials(user_row["name"], user_row["email"]),
        joined_at=membership["created_at"],
        last_login_at=user_row["last_login_at"],
        is_superadmin=user_row["is_superadmin"],
    )
    return InviteResponse(
        member=member,
        temp_password=temp_password,
        created_user=created_user,
    )
