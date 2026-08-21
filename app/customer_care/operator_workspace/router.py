from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select, text

from customer_care.ai.router import automatic_draft_status, evaluate_automatic_trigger, evaluate_unclaimed_autonomous_trigger, evidence_for_generation, generation_dict, is_customer_typing, latest_generation_dict
from customer_care.audit.service import record_event
from customer_care.autonomy.service import resolve_elapsed_autonomous_sends
from customer_care.conversations.projections import assigned_operator_id, customer_projection
from customer_care.infrastructure.models import (
    AIGeneration,
    Conversation,
    ConversationAssignment,
    Message,
    MessageCitation,
    PendingAutonomousSend,
    RetrievalHit,
    SystemSettings,
)
from customer_care.scheduling.availability import booking_summary_dict
from customer_care.scheduling.models import AppointmentBooking
from customer_care.shared.dependencies import CurrentOperator, DbSession
from customer_care.shared.errors import api_error
from customer_care.shared.schemas import ConversationSummaryOut, OperatorMessageOut, OperatorSendIn
from customer_care.shared.settings import get_settings

router = APIRouter(prefix="/operator", tags=["Operator"])


def require_assignment(session: DbSession, conversation_id: UUID, operator_id: UUID) -> Conversation:
    conversation = session.get(Conversation, conversation_id)
    if not conversation:
        raise api_error(404, "NOT_FOUND", "Conversation not found")
    if assigned_operator_id(session, conversation_id) != operator_id:
        raise api_error(403, "FORBIDDEN", "Conversation is not assigned to this operator")
    return conversation


def summary(conversation: Conversation, unread_by_conversation: dict[UUID, int] | None = None, pending_autonomous_send_by_conversation: dict[UUID, dict] | None = None) -> dict:
    unread = (unread_by_conversation or {}).get(conversation.id, 0)
    # 010, T20: category + resolves_at only, not the full draft text — kept
    # out of this list response for the same payload-size-on-a-2s-poll
    # reason automatic_draft_seconds_remaining already is.
    pending = (pending_autonomous_send_by_conversation or {}).get(conversation.id)
    return {"id": conversation.id, "status": conversation.status, "effective_mode": conversation.effective_mode, "created_at": conversation.created_at, "last_message_at": conversation.last_message_at, "unread_customer_messages": unread, "pending_autonomous_send": pending}


def pending_autonomous_send_summaries(session: DbSession, conversation_ids: list[UUID]) -> dict[UUID, dict]:
    """010, T20: batched (one query, not one per conversation) — matches
    unread_customer_message_counts()'s own established pattern for this
    2s-polled endpoint."""
    if not conversation_ids:
        return {}
    rows = session.scalars(select(PendingAutonomousSend).where(PendingAutonomousSend.conversation_id.in_(conversation_ids), PendingAutonomousSend.status == "PENDING")).all()
    return {row.conversation_id: {"id": row.id, "category": row.category, "resolves_at": row.resolves_at} for row in rows}


def unread_customer_message_counts(session: DbSession, conversation_ids: list[UUID]) -> dict[UUID, int]:
    """Trailing CUSTOMER messages sent after the conversation's own most recent
    OPERATOR message (or all CUSTOMER messages, if the operator has never
    replied) — i.e. how many of the customer's latest messages are still
    unanswered. Batched into one query per call site instead of per
    conversation, since this endpoint is polled every ~2s by every operator."""
    if not conversation_ids:
        return {}
    last_operator_message = (
        select(Message.conversation_id, func.max(Message.created_at).label("last_operator_at"))
        .where(Message.conversation_id.in_(conversation_ids), Message.author_type == "OPERATOR")
        .group_by(Message.conversation_id)
        .subquery()
    )
    rows = session.execute(
        select(Message.conversation_id, func.count())
        .select_from(Message)
        .outerjoin(last_operator_message, last_operator_message.c.conversation_id == Message.conversation_id)
        .where(
            Message.conversation_id.in_(conversation_ids),
            Message.author_type == "CUSTOMER",
            or_(last_operator_message.c.last_operator_at.is_(None), Message.created_at > last_operator_message.c.last_operator_at),
        )
        .group_by(Message.conversation_id)
    ).all()
    return {conversation_id: count for conversation_id, count in rows}


def automatic_draft_fields(session: DbSession, conversation: Conversation) -> dict:
    eligible, seconds_remaining = automatic_draft_status(session, conversation)
    return {"automatic_draft_eligible": eligible, "automatic_draft_seconds_remaining": seconds_remaining}


def booking_summary_fields(session: DbSession, conversation: Conversation) -> dict:
    """007/BS-5: the operator-facing computed field — read fresh from
    `appointment_bookings` each time, matching how `automatic_draft_fields()`
    is itself never persisted, just composed on top of `customer_projection()`."""
    booking = session.scalar(select(AppointmentBooking).where(AppointmentBooking.conversation_id == conversation.id).order_by(AppointmentBooking.recorded_at.desc()))
    return {"booking_summary": booking_summary_dict(session, booking) if booking else None}


def pending_autonomous_send_fields(session: DbSession, conversation: Conversation) -> dict:
    """010/GA-3, T19: the open (PENDING) autonomous-send window for this
    conversation, if any — read fresh each poll, matching
    automatic_draft_fields()/booking_summary_fields()'s own pattern.
    Draft text is read from the generation, not duplicated onto the row
    itself."""
    pending = session.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.conversation_id == conversation.id, PendingAutonomousSend.status == "PENDING").order_by(PendingAutonomousSend.created_at.desc()))
    if not pending:
        return {"pending_autonomous_send": None}
    generation = session.get(AIGeneration, pending.generation_id)
    return {"pending_autonomous_send": {"id": pending.id, "category": pending.category, "resolves_at": pending.resolves_at, "draft_text": generation.draft_text if generation else ""}}


@router.get("/runtime-config")
def runtime_config(operator: CurrentOperator) -> dict:
    settings = get_settings()
    return {"global_maturity_mode": settings.global_maturity_mode, "n1_assistive_search_enabled": settings.n1_assistive_search_enabled, "max_active_conversations": settings.operator_max_active_conversations}


def autonomy_settings_dict(settings: SystemSettings) -> dict:
    return {"window_seconds": settings.autonomy_window_seconds, "kill_switch_enabled": settings.autonomy_kill_switch_enabled, "updated_at": settings.updated_at}


def get_system_settings(session: DbSession) -> SystemSettings:
    """The migration that creates `system_settings` also seeds its one
    singleton row — a missing row here means that migration never ran,
    not a legitimate empty-settings state."""
    settings = session.get(SystemSettings, True)
    if not settings:
        raise api_error(500, "SETTINGS_MISSING", "system_settings singleton row is missing")
    return settings


@router.get("/autonomy-settings")
def get_autonomy_settings(operator: CurrentOperator, session: DbSession) -> dict:
    """010/GA-3, GA-5, T17."""
    return autonomy_settings_dict(get_system_settings(session))


class SetAutonomySettingsIn(BaseModel):
    window_seconds: int | None = None
    kill_switch_enabled: bool | None = None


@router.post("/autonomy-settings")
def set_autonomy_settings(payload: SetAutonomySettingsIn, operator: CurrentOperator, session: DbSession) -> dict:
    """010/GA-3, GA-5, T17. Either field may be omitted to change only the
    other. `window_seconds=0` is explicitly allowed (Constitution
    Amendment 1.2.0 clause (d) — immediate send)."""
    settings = get_system_settings(session)
    if payload.window_seconds is not None:
        if payload.window_seconds < 0:
            raise api_error(422, "INVALID_WINDOW", "window_seconds must be >= 0")
        before = settings.autonomy_window_seconds
        settings.autonomy_window_seconds = payload.window_seconds
        record_event(session, "autonomy.window_duration_changed", "OPERATOR", actor_id=operator.id, payload={"before_seconds": before, "after_seconds": payload.window_seconds})
    if payload.kill_switch_enabled is not None:
        before_switch = settings.autonomy_kill_switch_enabled
        settings.autonomy_kill_switch_enabled = payload.kill_switch_enabled
        record_event(session, "autonomy.kill_switch_toggled", "OPERATOR", actor_id=operator.id, payload={"before": before_switch, "after": payload.kill_switch_enabled})
    settings.updated_at = datetime.now(UTC)
    settings.updated_by_operator_id = operator.id
    session.commit()
    return autonomy_settings_dict(settings)


@router.get("/conversations", response_model=list[ConversationSummaryOut])
def list_conversations(
    operator: CurrentOperator,
    session: DbSession,
    scope: Literal["waiting", "active", "all"] = Query("all"),
) -> list[dict]:
    waiting = select(Conversation).where(Conversation.status == "WAITING")
    active = select(Conversation).join(ConversationAssignment, ConversationAssignment.conversation_id == Conversation.id).where(Conversation.status == "ACTIVE", ConversationAssignment.operator_id == operator.id, ConversationAssignment.released_at.is_(None))
    if scope == "waiting":
        rows = session.scalars(waiting.order_by(Conversation.last_message_at, Conversation.created_at)).all()
    elif scope == "active":
        rows = session.scalars(active.order_by(Conversation.last_message_at, Conversation.created_at)).all()
    else:
        rows = [*session.scalars(waiting).all(), *session.scalars(active).all()]
    # 010/GA-6: lazily evaluated per WAITING row, same no-scheduler
    # discipline as evaluate_automatic_trigger() itself — every logged-in
    # operator's own queue poll is what drives this, not a background
    # worker (plan.md §2.4).
    for row in rows:
        if row.status == "WAITING":
            evaluate_unclaimed_autonomous_trigger(session, row)
    resolve_elapsed_autonomous_sends(session)
    unread_by_conversation = unread_customer_message_counts(session, [row.id for row in rows])
    pending_by_conversation = pending_autonomous_send_summaries(session, [row.id for row in rows])
    return [summary(row, unread_by_conversation, pending_by_conversation) for row in rows]


@router.get("/conversations/{conversation_id}")
def operator_conversation_detail(conversation_id: UUID, operator: CurrentOperator, session: DbSession) -> dict:
    conversation = require_assignment(session, conversation_id, operator.id)
    evaluate_automatic_trigger(session, conversation)
    resolve_elapsed_autonomous_sends(session)
    return {**summary(conversation, unread_customer_message_counts(session, [conversation.id])), **customer_projection(session, conversation, include_generation_id=True), "is_customer_typing": is_customer_typing(conversation), "latest_generation": latest_generation_dict(session, conversation), **automatic_draft_fields(session, conversation), **booking_summary_fields(session, conversation), **pending_autonomous_send_fields(session, conversation)}


@router.post("/conversations/{conversation_id}/claim")
def claim(conversation_id: UUID, operator: CurrentOperator, session: DbSession, request: Request) -> dict:
    session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:operator_id, 0))"), {"operator_id": str(operator.id)})
    active_count = session.scalar(select(func.count()).select_from(ConversationAssignment).join(Conversation).where(ConversationAssignment.operator_id == operator.id, ConversationAssignment.released_at.is_(None), Conversation.status == "ACTIVE")) or 0
    if active_count >= get_settings().operator_max_active_conversations:
        session.rollback()
        raise api_error(409, "CAPACITY_EXCEEDED", "Operator active-conversation capacity reached")
    conversation = session.scalar(select(Conversation).where(Conversation.id == conversation_id).with_for_update())
    if not conversation or conversation.status != "WAITING" or assigned_operator_id(session, conversation_id):
        session.rollback()
        raise api_error(409, "NOT_CLAIMABLE", "Conversation is no longer claimable")
    assignment = ConversationAssignment(conversation_id=conversation.id, operator_id=operator.id)
    session.add(assignment)
    conversation.status = "ACTIVE"
    record_event(session, "conversation.claimed", "OPERATOR", actor_id=operator.id, conversation_id=conversation.id, correlation_id=request.state.request_id, payload={"active_count_after": active_count + 1})
    session.commit()
    return {**summary(conversation, unread_customer_message_counts(session, [conversation.id])), **customer_projection(session, conversation, include_generation_id=True), "is_customer_typing": is_customer_typing(conversation), "latest_generation": latest_generation_dict(session, conversation), **automatic_draft_fields(session, conversation), **booking_summary_fields(session, conversation), **pending_autonomous_send_fields(session, conversation)}


@router.post("/conversations/{conversation_id}/release", response_model=ConversationSummaryOut)
def release(conversation_id: UUID, operator: CurrentOperator, session: DbSession, request: Request) -> dict:
    conversation = require_assignment(session, conversation_id, operator.id)
    assignment = session.scalar(select(ConversationAssignment).where(ConversationAssignment.conversation_id == conversation.id, ConversationAssignment.operator_id == operator.id, ConversationAssignment.released_at.is_(None)))
    if not assignment or conversation.status != "ACTIVE":
        raise api_error(409, "NOT_ACTIVE", "Conversation is not active")
    assignment.released_at = datetime.now(UTC)
    assignment.release_reason = "RELEASED"
    conversation.status = "WAITING"
    record_event(session, "conversation.released", "OPERATOR", actor_id=operator.id, conversation_id=conversation.id, correlation_id=request.state.request_id)
    session.commit()
    return summary(conversation, unread_customer_message_counts(session, [conversation.id]))


@router.post("/conversations/{conversation_id}/close", response_model=ConversationSummaryOut)
def close(conversation_id: UUID, operator: CurrentOperator, session: DbSession, request: Request) -> dict:
    conversation = require_assignment(session, conversation_id, operator.id)
    assignment = session.scalar(select(ConversationAssignment).where(ConversationAssignment.conversation_id == conversation.id, ConversationAssignment.released_at.is_(None)))
    now = datetime.now(UTC)
    if assignment:
        assignment.released_at = now
        assignment.release_reason = "CLOSED"
    conversation.status = "CLOSED"
    conversation.closed_at = now
    record_event(session, "conversation.closed", "OPERATOR", actor_id=operator.id, conversation_id=conversation.id, correlation_id=request.state.request_id)
    session.commit()
    return summary(conversation, unread_customer_message_counts(session, [conversation.id]))


@router.post("/conversations/{conversation_id}/take-over")
def take_over(conversation_id: UUID, operator: CurrentOperator, session: DbSession, request: Request) -> dict:
    conversation = require_assignment(session, conversation_id, operator.id)
    if conversation.effective_mode != "N2" or conversation.status != "ACTIVE":
        raise api_error(409, "MODE_NOT_ALLOWED", "Take over requires an active N2 conversation")
    conversation.effective_mode = "N1"
    conversation.taken_over_at = datetime.now(UTC)
    # 010/GA-4, T15: TAKE OVER resolves any open autonomous-send window as
    # a side effect — no separate endpoint. The conversation is now N1, so
    # nothing would autonomously send for it again regardless, but the
    # row's own status should reflect why this particular draft never sent.
    pending = session.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.conversation_id == conversation.id, PendingAutonomousSend.status == "PENDING"))
    if pending:
        pending.status = "TAKEN_OVER"
        pending.resolved_at = datetime.now(UTC)
        pending.resolved_by_operator_id = operator.id
    record_event(session, "conversation.taken_over", "OPERATOR", actor_id=operator.id, conversation_id=conversation.id, correlation_id=request.state.request_id, payload={"from_mode": "N2", "to_mode": "N1"})
    session.commit()
    return {**summary(conversation, unread_customer_message_counts(session, [conversation.id])), **customer_projection(session, conversation, include_generation_id=True), "is_customer_typing": is_customer_typing(conversation), "latest_generation": latest_generation_dict(session, conversation), **automatic_draft_fields(session, conversation), **booking_summary_fields(session, conversation), **pending_autonomous_send_fields(session, conversation)}


@router.post("/conversations/{conversation_id}/messages", response_model=OperatorMessageOut, status_code=201)
def send_operator_message(conversation_id: UUID, payload: OperatorSendIn, operator: CurrentOperator, session: DbSession, request: Request) -> dict:
    conversation = require_assignment(session, conversation_id, operator.id)
    if conversation.status != "ACTIVE":
        raise api_error(409, "NOT_ACTIVE", "Conversation is not active")
    generation = None
    if payload.source_generation_id:
        generation = session.get(AIGeneration, payload.source_generation_id)
        if not generation or generation.conversation_id != conversation.id:
            raise api_error(422, "INVALID_GENERATION", "Generation does not belong to this conversation")
        # V3-2: protects every send-from-a-generation path (an edited
        # reply-box send and quick-approve alike) — not just quick-approve,
        # which adds no dedicated endpoint of its own (plan.md §5).
        latest_id = session.scalar(select(AIGeneration.id).where(AIGeneration.conversation_id == conversation.id, AIGeneration.status != "FAILED").order_by(AIGeneration.created_at.desc()))
        if generation.id != latest_id:
            raise api_error(409, "STALE_GENERATION", "A newer draft exists for this conversation; refresh before sending")
    validated = []
    for hit_id in payload.citation_retrieval_hit_ids:
        hit = session.get(RetrievalHit, hit_id)
        if not hit or hit.matched_kind != "CLINICAL_CHILD" or not hit.expanded_parent_document_id:
            raise api_error(422, "CITATION_NOT_EXPOSABLE", "Citation candidate is not an exposable clinical source")
        document = hit.expanded_parent_document_id
        allowed = session.scalar(text("SELECT customer_citation_allowed FROM content.documents WHERE document_id=:id"), {"id": document})
        if not allowed:
            raise api_error(422, "CITATION_NOT_EXPOSABLE", "Citation source is not customer exposable")
        validated.append(hit)
    message = Message(conversation_id=conversation.id, author_type="OPERATOR", operator_id=operator.id, body=payload.body, source_generation_id=payload.source_generation_id)
    session.add(message)
    session.flush()
    for hit in validated:
        row = session.execute(text("SELECT title FROM content.documents WHERE document_id=:id"), {"id": hit.expanded_parent_document_id}).mappings().one()
        section = session.scalar(text("SELECT heading FROM content.chunks WHERE chunk_id=:id"), {"id": hit.matched_chunk_id})
        session.add(MessageCitation(message_id=message.id, knowledge_document_id=hit.expanded_parent_document_id, knowledge_chunk_id=hit.matched_chunk_id, display_title=row["title"], display_section=section))
    edited = bool(generation and generation.draft_text != payload.body)
    if generation:
        record_event(session, "ai.draft_edited" if edited else "ai.draft_accepted", "OPERATOR", actor_id=operator.id, conversation_id=conversation.id, payload={"ai_generation_id": str(generation.id), "final_message_id": str(message.id)})
    record_event(session, "message.operator_sent", "OPERATOR", actor_id=operator.id, conversation_id=conversation.id, correlation_id=request.state.request_id, payload={"message_id": str(message.id), "source_generation_id": str(generation.id) if generation else None, "modified_from_draft": edited if generation else None})
    # 010/GA-4, T14: EDIT resolves any open autonomous-send window as a
    # side effect of an ordinary manual send — no separate "cancel" click
    # required first. Any PENDING row for this conversation, not just one
    # tied to `generation`, since an operator sending anything manually
    # while a window is open is unambiguously taking over that reply.
    pending = session.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.conversation_id == conversation.id, PendingAutonomousSend.status == "PENDING"))
    if pending:
        pending.status = "EDITED"
        pending.resolved_at = message.created_at
        pending.resolved_by_operator_id = operator.id
    conversation.last_message_at = message.created_at
    session.commit()
    session.refresh(message)
    citations = session.scalars(select(MessageCitation).where(MessageCitation.message_id == message.id)).all()
    return {"id": message.id, "author_type": "OPERATOR", "body": message.body, "citations": [{"title": c.display_title, "section": c.display_section, "url": c.display_url} for c in citations], "created_at": message.created_at}


@router.post("/conversations/{conversation_id}/pending-autonomous-send/{pending_id}/pause")
def pause_pending_autonomous_send(conversation_id: UUID, pending_id: UUID, operator: CurrentOperator, session: DbSession) -> dict:
    """010/GA-4, T13: cancels this one autonomous send; the draft becomes
    an ordinary N2 draft awaiting manual send. The category's own policy
    is unaffected — the next eligible message in it still opens its own
    window. Available to any authenticated operator, not only one who has
    claimed the conversation (GA-6 — an unclaimed conversation's pending
    send has no assigned operator to restrict this to)."""
    pending = session.get(PendingAutonomousSend, pending_id)
    if not pending or pending.conversation_id != conversation_id:
        raise api_error(404, "NOT_FOUND", "Pending autonomous send not found")
    if pending.status != "PENDING":
        raise api_error(409, "ALREADY_RESOLVED", f"Pending autonomous send already resolved as {pending.status}")
    pending.status = "PAUSED"
    pending.resolved_at = datetime.now(UTC)
    pending.resolved_by_operator_id = operator.id
    record_event(session, "autonomy.pending_send_paused", "OPERATOR", actor_id=operator.id, conversation_id=conversation_id, payload={"pending_autonomous_send_id": str(pending.id)})
    session.commit()
    return {"id": pending.id, "status": pending.status}


def require_generation(session: DbSession, conversation: Conversation, generation_id: UUID) -> AIGeneration:
    generation = session.get(AIGeneration, generation_id)
    if not generation:
        raise api_error(404, "NOT_FOUND", "Generation not found")
    if generation.conversation_id != conversation.id:
        raise api_error(422, "INVALID_GENERATION", "Generation does not belong to this conversation")
    return generation


@router.post("/conversations/{conversation_id}/generations/{generation_id}/mark-incorrect")
def mark_incorrect(conversation_id: UUID, generation_id: UUID, operator: CurrentOperator, session: DbSession, request: Request) -> dict:
    """V3-1: retroactive, reachable from any generation in the
    conversation's history, not only the latest. Idempotent — re-marking
    just updates the timestamp/actor."""
    conversation = require_assignment(session, conversation_id, operator.id)
    generation = require_generation(session, conversation, generation_id)
    generation.marked_incorrect_at = datetime.now(UTC)
    generation.marked_incorrect_by_operator_id = operator.id
    record_event(session, "generation.marked_incorrect", "OPERATOR", actor_id=operator.id, conversation_id=conversation.id, correlation_id=request.state.request_id, payload={"ai_generation_id": str(generation.id)})
    session.commit()
    return generation_dict(session, generation, evidence_for_generation(session, generation))


@router.post("/conversations/{conversation_id}/generations/{generation_id}/escalate")
def escalate(conversation_id: UUID, generation_id: UUID, operator: CurrentOperator, session: DbSession, request: Request) -> dict:
    """V3-1, redefined per spec.md: a content-gap signal ("the operator
    could not answer using what is already standardized") — not a routing/
    handoff request to a specialist (that remains V5's separate, unbuilt
    workflow). Tag only: no queue, no routing side effect."""
    conversation = require_assignment(session, conversation_id, operator.id)
    generation = require_generation(session, conversation, generation_id)
    generation.escalated_at = datetime.now(UTC)
    generation.escalated_by_operator_id = operator.id
    record_event(session, "generation.escalated", "OPERATOR", actor_id=operator.id, conversation_id=conversation.id, correlation_id=request.state.request_id, payload={"ai_generation_id": str(generation.id)})
    session.commit()
    return generation_dict(session, generation, evidence_for_generation(session, generation))
