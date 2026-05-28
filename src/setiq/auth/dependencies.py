from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

import asyncpg
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from setiq import db
from setiq.auth import revocation
from setiq.auth.jwt import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    user_id: UUID
    tenant_id: UUID
    role: str
    jti: str
    exp: int
    remember: bool


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}") from e

    jti = payload.get("jti", "")
    if await revocation.is_revoked(jti):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token revoked")

    return CurrentUser(
        user_id=UUID(payload["sub"]),
        tenant_id=UUID(payload["tenant_id"]),
        role=payload["role"],
        jti=jti,
        exp=int(payload["exp"]),
        remember=bool(payload.get("remember", False)),
    )


async def get_tenant_db(
    current_user: CurrentUser = Depends(get_current_user),
) -> AsyncIterator[asyncpg.Connection]:
    """Yield a DB connection inside a transaction with the tenant context set.
    Any query through this connection is automatically tenant-scoped via RLS."""
    async with db.acquire_for_tenant(str(current_user.tenant_id)) as conn:
        yield conn


async def require_admin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    if current_user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return current_user
