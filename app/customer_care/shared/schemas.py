from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class CustomerMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    author_type: Literal["CUSTOMER"]
    body: str
    created_at: datetime


class CitationOut(BaseModel):
    title: str
    section: str | None = None
    url: str | None = None


class OperatorMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    author_type: Literal["OPERATOR"]
    body: str
    citations: list[CitationOut] = []
    created_at: datetime


class ConversationOut(BaseModel):
    id: UUID
    status: Literal["WAITING", "ACTIVE", "CLOSED"]
    messages: list[CustomerMessageOut | OperatorMessageOut]
    created_at: datetime
    closed_at: datetime | None = None
    # 008/CS-2: true only while an automatic-draft debounce window is open
    # for this conversation — never the seconds-remaining count itself
    # (CS-3). Composed only by read_conversation(); every other endpoint
    # returning ConversationOut keeps this default, which is already
    # correct for those cases (a just-created or just-closed conversation
    # is never mid-debounce).
    preparing_response: bool = False
    # 007/BS-6: a single rendered summary line once a booking flow has
    # completed for this conversation — session-only on the client (never
    # written to sessionStorage), computed fresh here on every read.
    booking_summary_line: str | None = None


class CreateConversationOut(BaseModel):
    conversation: ConversationOut
    access_token: str


class BodyIn(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


class OperatorLoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=1024)


class OperatorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    display_name: str


class OperatorLoginOut(BaseModel):
    access_token: str
    operator: OperatorOut


class ConversationSummaryOut(BaseModel):
    id: UUID
    status: str
    effective_mode: str
    created_at: datetime
    last_message_at: datetime | None
    unread_customer_messages: int = 0


class OperatorSendIn(BaseModel):
    body: str = Field(min_length=1, max_length=12000)
    source_generation_id: UUID | None = None
    citation_retrieval_hit_ids: list[UUID] = []
