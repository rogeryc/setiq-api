from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


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
