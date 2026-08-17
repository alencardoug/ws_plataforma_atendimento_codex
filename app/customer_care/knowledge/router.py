from datetime import UTC, date, datetime
from uuid import uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from customer_care.audit.service import record_event
from customer_care.infrastructure.models import KnowledgeChunk, KnowledgeDocument, QADynamicBinding, QAEntry
from customer_care.knowledge.dynamic_binding import ALLOWLISTED_TABLES
from customer_care.knowledge.ingest import apply_embedding, chunk_content_hash, needs_reembedding, qa_content_hash
from customer_care.rag.service import configured_embedding_provider
from customer_care.shared.dependencies import CurrentOperator, DbSession
from customer_care.shared.errors import api_error

router = APIRouter(prefix="/operator/knowledge", tags=["Operator Knowledge CRUD"])


class DynamicBindingIn(BaseModel):
    source_table: str
    filter: dict[str, str] = {}
    output_columns: list[dict[str, str]]
    row_limit: int = 4


class CreateQAIn(BaseModel):
    category: str
    question: str
    answer_markdown: str
    customer_citation_allowed: bool = False
    dynamic_binding: DynamicBindingIn | None = None


class UpdateQAIn(BaseModel):
    category: str | None = None
    question: str | None = None
    answer_markdown: str | None = None
    customer_citation_allowed: bool | None = None
    dynamic_binding: DynamicBindingIn | None = None


class CreateClinicalDocumentIn(BaseModel):
    title: str
    content_markdown: str
    version: str | None = None
    customer_citation_allowed: bool = True


class UpdateClinicalDocumentIn(BaseModel):
    title: str | None = None
    content_markdown: str | None = None
    version: str | None = None
    customer_citation_allowed: bool | None = None


class CreateClinicalChunkIn(BaseModel):
    ordinal: int
    content_markdown: str
    heading: str | None = None


class UpdateClinicalChunkIn(BaseModel):
    ordinal: int | None = None
    content_markdown: str | None = None
    heading: str | None = None


def qa_dict(session: DbSession, qa: QAEntry) -> dict:
    binding = session.get(QADynamicBinding, qa.qa_id)
    return {
        "qa_id": qa.qa_id,
        "category": qa.category,
        "question": qa.question,
        "answer_markdown": qa.answer_markdown,
        "customer_citation_allowed": qa.customer_citation_allowed,
        "is_active": qa.is_active,
        "dynamic_binding": {"source_table": binding.source_table, "filter": binding.filter, "output_columns": binding.output_columns, "row_limit": binding.row_limit} if binding else None,
        "created_at": qa.created_at,
        "updated_at": qa.updated_at,
    }


def document_dict(document: KnowledgeDocument) -> dict:
    return {
        "document_id": document.document_id,
        "title": document.title,
        "version": document.version,
        "content_markdown": document.content_markdown,
        "customer_citation_allowed": document.customer_citation_allowed,
        "is_active": document.is_active,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def chunk_dict(chunk: KnowledgeChunk) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "parent_document_id": chunk.parent_document_id,
        "ordinal": chunk.ordinal,
        "heading": chunk.heading,
        "content_markdown": chunk.content_markdown,
        "is_active": chunk.is_active,
        "created_at": chunk.created_at,
        "updated_at": chunk.updated_at,
    }


def validate_binding(binding_in: DynamicBindingIn) -> None:
    """Write-time mirror of dynamic_binding.py's resolution-time allowlist
    check (data-model.md §6): catches an operator's table/column typo at
    creation time with a 422, instead of only surfacing it later as a
    generic ABSTAIN fallback. Not itself a security boundary — the
    resolution-time check remains authoritative and is never skipped, since
    an allowlist entry could theoretically be removed after this check ran."""
    allowlisted = ALLOWLISTED_TABLES.get(binding_in.source_table)
    if not allowlisted:
        raise api_error(422, "INVALID_DYNAMIC_BINDING", f"source_table '{binding_in.source_table}' is not in the allowlist")
    model, _order_column = allowlisted
    for spec in binding_in.output_columns:
        if not hasattr(model, spec.get("column", "")):
            raise api_error(422, "INVALID_DYNAMIC_BINDING", f"column '{spec.get('column')}' not found in table '{binding_in.source_table}'")
    for key in binding_in.filter:
        if not hasattr(model, key):
            raise api_error(422, "INVALID_DYNAMIC_BINDING", f"filter column '{key}' not found in table '{binding_in.source_table}'")


def upsert_binding(session: DbSession, qa_id: str, binding_in: DynamicBindingIn | None) -> None:
    existing = session.get(QADynamicBinding, qa_id)
    if binding_in is None:
        if existing:
            session.delete(existing)
        return
    validate_binding(binding_in)
    if existing:
        existing.source_table = binding_in.source_table
        existing.filter = binding_in.filter
        existing.output_columns = binding_in.output_columns
        existing.row_limit = binding_in.row_limit
        existing.updated_at = datetime.now(UTC)
    else:
        session.add(QADynamicBinding(qa_id=qa_id, source_table=binding_in.source_table, filter=binding_in.filter, output_columns=binding_in.output_columns, row_limit=binding_in.row_limit))


# --- Q&A -----------------------------------------------------------------


@router.get("/qa")
def list_qa(operator: CurrentOperator, session: DbSession, include_inactive: bool = Query(False)) -> list[dict]:
    query = select(QAEntry) if include_inactive else select(QAEntry).where(QAEntry.is_active.is_(True))
    return [qa_dict(session, row) for row in session.scalars(query.order_by(QAEntry.qa_id)).all()]


@router.post("/qa", status_code=201)
def create_qa(payload: CreateQAIn, operator: CurrentOperator, session: DbSession) -> dict:
    qa_id = f"qa-{uuid4().hex[:12]}"
    qa = QAEntry(qa_id=qa_id, category=payload.category, question=payload.question, answer_markdown=payload.answer_markdown, retrieval_intents=[], dynamic_data_required=payload.dynamic_binding is not None, customer_citation_allowed=payload.customer_citation_allowed, is_active=True)
    session.add(qa)
    session.flush()
    upsert_binding(session, qa_id, payload.dynamic_binding)
    provider = configured_embedding_provider()
    content_hash = qa_content_hash(payload.question, payload.answer_markdown)
    apply_embedding(qa, provider, content_hash, provider.embed([f"{payload.question}\n{payload.answer_markdown}"])[0])
    record_event(session, "knowledge.qa_created", "OPERATOR", actor_id=operator.id, payload={"qa_id": qa_id})
    session.commit()
    return qa_dict(session, qa)


@router.get("/qa/{qa_id}")
def get_qa(qa_id: str, operator: CurrentOperator, session: DbSession) -> dict:
    qa = session.get(QAEntry, qa_id)
    if not qa:
        raise api_error(404, "NOT_FOUND", "Q&A entry not found")
    return qa_dict(session, qa)


@router.patch("/qa/{qa_id}")
def update_qa(qa_id: str, payload: UpdateQAIn, operator: CurrentOperator, session: DbSession) -> dict:
    qa = session.get(QAEntry, qa_id)
    if not qa:
        raise api_error(404, "NOT_FOUND", "Q&A entry not found")
    changes = payload.model_dump(exclude_unset=True)
    if "category" in changes:
        qa.category = changes["category"]
    if "question" in changes:
        qa.question = changes["question"]
    if "answer_markdown" in changes:
        qa.answer_markdown = changes["answer_markdown"]
    if "customer_citation_allowed" in changes:
        qa.customer_citation_allowed = changes["customer_citation_allowed"]
    if "dynamic_binding" in changes:
        upsert_binding(session, qa_id, payload.dynamic_binding)
        qa.dynamic_data_required = payload.dynamic_binding is not None
    qa.updated_at = datetime.now(UTC)
    provider = configured_embedding_provider()
    content_hash = qa_content_hash(qa.question, qa.answer_markdown)
    if needs_reembedding(qa, content_hash, provider):
        apply_embedding(qa, provider, content_hash, provider.embed([f"{qa.question}\n{qa.answer_markdown}"])[0])
    record_event(session, "knowledge.qa_updated", "OPERATOR", actor_id=operator.id, payload={"qa_id": qa_id})
    session.commit()
    return qa_dict(session, qa)


@router.delete("/qa/{qa_id}", status_code=204)
def deactivate_qa(qa_id: str, operator: CurrentOperator, session: DbSession) -> None:
    qa = session.get(QAEntry, qa_id)
    if not qa:
        raise api_error(404, "NOT_FOUND", "Q&A entry not found")
    qa.is_active = False
    qa.updated_at = datetime.now(UTC)
    record_event(session, "knowledge.qa_deactivated", "OPERATOR", actor_id=operator.id, payload={"qa_id": qa_id})
    session.commit()


# --- Clinical parent documents --------------------------------------------


@router.get("/clinical-documents")
def list_documents(operator: CurrentOperator, session: DbSession, include_inactive: bool = Query(False)) -> list[dict]:
    query = select(KnowledgeDocument) if include_inactive else select(KnowledgeDocument).where(KnowledgeDocument.is_active.is_(True))
    return [document_dict(row) for row in session.scalars(query.order_by(KnowledgeDocument.document_id)).all()]


@router.post("/clinical-documents", status_code=201)
def create_document(payload: CreateClinicalDocumentIn, operator: CurrentOperator, session: DbSession) -> dict:
    document_id = f"doc-{uuid4().hex[:12]}"
    today = date.today()
    document = KnowledgeDocument(
        document_id=document_id, title=payload.title, document_type="orientacao_clinica", audience=["paciente", "familiar"], language="pt-BR",
        responsible_physician="Não informado", version=payload.version or "1.0", status="published",
        created_at=today, last_reviewed_at=today, next_review_at=today,
        patient_markdown_path=f"crud:{document_id}", content_markdown=payload.content_markdown, content_hash=None,
        customer_citation_allowed=payload.customer_citation_allowed, is_active=True, dynamic_data_required=False, metadata_json={},
    )
    session.add(document)
    record_event(session, "knowledge.clinical_document_created", "OPERATOR", actor_id=operator.id, payload={"document_id": document_id})
    session.commit()
    return document_dict(document)


@router.get("/clinical-documents/{document_id}")
def get_document(document_id: str, operator: CurrentOperator, session: DbSession) -> dict:
    document = session.get(KnowledgeDocument, document_id)
    if not document:
        raise api_error(404, "NOT_FOUND", "Clinical document not found")
    return document_dict(document)


@router.patch("/clinical-documents/{document_id}")
def update_document(document_id: str, payload: UpdateClinicalDocumentIn, operator: CurrentOperator, session: DbSession) -> dict:
    document = session.get(KnowledgeDocument, document_id)
    if not document:
        raise api_error(404, "NOT_FOUND", "Clinical document not found")
    changes = payload.model_dump(exclude_unset=True)
    if "title" in changes:
        document.title = changes["title"]
    if "content_markdown" in changes:
        document.content_markdown = changes["content_markdown"]
    if "version" in changes:
        document.version = changes["version"]
    if "customer_citation_allowed" in changes:
        document.customer_citation_allowed = changes["customer_citation_allowed"]
    document.updated_at = datetime.now(UTC)
    record_event(session, "knowledge.clinical_document_updated", "OPERATOR", actor_id=operator.id, payload={"document_id": document_id})
    session.commit()
    return document_dict(document)


@router.delete("/clinical-documents/{document_id}", status_code=204)
def deactivate_document(document_id: str, operator: CurrentOperator, session: DbSession) -> None:
    document = session.get(KnowledgeDocument, document_id)
    if not document:
        raise api_error(404, "NOT_FOUND", "Clinical document not found")
    document.is_active = False
    document.updated_at = datetime.now(UTC)
    record_event(session, "knowledge.clinical_document_deactivated", "OPERATOR", actor_id=operator.id, payload={"document_id": document_id})
    session.commit()


# --- Clinical child chunks -------------------------------------------------


@router.get("/clinical-documents/{document_id}/chunks")
def list_chunks(document_id: str, operator: CurrentOperator, session: DbSession) -> list[dict]:
    if not session.get(KnowledgeDocument, document_id):
        raise api_error(404, "NOT_FOUND", "Clinical document not found")
    rows = session.scalars(select(KnowledgeChunk).where(KnowledgeChunk.parent_document_id == document_id).order_by(KnowledgeChunk.ordinal)).all()
    return [chunk_dict(row) for row in rows]


@router.post("/clinical-documents/{document_id}/chunks", status_code=201)
def create_chunk(document_id: str, payload: CreateClinicalChunkIn, operator: CurrentOperator, session: DbSession) -> dict:
    document = session.get(KnowledgeDocument, document_id)
    if not document:
        raise api_error(404, "NOT_FOUND", "Clinical document not found")
    chunk_id = f"{document_id}-C{payload.ordinal:02d}"
    if session.get(KnowledgeChunk, chunk_id):
        raise api_error(422, "ORDINAL_TAKEN", "A chunk with this ordinal already exists for this document; update it or choose another ordinal")
    heading = payload.heading or ""
    chunk = KnowledgeChunk(chunk_id=chunk_id, parent_document_id=document_id, ordinal=payload.ordinal, heading=heading, content_markdown=payload.content_markdown, retrieval_intents=[], symptoms=[], urgency="educativo", metadata_json={}, is_active=True)
    session.add(chunk)
    provider = configured_embedding_provider()
    content_hash = chunk_content_hash(heading, payload.content_markdown)
    apply_embedding(chunk, provider, content_hash, provider.embed([f"{heading}\n{payload.content_markdown}"])[0])
    record_event(session, "knowledge.clinical_chunk_created", "OPERATOR", actor_id=operator.id, payload={"document_id": document_id, "chunk_id": chunk_id})
    session.commit()
    return chunk_dict(chunk)


@router.patch("/clinical-documents/{document_id}/chunks/{chunk_id}")
def update_chunk(document_id: str, chunk_id: str, payload: UpdateClinicalChunkIn, operator: CurrentOperator, session: DbSession) -> dict:
    chunk = session.get(KnowledgeChunk, chunk_id)
    if not chunk or chunk.parent_document_id != document_id:
        raise api_error(404, "NOT_FOUND", "Clinical chunk not found")
    changes = payload.model_dump(exclude_unset=True)
    if "ordinal" in changes:
        chunk.ordinal = changes["ordinal"]
    if "heading" in changes:
        chunk.heading = changes["heading"] or ""
    if "content_markdown" in changes:
        chunk.content_markdown = changes["content_markdown"]
    chunk.updated_at = datetime.now(UTC)
    provider = configured_embedding_provider()
    content_hash = chunk_content_hash(chunk.heading, chunk.content_markdown)
    if needs_reembedding(chunk, content_hash, provider):
        apply_embedding(chunk, provider, content_hash, provider.embed([f"{chunk.heading}\n{chunk.content_markdown}"])[0])
    record_event(session, "knowledge.clinical_chunk_updated", "OPERATOR", actor_id=operator.id, payload={"document_id": document_id, "chunk_id": chunk_id})
    session.commit()
    return chunk_dict(chunk)


@router.delete("/clinical-documents/{document_id}/chunks/{chunk_id}", status_code=204)
def deactivate_chunk(document_id: str, chunk_id: str, operator: CurrentOperator, session: DbSession) -> None:
    chunk = session.get(KnowledgeChunk, chunk_id)
    if not chunk or chunk.parent_document_id != document_id:
        raise api_error(404, "NOT_FOUND", "Clinical chunk not found")
    chunk.is_active = False
    chunk.updated_at = datetime.now(UTC)
    record_event(session, "knowledge.clinical_chunk_deactivated", "OPERATOR", actor_id=operator.id, payload={"document_id": document_id, "chunk_id": chunk_id})
    session.commit()
