from fastapi import APIRouter, Depends, HTTPException, status

from setiq import db
from setiq.auth.dependencies import CurrentUser, get_current_user
from setiq.auth.jwt import issue_token
from setiq.auth.passwords import verify_password
from setiq.auth.schemas import LoginRequest, TokenResponse, UserResponse

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

    token = issue_token(
        user_id=user_row["id"],
        tenant_id=membership["tenant_id"],
        role=membership["role"],
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser = Depends(get_current_user)) -> UserResponse:
    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, name FROM users WHERE id = $1 AND deleted_at IS NULL",
            current_user.user_id,
        )
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return UserResponse(
        id=row["id"],
        email=row["email"],
        name=row["name"],
        tenant_id=current_user.tenant_id,
        role=current_user.role,
    )
