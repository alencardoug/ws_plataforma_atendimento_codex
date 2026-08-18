from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select, text

from customer_care.ai.router import evaluate_automatic_trigger, evidence_for_generation, generation_dict, is_customer_typing, latest_generation_dict
from customer_care.audit.service import record_event
from customer_care.conversations.projections import assigned_operator_id, customer_projection
from customer_care.infrastructure.models import (
    AIGeneration,
    Conversation,
    ConversationAssignment,
    Message,
    MessageCitation,
    RetrievalHit,
)
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


def summary(conversation: Conversation) -> dict:
    return {"id": conversation.id, "status": conversation.status, "effective_mode": conversation.effective_mode, "created_at": conversation.created_at, "last_message_at": conversation.last_message_at, "unread_customer_messages": 0}


@router.get("/runtime-config")
def runtime_config(operator: CurrentOperator) -> dict:
    settings = get_settings()
    return {"global_maturity_mode": settings.global_maturity_mode, "n1_assistive_search_enabled": settings.n1_assistive_search_enabled, "max_active_conversations": settings.operator_max_active_conversations}


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
    return [summary(row) for row in rows]


@router.get("/conversations/{conversation_id}")
def operator_conversation_detail(conversation_id: UUID, operator: CurrentOperator, session: DbSession) -> dict:
    conversation = require_assignment(session, conversation_id, operator.id)
    evaluate_automatic_trigger(session, conversation)
    return {**summary(conversation), **customer_projection(session, conversation, include_generation_id=True), "is_customer_typing": is_customer_typing(conversation), "latest_generation": latest_generation_dict(session, conversation)}


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
    return {**summary(conversation), **customer_projection(session, conversation, include_generation_id=True), "is_customer_typing": is_customer_typing(conversation), "latest_generation": latest_generation_dict(session, conversation)}


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
    return summary(conversation)


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
    return summary(conversation)


@router.post("/conversations/{conversation_id}/take-over")
def take_over(conversation_id: UUID, operator: CurrentOperator, session: DbSession, request: Request) -> dict:
    conversation = require_assignment(session, conversation_id, operator.id)
    if conversation.effective_mode != "N2" or conversation.status != "ACTIVE":
        raise api_error(409, "MODE_NOT_ALLOWED", "Take over requires an active N2 conversation")
    conversation.effective_mode = "N1"
    conversation.taken_over_at = datetime.now(UTC)
    record_event(session, "conversation.taken_over", "OPERATOR", actor_id=operator.id, conversation_id=conversation.id, correlation_id=request.state.request_id, payload={"from_mode": "N2", "to_mode": "N1"})
    session.commit()
    return {**summary(conversation), **customer_projection(session, conversation, include_generation_id=True), "is_customer_typing": is_customer_typing(conversation), "latest_generation": latest_generation_dict(session, conversation)}


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
    conversation.last_message_at = message.created_at
    session.commit()
    session.refresh(message)
    citations = session.scalars(select(MessageCitation).where(MessageCitation.message_id == message.id)).all()
    return {"id": message.id, "author_type": "OPERATOR", "body": message.body, "citations": [{"title": c.display_title, "section": c.display_section, "url": c.display_url} for c in citations], "created_at": message.created_at}


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
