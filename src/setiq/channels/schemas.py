from datetime import datetime

from pydantic import BaseModel


class ModuleToggles(BaseModel):
    setiq: bool
    kaizen: bool


class ChannelModulesPatch(BaseModel):
    setiq: bool | None = None
    kaizen: bool | None = None


class ChannelStatus(BaseModel):
    key: str           # 'instagram' | 'facebook' | 'tiktok' | 'email' | 'whatsapp' | 'phone'
    label: str         # 'Instagram'
    connected: bool
    account_label: str | None = None
    status: str        # 'active' | 'warning' | 'disconnected'
    last_sync_at: datetime | None = None
    modules: ModuleToggles
    warning: str | None = None


class ChannelsResponse(BaseModel):
    channels: list[ChannelStatus]
    connected_count: int
    warning_count: int
