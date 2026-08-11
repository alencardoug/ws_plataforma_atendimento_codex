from time import perf_counter
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from customer_care.ai.providers import GenerationResult, configured_generation_provider
from customer_care.ai.prompts import load_prompt
from customer_care.audit.service import record_event
from customer_care.conversations.projections import assigned_operator_id
from customer_care.infrastructure.models import AIGeneration, AIGenerationSource, Conversation, Message
from customer_care.rag.service import Evidence, evidence_dict, retrieve
from customer_care.shared.dependencies import CurrentOperator, DbSession
from customer_care.shared.errors import api_error

router = APIRouter(tags=["Operator AI"])


class DraftIn(BaseModel):
    triggering_message_id: UUID


def generation_dict(session: DbSession, generation: AIGeneration, evidence: list[dict]) -> dict:
    return {"id": generation.id, "conversation_id": generation.conversation_id, "triggering_message_id": generation.triggering_message_id, "prior_generation_id": generation.prior_generation_id, "status": generation.status, "draft_text": generation.draft_text, "reason_code": generation.abstention_reason, "evidence": evidence, "model": generation.model, "prompt_version": generation.prompt_version, "duration_ms": generation.duration_ms, "created_at": generation.created_at}


def full_parent_draft(evidence: list[Evidence]) -> GenerationResult | None:
    if not evidence or evidence[0].knowledge_type != "CLINICAL":
        return None
    parent = evidence[0]
    return GenerationResult("ANSWER", parent.content, None, [str(parent.retrieval_hit_id)])


def generate_draft(session: DbSession, operator_id: UUID, conversation: Conversation, triggering_message: Message, prior_generation_id: UUID | None = None) -> tuple[AIGeneration, list[dict]]:
    if conversation.status != "ACTIVE" or conversation.effective_mode != "N2":
        raise api_error(409, "MODE_NOT_ALLOWED", "Draft generation requires an active effective-N2 conversation")
    history_rows = session.scalars(select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.desc()).limit(20)).all()
    history = [{"role": row.author_type.lower(), "content": row.body} for row in reversed(history_rows)]
    run, evidence = retrieve(session, operator_id=operator_id, query=triggering_message.body, purpose="N2_DRAFT", top_k=8, conversation_id=conversation.id, triggering_message_id=triggering_message.id)
    started = perf_counter()
    prompt = load_prompt()
    prompt_version = prompt.version
    try:
        parent_result = full_parent_draft(evidence)
        if parent_result:
            result = parent_result
            provider_name = "clinical-parent-document"
            model = "not-applicable"
        else:
            provider = configured_generation_provider()
            qa_evidence = [item for item in evidence if item.knowledge_type == "ADMIN_QA"]
            result = provider.generate(history, qa_evidence, prompt.content)
            provider_name = provider.name
            model = provider.model
        generation = AIGeneration(conversation_id=conversation.id, triggering_message_id=triggering_message.id, retrieval_run_id=run.id, prior_generation_id=prior_generation_id, operator_id=operator_id, status=result.status, draft_text=result.draft_text, abstention_reason=result.reason_code, provider=provider_name, model=model, prompt_version=prompt_version, input_tokens=result.input_tokens, output_tokens=result.output_tokens, duration_ms=round((perf_counter() - started) * 1000))
        session.add(generation)
        session.flush()
        selected = {UUID(value) for value in result.used_hit_ids}
        for order, item in enumerate((item for item in evidence if item.retrieval_hit_id in selected), 1):
            session.add(AIGenerationSource(ai_generation_id=generation.id, retrieval_hit_id=item.retrieval_hit_id, use_order=order))
        event_type = "ai.draft_abstained" if result.status == "ABSTAIN" else "ai.draft_regenerated" if prior_generation_id else "ai.draft_generated"
        record_event(session, event_type, "OPERATOR", actor_id=operator_id, conversation_id=conversation.id, payload={"ai_generation_id": str(generation.id), "new_generation_id": str(generation.id) if prior_generation_id else None, "retrieval_run_id": str(run.id), "model": model, "duration_ms": generation.duration_ms, "prior_generation_id": str(prior_generation_id) if prior_generation_id else None, "reason_code": result.reason_code})
        session.commit()
        return generation, [evidence_dict(item) for item in evidence]
    except Exception as exc:
        generation = AIGeneration(conversation_id=conversation.id, triggering_message_id=triggering_message.id, retrieval_run_id=run.id, prior_generation_id=prior_generation_id, operator_id=operator_id, status="FAILED", draft_text="", abstention_reason="PROVIDER_FAILURE", provider="unavailable", model="unavailable", prompt_version=prompt_version, duration_ms=round((perf_counter() - started) * 1000))
        session.add(generation)
        session.commit()
        raise api_error(503, "AI_PROVIDER_UNAVAILABLE", "Draft generation failed; manual service remains available") from exc


@router.post("/operator/conversations/{conversation_id}/drafts", status_code=201)
def draft(conversation_id: UUID, payload: DraftIn, operator: CurrentOperator, session: DbSession) -> dict:
    conversation = session.get(Conversation, conversation_id)
    if not conversation or assigned_operator_id(session, conversation_id) != operator.id:
        raise api_error(403, "FORBIDDEN", "Conversation is not assigned to this operator")
    message = session.get(Message, payload.triggering_message_id)
    if not message or message.conversation_id != conversation.id or message.author_type != "CUSTOMER":
        raise api_error(409, "MESSAGE_NOT_ELIGIBLE", "Trigger must be a customer message from this conversation")
    generation, evidence = generate_draft(session, operator.id, conversation, message)
    return generation_dict(session, generation, evidence)


@router.post("/operator/drafts/{generation_id}/regenerate", status_code=201)
def regenerate(generation_id: UUID, operator: CurrentOperator, session: DbSession) -> dict:
    prior = session.get(AIGeneration, generation_id)
    if not prior:
        raise api_error(404, "NOT_FOUND", "Generation not found")
    conversation = session.get(Conversation, prior.conversation_id)
    if not conversation or assigned_operator_id(session, conversation.id) != operator.id:
        raise api_error(403, "FORBIDDEN", "Conversation is not assigned to this operator")
    message = session.get(Message, prior.triggering_message_id)
    assert message is not None
    generation, evidence = generate_draft(session, operator.id, conversation, message, prior_generation_id=prior.id)
    return generation_dict(session, generation, evidence)
