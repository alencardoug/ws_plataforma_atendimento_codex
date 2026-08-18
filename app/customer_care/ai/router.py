from datetime import UTC, datetime, timedelta
from time import perf_counter
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from customer_care.ai.providers import GenerationResult, configured_generation_provider
from customer_care.ai.prompts import load_prompt
from customer_care.audit.service import record_event
from customer_care.conversations.projections import assigned_operator_id
from customer_care.infrastructure.models import AIGeneration, AIGenerationSource, Conversation, KnowledgeDocument, Message, MessageSelection, QAEntry, RetrievalHit
from customer_care.knowledge.dynamic_binding import DynamicResolutionError, resolve_dynamic_pattern
from customer_care.rag.service import Evidence, evidence_dict, load_evidence, retrieve
from customer_care.shared.dependencies import CurrentOperator, DbSession
from customer_care.shared.errors import api_error

router = APIRouter(tags=["Operator AI"])

# V2-7: fixed product behavior (spec.md), not an operator-tunable setting.
AUTOMATIC_TRIGGER_IDLE_SECONDS = 8


class DraftIn(BaseModel):
    selected_message_ids: list[UUID] = []
    manual_search_text: str = ""


class SelectEvidenceIn(BaseModel):
    conversation_id: UUID


def evidence_for_generation(session: DbSession, generation: AIGeneration) -> list[dict]:
    hit_ids = session.scalars(select(AIGenerationSource.retrieval_hit_id).where(AIGenerationSource.ai_generation_id == generation.id).order_by(AIGenerationSource.use_order)).all()
    items = [load_evidence(session, hit_id) for hit_id in hit_ids]
    return [evidence_dict(item) for item in items if item]


def latest_generation_dict(session: DbSession, conversation: Conversation) -> dict | None:
    """Surfaces the most recent non-FAILED generation for the operator UI —
    required so an AUTOMATIC-trigger draft (produced server-side, with no
    direct API response to the operator's browser) becomes visible via the
    next poll, not just generations the operator explicitly requested."""
    latest = session.scalar(select(AIGeneration).where(AIGeneration.conversation_id == conversation.id, AIGeneration.status != "FAILED").order_by(AIGeneration.created_at.desc()))
    if not latest:
        return None
    return generation_dict(session, latest, evidence_for_generation(session, latest))


def generation_dict(session: DbSession, generation: AIGeneration, evidence: list[dict], request_messages: list[dict[str, str]] | None = None) -> dict:
    """`request_messages` is only ever populated at generation-creation time
    (draft()/select_evidence(), operator-only response) — it is never
    persisted, so a later poll reloading this same generation via
    latest_generation_dict omits it. This is intentional: the operator
    debug pop-up (§ ad hoc request, 2026-08-18) reads it from the frontend's
    already-held response to the generating call, not from a later reload."""
    selected_message_ids = session.scalars(select(MessageSelection.message_id).where(MessageSelection.ai_generation_id == generation.id)).all()
    return {
        "id": generation.id,
        "conversation_id": generation.conversation_id,
        "triggering_message_id": generation.triggering_message_id,
        "prior_generation_id": generation.prior_generation_id,
        "trigger": generation.trigger,
        "dynamic_pattern_used": generation.dynamic_pattern_used,
        "status": generation.status,
        "draft_text": generation.draft_text,
        "reason_code": generation.abstention_reason,
        "evidence": evidence,
        "selected_message_ids": list(selected_message_ids),
        "model": generation.model,
        "prompt_version": generation.prompt_version,
        "duration_ms": generation.duration_ms,
        "created_at": generation.created_at,
        "request_messages": request_messages,
        "category_slug": generation.category_slug,
    }


def derive_category_slug(session: DbSession, generation: AIGeneration) -> str | None:
    """V3-1/V3-3/V3-4/V3-12 (plan.md §3.1, resolved 2026-08-18): category
    attribution for a completed ANSWER generation, from whichever evidence
    was actually used (use_order=1) — QAEntry.category for a Q&A-grounded
    answer, KnowledgeDocument.cancer_type for a clinical-parent-grounded
    one (both the same content.categories registry). NULL for ABSTAIN/
    FAILED and for evidence-free ANSWERs (e.g. a plain greeting) — callers
    must call this only after AIGenerationSource rows for `generation` are
    flushed."""
    if generation.status != "ANSWER":
        return None
    source = session.scalar(select(AIGenerationSource).where(AIGenerationSource.ai_generation_id == generation.id, AIGenerationSource.use_order == 1))
    if not source:
        return None
    hit = session.get(RetrievalHit, source.retrieval_hit_id)
    if not hit:
        return None
    if hit.matched_qa_id:
        qa = session.get(QAEntry, hit.matched_qa_id)
        return qa.category if qa else None
    if hit.expanded_parent_document_id:
        document = session.get(KnowledgeDocument, hit.expanded_parent_document_id)
        return document.cancer_type if document else None
    return None


def full_parent_draft(evidence: list[Evidence]) -> GenerationResult | None:
    if not evidence or evidence[0].knowledge_type != "CLINICAL":
        return None
    parent = evidence[0]
    return GenerationResult("ANSWER", parent.content, None, [str(parent.retrieval_hit_id)])


def dynamic_pattern_result(session: DbSession, evidence: list[Evidence]) -> tuple[GenerationResult, bool, str | None] | None:
    """V2-6: if the top evidence is an ADMIN_QA entry flagged
    dynamic_data_required, resolve it deterministically instead of an LLM
    call. Returns (result, dynamic_pattern_used, audit_only_failure_cause) —
    None means "not applicable, fall through to the normal LLM path".
    A configured-but-failing resolution and an unconfigured
    dynamic_data_required entry both fall back identically (spec.md V2-6
    §9.4): this is what finally retires the original V1 finding."""
    if not evidence or evidence[0].knowledge_type != "ADMIN_QA":
        return None
    hit = session.get(RetrievalHit, evidence[0].retrieval_hit_id)
    if not hit or not hit.matched_qa_id:
        return None
    qa = session.get(QAEntry, hit.matched_qa_id)
    if not qa or not qa.dynamic_data_required:
        return None
    try:
        resolution = resolve_dynamic_pattern(session, qa)
        return GenerationResult("ANSWER", resolution.pattern_text, None, [str(evidence[0].retrieval_hit_id)]), True, None
    except DynamicResolutionError as exc:
        return GenerationResult("ABSTAIN", "", "DYNAMIC_DATA_UNAVAILABLE", []), False, exc.cause


def generate_draft(
    session: DbSession,
    operator_id: UUID,
    conversation: Conversation,
    selected_messages: list[Message],
    manual_search_text: str,
    trigger: str = "MANUAL_DRAFT",
    prior_generation_id: UUID | None = None,
) -> tuple[AIGeneration, list[dict], list[dict[str, str]] | None]:
    if conversation.status != "ACTIVE" or conversation.effective_mode != "N2":
        raise api_error(409, "MODE_NOT_ALLOWED", "Draft generation requires an active effective-N2 conversation")
    history = [{"role": row.author_type.lower(), "content": row.body} for row in selected_messages]
    query = "\n".join([*(row.body for row in selected_messages), *([manual_search_text] if manual_search_text else [])])
    triggering_message_id = selected_messages[-1].id if selected_messages else None
    run, evidence = retrieve(session, operator_id=operator_id, query=query, purpose="N2_DRAFT", top_k=8, conversation_id=conversation.id, triggering_message_id=triggering_message_id)
    started = perf_counter()
    prompt = load_prompt()
    prompt_version = prompt.version
    try:
        dynamic_used = False
        dynamic_cause = None
        parent_result = full_parent_draft(evidence)
        if parent_result:
            result = parent_result
            provider_name = "clinical-parent-document"
            model = "not-applicable"
        else:
            dynamic = dynamic_pattern_result(session, evidence)
            if dynamic:
                result, dynamic_used, dynamic_cause = dynamic
                provider_name = "dynamic-pattern-resolver"
                model = "not-applicable"
            else:
                provider = configured_generation_provider()
                qa_evidence = [item for item in evidence if item.knowledge_type == "ADMIN_QA"]
                result = provider.generate(history, qa_evidence, prompt.content)
                provider_name = provider.name
                model = provider.model
        generation = AIGeneration(conversation_id=conversation.id, triggering_message_id=triggering_message_id, retrieval_run_id=run.id, prior_generation_id=prior_generation_id, operator_id=operator_id, status=result.status, draft_text=result.draft_text, abstention_reason=result.reason_code, provider=provider_name, model=model, prompt_version=prompt_version, input_tokens=result.input_tokens, output_tokens=result.output_tokens, duration_ms=round((perf_counter() - started) * 1000), trigger=trigger, manual_search_text=manual_search_text or None, dynamic_pattern_used=dynamic_used)
        session.add(generation)
        session.flush()
        for message in selected_messages:
            session.add(MessageSelection(ai_generation_id=generation.id, message_id=message.id))
        selected = {UUID(value) for value in result.used_hit_ids}
        for order, item in enumerate((item for item in evidence if item.retrieval_hit_id in selected), 1):
            session.add(AIGenerationSource(ai_generation_id=generation.id, retrieval_hit_id=item.retrieval_hit_id, use_order=order))
        session.flush()
        generation.category_slug = derive_category_slug(session, generation)
        event_type = "ai.draft_abstained" if result.status == "ABSTAIN" else "ai.draft_generated"
        record_event(session, event_type, "OPERATOR", actor_id=operator_id, conversation_id=conversation.id, payload={"ai_generation_id": str(generation.id), "retrieval_run_id": str(run.id), "model": model, "duration_ms": generation.duration_ms, "prior_generation_id": str(prior_generation_id) if prior_generation_id else None, "reason_code": result.reason_code, "trigger": trigger})
        if dynamic_cause is not None:
            record_event(session, "ai.dynamic_pattern_fallback", "OPERATOR", actor_id=operator_id, conversation_id=conversation.id, payload={"ai_generation_id": str(generation.id), "cause": dynamic_cause})
        elif dynamic_used:
            record_event(session, "ai.dynamic_pattern_resolved", "OPERATOR", actor_id=operator_id, conversation_id=conversation.id, payload={"ai_generation_id": str(generation.id)})
        session.commit()
        return generation, [evidence_dict(item) for item in evidence], result.request_messages
    except Exception as exc:
        generation = AIGeneration(conversation_id=conversation.id, triggering_message_id=triggering_message_id, retrieval_run_id=run.id, prior_generation_id=prior_generation_id, operator_id=operator_id, status="FAILED", draft_text="", abstention_reason="PROVIDER_FAILURE", provider="unavailable", model="unavailable", prompt_version=prompt_version, duration_ms=round((perf_counter() - started) * 1000), trigger=trigger)
        session.add(generation)
        session.commit()
        raise api_error(503, "AI_PROVIDER_UNAVAILABLE", "Draft generation failed; manual service remains available") from exc


@router.post("/operator/conversations/{conversation_id}/drafts", status_code=201)
def draft(conversation_id: UUID, payload: DraftIn, operator: CurrentOperator, session: DbSession) -> dict:
    conversation = session.get(Conversation, conversation_id)
    if not conversation or assigned_operator_id(session, conversation_id) != operator.id:
        raise api_error(403, "FORBIDDEN", "Conversation is not assigned to this operator")
    manual_search_text = payload.manual_search_text.strip()
    if not payload.selected_message_ids and not manual_search_text:
        raise api_error(422, "EMPTY_SELECTION", "Select at least one message or provide manual search text")
    selected_messages: list[Message] = []
    if payload.selected_message_ids:
        rows = session.scalars(select(Message).where(Message.id.in_(payload.selected_message_ids), Message.conversation_id == conversation.id)).all()
        found_ids = {row.id for row in rows}
        missing = set(payload.selected_message_ids) - found_ids
        if missing:
            raise api_error(422, "MESSAGE_NOT_IN_CONVERSATION", "One or more selected messages do not belong to this conversation")
        selected_messages = sorted(rows, key=lambda row: row.created_at)
    generation, evidence, request_messages = generate_draft(session, operator.id, conversation, selected_messages, manual_search_text)
    return generation_dict(session, generation, evidence, request_messages)


@router.post("/operator/knowledge/evidence/{retrieval_hit_id}/select", status_code=201)
def select_evidence(retrieval_hit_id: UUID, payload: SelectEvidenceIn, operator: CurrentOperator, session: DbSession) -> dict:
    """"Buscar evidências" (V2-3): a single selected retrieval hit deterministically
    becomes either the complete clinical parent document or an LLM-composed
    Q&A answer. Fully independent of message_selections (V2-4) — no
    conversation-message context is read or written here."""
    conversation = session.get(Conversation, payload.conversation_id)
    if not conversation or assigned_operator_id(session, conversation.id) != operator.id:
        raise api_error(403, "FORBIDDEN", "Conversation is not assigned to this operator")
    if conversation.status != "ACTIVE" or conversation.effective_mode != "N2":
        raise api_error(409, "MODE_NOT_ALLOWED", "Evidence selection requires an active effective-N2 conversation")
    hit = session.get(RetrievalHit, retrieval_hit_id)
    if not hit:
        raise api_error(404, "NOT_FOUND", "Retrieval hit not found")
    evidence = load_evidence(session, retrieval_hit_id)
    if not evidence:
        raise api_error(404, "NOT_FOUND", "Retrieval hit not found")
    started = perf_counter()
    prompt_version = "not-applicable"
    try:
        dynamic_used = False
        dynamic_cause = None
        parent_result = full_parent_draft([evidence])
        if parent_result:
            result = parent_result
            provider_name = "clinical-parent-document"
            model = "not-applicable"
        else:
            dynamic = dynamic_pattern_result(session, [evidence])
            if dynamic:
                result, dynamic_used, dynamic_cause = dynamic
                provider_name = "dynamic-pattern-resolver"
                model = "not-applicable"
            else:
                provider = configured_generation_provider()
                prompt = load_prompt()
                prompt_version = prompt.version
                # No message_selections context by design (V2-3); the latest
                # customer message, if any, gives the LLM a request to focus on.
                latest_customer = session.scalar(select(Message).where(Message.conversation_id == conversation.id, Message.author_type == "CUSTOMER").order_by(Message.created_at.desc()))
                history = [{"role": "customer", "content": latest_customer.body}] if latest_customer else []
                result = provider.generate(history, [evidence], prompt.content)
                provider_name = provider.name
                model = provider.model
        generation = AIGeneration(conversation_id=conversation.id, triggering_message_id=None, retrieval_run_id=hit.retrieval_run_id, operator_id=operator.id, status=result.status, draft_text=result.draft_text, abstention_reason=result.reason_code, provider=provider_name, model=model, prompt_version=prompt_version, input_tokens=result.input_tokens, output_tokens=result.output_tokens, duration_ms=round((perf_counter() - started) * 1000), trigger="MANUAL_EVIDENCE", dynamic_pattern_used=dynamic_used)
        session.add(generation)
        session.flush()
        session.add(AIGenerationSource(ai_generation_id=generation.id, retrieval_hit_id=hit.id, use_order=1))
        session.flush()
        generation.category_slug = derive_category_slug(session, generation)
        event_type = "ai.draft_abstained" if result.status == "ABSTAIN" else "ai.draft_generated"
        record_event(session, event_type, "OPERATOR", actor_id=operator.id, conversation_id=conversation.id, payload={"ai_generation_id": str(generation.id), "retrieval_run_id": str(hit.retrieval_run_id), "model": model, "duration_ms": generation.duration_ms, "reason_code": result.reason_code, "trigger": "MANUAL_EVIDENCE"})
        if dynamic_cause is not None:
            record_event(session, "ai.dynamic_pattern_fallback", "OPERATOR", actor_id=operator.id, conversation_id=conversation.id, payload={"ai_generation_id": str(generation.id), "cause": dynamic_cause})
        elif dynamic_used:
            record_event(session, "ai.dynamic_pattern_resolved", "OPERATOR", actor_id=operator.id, conversation_id=conversation.id, payload={"ai_generation_id": str(generation.id)})
        session.commit()
        return generation_dict(session, generation, [evidence_dict(evidence)], result.request_messages)
    except Exception as exc:
        generation = AIGeneration(conversation_id=conversation.id, triggering_message_id=None, retrieval_run_id=hit.retrieval_run_id, operator_id=operator.id, status="FAILED", draft_text="", abstention_reason="PROVIDER_FAILURE", provider="unavailable", model="unavailable", prompt_version=prompt_version, duration_ms=round((perf_counter() - started) * 1000), trigger="MANUAL_EVIDENCE")
        session.add(generation)
        session.commit()
        raise api_error(503, "AI_PROVIDER_UNAVAILABLE", "Evidence selection failed; manual service remains available") from exc


TYPING_GRACE_SECONDS = 5


def is_customer_typing(conversation: Conversation) -> bool:
    if not conversation.last_customer_typing_at:
        return False
    return datetime.now(UTC) - conversation.last_customer_typing_at < timedelta(seconds=TYPING_GRACE_SECONDS)


def evaluate_automatic_trigger(session: DbSession, conversation: Conversation) -> None:
    """V2-7 automatic/instant trigger: lazily evaluated as a side effect of the
    operator's conversation-detail poll and of the customer's typing heartbeat
    (plan.md §7.2) — no scheduler/background worker. Any generation failure is
    swallowed here (already persisted as a FAILED AIGeneration by
    generate_draft) so it never breaks the caller's own request."""
    if conversation.status != "ACTIVE" or conversation.effective_mode != "N2":
        return
    if not conversation.last_customer_activity_at:
        return
    if datetime.now(UTC) - conversation.last_customer_activity_at < timedelta(seconds=AUTOMATIC_TRIGGER_IDLE_SECONDS):
        return
    newest_customer = session.scalar(select(Message).where(Message.conversation_id == conversation.id, Message.author_type == "CUSTOMER").order_by(Message.created_at.desc()))
    if not newest_customer or newest_customer.id == conversation.auto_draft_covers_through_message_id:
        return
    operator_id = assigned_operator_id(session, conversation.id)
    if not operator_id:
        return
    history_rows = session.scalars(select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.desc())).all()
    selected_messages: list[Message] = []
    for row in history_rows:
        if row.author_type != "CUSTOMER":
            break
        selected_messages.append(row)
    selected_messages.reverse()
    # Mark this activity run covered before attempting generation, win or
    # lose — an unrecoverable provider failure must not retry on every poll.
    conversation.auto_draft_covers_through_message_id = newest_customer.id
    session.commit()
    try:
        generate_draft(session, operator_id, conversation, selected_messages, "", trigger="AUTOMATIC")
    except Exception:
        pass
