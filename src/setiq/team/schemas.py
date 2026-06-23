from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

Role = Literal["admin", "agent", "viewer"]


class TeamMember(BaseModel):
    id: UUID
    email: str
    name: str
    role: str           # 'admin' | 'agent' | 'viewer'
    initials: str
    joined_at: datetime
    last_login_at: datetime | None = None
    is_superadmin: bool = False


class TeamResponse(BaseModel):
    members: list[TeamMember]
    count_by_role: dict[str, int]
    total: int


class InviteRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    name: str | None = Field(default=None, max_length=120)
    role: Role = "agent"

    @field_validator("email")
    @classmethod
    def _basic_email_shape(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@", 1)[1]:
            raise ValueError("invalid email")
        return v


class InviteResponse(BaseModel):
    member: TeamMember
    # Returned ONLY when the user was newly created. The admin must share
    # it manually until Postmark/email is wired. null when the invitee
    # already had an account (got added to this tenant only).
    temp_password: str | None = None
    created_user: bool
