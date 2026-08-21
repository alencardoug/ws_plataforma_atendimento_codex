from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from customer_care.audit.service import record_event
from customer_care.infrastructure.models import KnowledgeChunk, KnowledgeDocument, QAEntry, RetrievalHit, RetrievalRun
from customer_care.knowledge.embeddings import DeterministicTestEmbeddingProvider, EmbeddingProvider, OpenAIEmbeddingProvider
from customer_care.shared.settings import get_settings


@dataclass(frozen=True)
class Evidence:
    retrieval_hit_id: UUID
    knowledge_type: str
    rank: int
    score: float
    title: str
    section: str | None
    content: str
    matched_child_excerpt: str | None
    customer_citation_allowed: bool


def configured_embedding_provider() -> EmbeddingProvider:
    return DeterministicTestEmbeddingProvider() if get_settings().ai_provider == "deterministic-test" else OpenAIEmbeddingProvider()


def retrieve(
    session: Session,
    *,
    operator_id: UUID | None,
    query: str,
    purpose: str,
    top_k: int,
    conversation_id: UUID | None = None,
    triggering_message_id: UUID | None = None,
) -> tuple[RetrievalRun, list[Evidence]]:
    provider = configured_embedding_provider()
    started = perf_counter()
    run = RetrievalRun(conversation_id=conversation_id, triggering_message_id=triggering_message_id, operator_id=operator_id, purpose=purpose, query_text=query, embedding_model=provider.model, top_k=top_k, status="STARTED")
    session.add(run)
    session.flush()
    record_event(session, "rag.search_started", "OPERATOR", actor_id=operator_id, conversation_id=conversation_id, payload={"retrieval_run_id": str(run.id), "trigger_message_id": str(triggering_message_id) if triggering_message_id else None})
    try:
        vector = provider.embed([query])[0]
        admin = session.execute(select(QAEntry, QAEntry.embedding.cosine_distance(vector).label("distance")).where(QAEntry.is_active.is_(True), QAEntry.embedding.is_not(None)).order_by("distance").limit(top_k)).all()
        clinical = session.execute(select(KnowledgeChunk, KnowledgeDocument, KnowledgeChunk.embedding.cosine_distance(vector).label("distance")).join(KnowledgeDocument, KnowledgeDocument.document_id == KnowledgeChunk.parent_document_id).where(KnowledgeChunk.is_active.is_(True), KnowledgeChunk.embedding.is_not(None)).order_by("distance").limit(top_k)).all()
        candidates = []
        for qa, distance in admin:
            candidates.append((float(distance), "ADMIN_QA", qa, None))
        for chunk, document, distance in clinical:
            candidates.append((float(distance), "CLINICAL_CHILD", chunk, document))
        candidates.sort(key=lambda item: item[0])
        evidence: list[Evidence] = []
        seen_parents: set[str] = set()
        for distance, kind, matched, parent in candidates:
            if len(evidence) >= top_k:
                break
            if kind == "CLINICAL_CHILD":
                assert parent is not None
                if parent.document_id in seen_parents:
                    continue
            hit = RetrievalHit(retrieval_run_id=run.id, matched_kind=kind, matched_qa_id=matched.qa_id if kind == "ADMIN_QA" else None, matched_chunk_id=matched.chunk_id if kind == "CLINICAL_CHILD" else None, expanded_parent_document_id=parent.document_id if parent else None, rank=len(evidence) + 1, score=1.0 - distance)
            session.add(hit)
            session.flush()
            if kind == "ADMIN_QA":
                item = Evidence(hit.id, "ADMIN_QA", hit.rank, hit.score, matched.question, None, matched.answer_markdown, None, False)
            else:
                assert parent is not None
                seen_parents.add(parent.document_id)
                item = Evidence(hit.id, "CLINICAL", hit.rank, hit.score, parent.title, matched.heading, parent.content_markdown or matched.content_markdown, matched.content_markdown, parent.customer_citation_allowed)
            evidence.append(item)
        run.status = "COMPLETED"
        run.duration_ms = round((perf_counter() - started) * 1000)
        run.completed_at = datetime.now(UTC)
        record_event(session, "rag.search_completed", "OPERATOR", actor_id=operator_id, conversation_id=conversation_id, payload={"retrieval_run_id": str(run.id), "hit_count": len(evidence), "duration_ms": run.duration_ms})
        return run, evidence
    except Exception as exc:
        run.status = "FAILED"
        run.error_code = type(exc).__name__
        run.completed_at = datetime.now(UTC)
        record_event(session, "rag.search_failed", "OPERATOR", actor_id=operator_id, conversation_id=conversation_id, payload={"retrieval_run_id": str(run.id), "error_class": type(exc).__name__})
        raise


def evidence_dict(item: Evidence) -> dict:
    return item.__dict__


def load_evidence(session: Session, retrieval_hit_id: UUID) -> Evidence | None:
    """Reconstruct the Evidence for an already-persisted RetrievalHit (V2-3)."""
    hit = session.get(RetrievalHit, retrieval_hit_id)
    if not hit:
        return None
    if hit.matched_kind == "ADMIN_QA":
        qa = session.get(QAEntry, hit.matched_qa_id) if hit.matched_qa_id else None
        if not qa:
            return None
        return Evidence(hit.id, "ADMIN_QA", hit.rank, hit.score, qa.question, None, qa.answer_markdown, None, False)
    chunk = session.get(KnowledgeChunk, hit.matched_chunk_id) if hit.matched_chunk_id else None
    parent = session.get(KnowledgeDocument, hit.expanded_parent_document_id) if hit.expanded_parent_document_id else None
    if not chunk or not parent:
        return None
    return Evidence(hit.id, "CLINICAL", hit.rank, hit.score, parent.title, chunk.heading, parent.content_markdown or chunk.content_markdown, chunk.content_markdown, parent.customer_citation_allowed)
