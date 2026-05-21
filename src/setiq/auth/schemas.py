from typing import Any
from uuid import UUID

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str
    remember_me: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class TenantInfo(BaseModel):
    id: UUID
    slug: str
    name: str
    modules: dict[str, Any]


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    initials: str
    role: str
    tenant: TenantInfo
