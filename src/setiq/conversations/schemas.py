from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ConversationUpdate(BaseModel):
    status: Literal[
        "open", "pending_agent", "waiting_customer", "resolved", "closed"
    ] | None = None
    assigned_user_id: UUID | None = None


class ConversationMutation(BaseModel):
    id: UUID
    status: str
    assigned_user_id: UUID | None = None


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


class ReplyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class ReplyResponse(BaseModel):
    """Returned by POST /conversations/{id}/reply when the Meta send succeeds.
    Contains the persisted outbound message + the Meta-side external id."""
    message: MessageDetail
    external_id: str | None = None


class DraftReplyResponse(BaseModel):
    """Returned by POST /conversations/{id}/draft-reply. NOT sent — this is a
    suggestion the agent edits in the composer before hitting Enviar."""
    text: str
    notes: str | None = None
    model: str


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
