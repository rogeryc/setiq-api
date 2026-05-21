from fastapi import APIRouter, Depends, HTTPException, status

from setiq import db
from setiq.auth.dependencies import CurrentUser, get_current_user
from setiq.auth.jwt import issue_token
from setiq.auth.passwords import verify_password
from setiq.auth.schemas import LoginRequest, TenantInfo, TokenResponse, UserResponse
from setiq.config import settings


def _initials(name: str | None, email: str) -> str:
    """Two-character avatar initials, same logic as team/router.py."""
    parts = [p for p in (name or "").split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    if parts:
        return parts[0][:2].upper()
    return email[:2].upper()

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest) -> TokenResponse:
    async with db.acquire() as conn:
        user_row = await conn.fetchrow(
            "SELECT id, password_hash FROM users "
            "WHERE email = $1 AND deleted_at IS NULL",
            req.email,
        )
        if user_row is None or not verify_password(req.password, user_row["password_hash"]):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

        membership = await conn.fetchrow(
            "SELECT tenant_id, role FROM tenant_users "
            "WHERE user_id = $1 ORDER BY created_at LIMIT 1",
            user_row["id"],
        )
    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User has no tenant access")

    ttl_minutes = (
        settings.jwt_remember_me_minutes if req.remember_me else settings.jwt_expires_minutes
    )
    token = issue_token(
        user_id=user_row["id"],
        tenant_id=membership["tenant_id"],
        role=membership["role"],
        expires_in_minutes=ttl_minutes,
    )
    return TokenResponse(access_token=token, expires_in_minutes=ttl_minutes)


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser = Depends(get_current_user)) -> UserResponse:
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.id, u.email, u.name,
                   t.id AS tenant_id, t.slug AS tenant_slug, t.name AS tenant_name,
                   t.modules AS tenant_modules
            FROM users u
            JOIN tenants t ON t.id = $2
            WHERE u.id = $1 AND u.deleted_at IS NULL
            """,
            current_user.user_id,
            current_user.tenant_id,
        )
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return UserResponse(
        id=row["id"],
        email=row["email"],
        name=row["name"],
        initials=_initials(row["name"], row["email"]),
        role=current_user.role,
        tenant=TenantInfo(
            id=row["tenant_id"],
            slug=row["tenant_slug"],
            name=row["tenant_name"],
            modules=row["tenant_modules"],
        ),
    )
