from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ConversationSummary(BaseModel):
    id: UUID
    contact_name: str | None = None
    contact_handle: str
    channel: str
    last_message_at: datetime | None = None
    last_message_preview: str | None = None
    message_count: int
    status: str
    subject: str | None = None
    sentiment: str | None = None
    intent: str | None = None
    priority: str | None = None
    # Set when the row represents an aggregated thread (group_by=thread) —
    # how many distinct contacts commented on the post.
    participant_count: int | None = None


class ConversationGroup(BaseModel):
    key: str
    label: str
    count: int
    conversations: list[ConversationSummary]


class ConversationsResponse(BaseModel):
    group_by: str
    total: int
    groups: list[ConversationGroup]


class MessageDetail(BaseModel):
    id: UUID
    direction: str
    sender_type: str
    content_type: str
    content_text: str | None = None
    sent_at: datetime
    sentiment: str | None = None
    intent: str | None = None
    # Per-message sender info (only meaningful when the detail spans
    # multiple contacts — i.e. when fetched as a thread).
    sender_name: str | None = None
    sender_handle: str | None = None


class ConversationDetail(BaseModel):
    id: UUID
    # For a single conversation: that contact. For a thread (as_thread=true):
    # a synthetic label like "Hilo · 5 personas".
    contact_name: str | None = None
    contact_handle: str
    channel: str
    status: str
    subject: str | None = None
    created_at: datetime
    last_message_at: datetime | None = None
    sentiment: str | None = None
    intent: str | None = None
    priority: str | None = None
    messages: list[MessageDetail]
    # Only set for thread detail.
    is_thread: bool = False
    participant_count: int | None = None
