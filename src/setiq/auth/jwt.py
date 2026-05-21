from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt

from setiq.config import settings


def issue_token(
    user_id: UUID,
    tenant_id: UUID,
    role: str,
    *,
    expires_in_minutes: int | None = None,
) -> str:
    ttl = expires_in_minutes if expires_in_minutes is not None else settings.jwt_expires_minutes
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
