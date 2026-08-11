from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select

from customer_care.anonymous_access.security import digest_conversation_token, issue_conversation_token
from customer_care.audit.service import record_event
from customer_care.conversations.projections import customer_projection
from customer_care.infrastructure.models import Conversation, Message
from customer_care.shared.dependencies import DbSession, customer_bearer
from customer_care.shared.errors import api_error
from customer_care.shared.schemas import BodyIn, ConversationOut, CreateConversationOut, CustomerMessageOut
from customer_care.shared.settings import get_settings

router = APIRouter(prefix="/public/conversations", tags=["Public Customer"])


def token_bound_conversation(
    conversation_id: UUID,
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(customer_bearer)],
) -> Conversation:
    if not credentials:
        raise api_error(401, "UNAUTHORIZED", "Conversation token required")
    digest = digest_conversation_token(credentials.credentials)
    conversation = session.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.anonymous_token_digest == digest))
    if not conversation:
        raise api_error(403, "FORBIDDEN", "Token is not valid for this conversation")
    return conversation


@router.post("", response_model=CreateConversationOut, status_code=201)
def create_conversation(session: DbSession, request: Request) -> dict:
    raw_token, digest = issue_conversation_token()
    mode = get_settings().global_maturity_mode
    with session.begin():
        conversation = Conversation(anonymous_token_digest=digest, initial_mode=mode, effective_mode=mode)
        session.add(conversation)
        session.flush()
        record_event(session, "conversation.created", "CUSTOMER", conversation_id=conversation.id, correlation_id=request.state.request_id, payload={"channel": "WEB"})
    return {"conversation": customer_projection(session, conversation), "access_token": raw_token}


@router.get("/{conversation_id}", response_model=ConversationOut)
def read_conversation(conversation: Annotated[Conversation, Depends(token_bound_conversation)], session: DbSession) -> dict:
    return customer_projection(session, conversation)


@router.post("/{conversation_id}", response_model=ConversationOut)
def close_conversation(conversation: Annotated[Conversation, Depends(token_bound_conversation)], session: DbSession, request: Request) -> dict:
    if conversation.status != "CLOSED":
        conversation.status = "CLOSED"
        conversation.closed_at = datetime.now(UTC)
        record_event(session, "conversation.closed", "CUSTOMER", conversation_id=conversation.id, correlation_id=request.state.request_id)
        session.commit()
    return customer_projection(session, conversation)


@router.post("/{conversation_id}/messages", response_model=CustomerMessageOut, status_code=201)
def send_customer_message(payload: BodyIn, conversation: Annotated[Conversation, Depends(token_bound_conversation)], session: DbSession, request: Request) -> Message:
    if conversation.status == "CLOSED":
        raise api_error(409, "CONVERSATION_CLOSED", "Conversation is closed")
    message = Message(conversation_id=conversation.id, author_type="CUSTOMER", body=payload.body)
    session.add(message)
    session.flush()
    conversation.last_message_at = message.created_at
    record_event(session, "message.customer_received", "CUSTOMER", conversation_id=conversation.id, correlation_id=request.state.request_id, payload={"message_id": str(message.id), "length": len(payload.body)})
    session.commit()
    session.refresh(message)
    return message
