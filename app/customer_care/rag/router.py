from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from customer_care.audit.service import record_event
from customer_care.conversations.projections import assigned_operator_id
from customer_care.infrastructure.models import Conversation
from customer_care.rag.service import evidence_dict, retrieve
from customer_care.shared.dependencies import CurrentOperator, DbSession
from customer_care.shared.errors import api_error
from customer_care.shared.settings import get_settings

router = APIRouter(prefix="/operator/knowledge", tags=["Operator AI"])


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None
    top_k: int = Field(default=8, ge=1, le=20)


@router.post("/search")
def search(payload: SearchIn, operator: CurrentOperator, session: DbSession) -> dict:
    purpose = "N2_MANUAL_SEARCH"
    if payload.conversation_id:
        conversation = session.get(Conversation, payload.conversation_id)
        if not conversation or assigned_operator_id(session, conversation.id) != operator.id:
            raise api_error(403, "FORBIDDEN", "Conversation is not assigned to this operator")
        if conversation.effective_mode == "N1":
            if not get_settings().n1_assistive_search_enabled:
                raise api_error(403, "N1_SEARCH_DISABLED", "N1 assistive search is disabled")
            purpose = "N1_MANUAL_SEARCH"
    elif get_settings().global_maturity_mode == "N1":
        if not get_settings().n1_assistive_search_enabled:
            raise api_error(403, "N1_SEARCH_DISABLED", "N1 assistive search is disabled")
        purpose = "N1_MANUAL_SEARCH"
    try:
        run, evidence = retrieve(session, operator_id=operator.id, query=payload.query, purpose=purpose, top_k=payload.top_k, conversation_id=payload.conversation_id)
        record_event(
            session,
            "knowledge.manual_search",
            "OPERATOR",
            actor_id=operator.id,
            conversation_id=payload.conversation_id,
            payload={"retrieval_run_id": str(run.id)},
        )
        session.commit()
    except Exception:
        session.commit()
        raise api_error(503, "RAG_UNAVAILABLE", "Knowledge retrieval is temporarily unavailable") from None
    return {"retrieval_run_id": run.id, "evidence": [evidence_dict(item) for item in evidence]}
