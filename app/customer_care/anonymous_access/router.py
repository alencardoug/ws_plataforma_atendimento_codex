from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select

from customer_care.ai.router import automatic_draft_status, evaluate_automatic_trigger
from customer_care.anonymous_access.rate_limit import enforce_not_locked_out, record_attempt
from customer_care.anonymous_access.security import digest_conversation_token, issue_conversation_token
from customer_care.audit.service import record_event
from customer_care.booking_script.service import advance_booking_script, persisted_customer_body
from customer_care.conversations.projections import customer_projection
from customer_care.infrastructure.models import AIGeneration, Conversation, ConversationSatisfactionResponse, Message
from customer_care.scheduling.availability import render_booking_summary_line
from customer_care.scheduling.guided_booking import advance_guided_booking
from customer_care.scheduling.guided_booking import persisted_customer_body as guided_persisted_customer_body
from customer_care.scheduling.models import AppointmentBooking
from customer_care.shared.dependencies import DbSession, customer_bearer
from customer_care.shared.errors import api_error
from customer_care.shared.http import client_ip
from customer_care.shared.schemas import BodyIn, ConversationOut, CreateConversationOut, CustomerMessageOut
from customer_care.shared.settings import get_settings

router = APIRouter(prefix="/public/conversations", tags=["Public Customer"])


def token_bound_conversation(
    conversation_id: UUID,
    session: DbSession,
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(customer_bearer)],
) -> Conversation:
    if not credentials:
        raise api_error(401, "UNAUTHORIZED", "Conversation token required")
    settings = get_settings()
    client_key = client_ip(request)
    try:
        enforce_not_locked_out("token_validation", client_key)
    except HTTPException:
        record_event(session, "anonymous_access.token_validation_rate_limited", "CUSTOMER", correlation_id=request.state.request_id)
        session.commit()
        raise
    digest = digest_conversation_token(credentials.credentials)
    conversation = session.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.anonymous_token_digest == digest))
    record_attempt(
        "token_validation",
        client_key,
        success=conversation is not None,
        max_failures=settings.anonymous_token_rate_limit_max_failures,
        window_seconds=settings.anonymous_token_rate_limit_window_seconds,
        base_lockout_seconds=settings.anonymous_token_rate_limit_base_lockout_seconds,
        max_lockout_seconds=settings.anonymous_token_rate_limit_max_lockout_seconds,
    )
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


def customer_draft_status(session: DbSession, conversation: Conversation) -> dict:
    """008/CS-1: reuses automatic_draft_status()'s existing eligibility
    computation verbatim — no duplicated logic, no new query. The countdown
    number itself (`_seconds_remaining`) is discarded here, before it ever
    reaches a response model, so it never crosses into any /public/*
    response (CS-3). No evaluate_automatic_trigger() call here by design
    (plan.md §2): this is a plain read of already-committed state, not a
    mutation, so no same-request ORM-freshness concern applies — adding one
    would make this GET side-effecting, a new trigger path spec.md never
    asked for."""
    eligible, _seconds_remaining = automatic_draft_status(session, conversation)
    return {"preparing_response": eligible}


def customer_booking_summary_fields(session: DbSession, conversation: Conversation) -> dict:
    """007/BS-6: computed fresh from `appointment_bookings` on every read
    — nothing written to `sessionStorage` or any other client store for
    this field; it becomes unreachable the moment the conversation itself
    does (spec.md §4/BS-6). Deliberately a separate function from the
    operator-side `booking_summary_fields()` (spec.md's own stated reason:
    keep this session-only promise structurally distinct), even though
    both read the same row."""
    booking = session.scalar(select(AppointmentBooking).where(AppointmentBooking.conversation_id == conversation.id).order_by(AppointmentBooking.recorded_at.desc()))
    return {"booking_summary_line": render_booking_summary_line(session, booking) if booking else None}


@router.get("/{conversation_id}", response_model=ConversationOut)
def read_conversation(conversation: Annotated[Conversation, Depends(token_bound_conversation)], session: DbSession) -> dict:
    return {**customer_projection(session, conversation), **customer_draft_status(session, conversation), **customer_booking_summary_fields(session, conversation)}


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
    # AA-10 parses CPF/payment replies only from the request-local value.
    # At those two script steps the durable message carries a fixed marker,
    # never the customer's raw input (spec.md outcome 13). 005/D-033: GB's
    # own parallel CPF/payment flow gets the same treatment — checked only
    # when AA-10 itself didn't already redact.
    durable_body = persisted_customer_body(conversation.booking_script_step, payload.body)
    if durable_body == payload.body:
        durable_body = guided_persisted_customer_body(session, conversation, payload.body)
    message = Message(conversation_id=conversation.id, author_type="CUSTOMER", body=durable_body)
    session.add(message)
    session.flush()
    conversation.last_message_at = message.created_at
    conversation.last_customer_activity_at = message.created_at
    record_event(
        session,
        "message.customer_received",
        "CUSTOMER",
        conversation_id=conversation.id,
        correlation_id=request.state.request_id,
        payload={"message_id": str(message.id), "length": len(durable_body)},
    )
    advance_booking_script(session, conversation, payload.body)  # AA-10 — raw input remains request-local; never calls an LLM
    advance_guided_booking(session, conversation, payload.body)  # 005/D-033 — same principle, GB's own parallel N2-draft flow; no-op if AA-10 just took over
    session.commit()
    session.refresh(message)
    return message


@router.post("/{conversation_id}/typing", status_code=204)
def typing_heartbeat(conversation: Annotated[Conversation, Depends(token_bound_conversation)], session: DbSession) -> None:
    """V2-7: customer-typing-activity heartbeat. Extends the 8-second
    automatic-draft debounce window and drives the operator's live
    "is typing" indicator. No request body; rate-limited via the same
    per-source token_bound_conversation dependency as every other
    /public/* route (plan.md §13.1) — a correct token here is always a
    success and never counts against the limiter, so legitimate frequent
    heartbeats are unaffected."""
    # Check using the *previous* activity timestamp before this heartbeat
    # resets it — otherwise the check below would always see "just now" and
    # never fire from within this same call.
    evaluate_automatic_trigger(session, conversation)
    now = datetime.now(UTC)
    conversation.last_customer_typing_at = now
    conversation.last_customer_activity_at = now
    session.commit()


class SubmitSatisfactionIn(BaseModel):
    score: int = Field(ge=1, le=5)
    resolved: bool


def satisfaction_dict(response: ConversationSatisfactionResponse) -> dict:
    return {"id": response.id, "conversation_id": response.conversation_id, "score": response.score, "resolved": response.resolved, "category_slug": response.category_slug, "submitted_at": response.submitted_at}


@router.post("/{conversation_id}/satisfaction", status_code=201)
def submit_satisfaction(payload: SubmitSatisfactionIn, conversation: Annotated[Conversation, Depends(token_bound_conversation)], session: DbSession, request: Request) -> dict:
    """V3-12: optional, non-blocking — the conversation already closed via
    close_conversation before this is ever called. Customer-only, no
    operator_id. category_slug is denormalized at submission time from the
    conversation's most recent ANSWER generation with a non-null
    category_slug (plan.md §3.1/§3.4); NULL if none exists."""
    if conversation.status != "CLOSED":
        raise api_error(409, "NOT_CLOSED", "Conversation must be closed before submitting a satisfaction response")
    existing = session.scalar(select(ConversationSatisfactionResponse).where(ConversationSatisfactionResponse.conversation_id == conversation.id))
    if existing:
        raise api_error(409, "ALREADY_SUBMITTED", "A satisfaction response already exists for this conversation")
    category_slug = session.scalar(select(AIGeneration.category_slug).where(AIGeneration.conversation_id == conversation.id, AIGeneration.status == "ANSWER", AIGeneration.category_slug.is_not(None)).order_by(AIGeneration.created_at.desc()))
    response = ConversationSatisfactionResponse(conversation_id=conversation.id, score=payload.score, resolved=payload.resolved, category_slug=category_slug)
    session.add(response)
    session.flush()
    record_event(session, "conversation.satisfaction_submitted", "CUSTOMER", conversation_id=conversation.id, correlation_id=request.state.request_id, payload={"score": payload.score, "resolved": payload.resolved, "category_slug": category_slug})
    session.commit()
    return satisfaction_dict(response)
