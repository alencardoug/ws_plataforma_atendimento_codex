from datetime import date, datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OperatorUser(Base):
    __tablename__ = "operator_users"
    __table_args__ = {"schema": "customer_service"}
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = {"schema": "customer_service"}
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    channel: Mapped[str] = mapped_column(String, default="WEB")
    status: Mapped[str] = mapped_column(String, default="WAITING")
    anonymous_token_digest: Mapped[str] = mapped_column(Text, unique=True)
    initial_mode: Mapped[str] = mapped_column(String)
    effective_mode: Mapped[str] = mapped_column(String)
    taken_over_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_customer_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_customer_typing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auto_draft_covers_through_message_id: Mapped[UUID | None] = mapped_column(ForeignKey("customer_service.messages.id"))
    # AA-10: transient flow-position marker for booking_script/service.py.
    # NULL = no script in progress. Never holds the customer's CPF/payment answer.
    booking_script_step: Mapped[str | None] = mapped_column(Text)
    # 005/D-033: GB's own parallel transient staging fields — the already-
    # interpreted result of a raw CPF/payment reply (never the raw value
    # itself), set synchronously at message-creation time and consumed/
    # cleared by the next draft-generation call. Never read or written by
    # booking_script/*. See scheduling/guided_booking.py.
    guided_booking_pending_text: Mapped[str | None] = mapped_column(Text)
    guided_booking_pending_trigger: Mapped[str | None] = mapped_column(Text)


class ConversationAssignment(Base):
    __tablename__ = "conversation_assignments"
    __table_args__ = {"schema": "customer_service"}
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("customer_service.conversations.id"))
    operator_id: Mapped[UUID] = mapped_column(ForeignKey("customer_service.operator_users.id"))
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(Text)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = {"schema": "customer_service"}
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("customer_service.conversations.id"))
    author_type: Mapped[str] = mapped_column(String)
    operator_id: Mapped[UUID | None] = mapped_column(ForeignKey("customer_service.operator_users.id"))
    body: Mapped[str] = mapped_column(Text)
    source_generation_id: Mapped[UUID | None] = mapped_column(ForeignKey("customer_service.ai_generations.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    # AA-10: NULL for every message except the ones send_scripted_message()
    # creates, which get "booking_script" — Constitution Amendment 1.1.0's
    # containment is enforced structurally by this column, not just documented.
    autonomous_source: Mapped[str | None] = mapped_column(Text)


class Category(Base):
    """V3-8: formal registry shared by content.qa_entries.category (administrative
    topics) and content.documents.cancer_type (clinical site), replacing both
    columns' previously ungoverned free text. See plan.md §3.1 (resolved
    2026-08-18)."""

    __tablename__ = "categories"
    __table_args__ = {"schema": "content"}
    slug: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class KnowledgeDocument(Base):
    __tablename__ = "documents"
    __table_args__ = {"schema": "content"}
    document_id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    document_type: Mapped[str] = mapped_column(Text)
    cancer_type: Mapped[str | None] = mapped_column(ForeignKey("content.categories.slug"))
    care_phase: Mapped[str | None] = mapped_column(Text)
    procedure_slug: Mapped[str | None] = mapped_column(Text)
    audience: Mapped[list[str]] = mapped_column(ARRAY(Text))
    language: Mapped[str] = mapped_column(Text)
    responsible_physician: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[date] = mapped_column(Date)
    last_reviewed_at: Mapped[date] = mapped_column(Date)
    next_review_at: Mapped[date] = mapped_column(Date)
    patient_markdown_path: Mapped[str] = mapped_column(Text)
    content_markdown: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(Text)
    customer_citation_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    dynamic_data_required: Mapped[bool] = mapped_column(Boolean, default=False)
    dynamic_resolver: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class KnowledgeChunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("parent_document_id", "ordinal"), {"schema": "content"})
    chunk_id: Mapped[str] = mapped_column(Text, primary_key=True)
    parent_document_id: Mapped[str] = mapped_column(ForeignKey("content.documents.document_id"))
    ordinal: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str] = mapped_column(Text)
    content_markdown: Mapped[str] = mapped_column(Text)
    retrieval_intents: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    symptoms: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    urgency: Mapped[str] = mapped_column(Text, default="educativo")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    content_hash: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    embedding_provider: Mapped[str | None] = mapped_column(Text)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    embedding_dimension: Mapped[int | None] = mapped_column(Integer)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class QAEntry(Base):
    __tablename__ = "qa_entries"
    __table_args__ = {"schema": "content"}
    qa_id: Mapped[str] = mapped_column(Text, primary_key=True)
    category: Mapped[str] = mapped_column(ForeignKey("content.categories.slug"))
    question: Mapped[str] = mapped_column(Text)
    answer_markdown: Mapped[str] = mapped_column(Text)
    retrieval_intents: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    dynamic_data_required: Mapped[bool] = mapped_column(Boolean, default=False)
    dynamic_resolver: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    content_hash: Mapped[str | None] = mapped_column(Text)
    customer_citation_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    embedding_provider: Mapped[str | None] = mapped_column(Text)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    embedding_dimension: Mapped[int | None] = mapped_column(Integer)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class RetrievalRun(Base):
    __tablename__ = "retrieval_runs"
    __table_args__ = {"schema": "customer_service"}
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    conversation_id: Mapped[UUID | None] = mapped_column(ForeignKey("customer_service.conversations.id"))
    triggering_message_id: Mapped[UUID | None] = mapped_column(ForeignKey("customer_service.messages.id"))
    operator_id: Mapped[UUID] = mapped_column(ForeignKey("customer_service.operator_users.id"))
    purpose: Mapped[str] = mapped_column(String)
    query_text: Mapped[str] = mapped_column(Text)
    embedding_model: Mapped[str] = mapped_column(Text)
    top_k: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RetrievalHit(Base):
    __tablename__ = "retrieval_hits"
    __table_args__ = (UniqueConstraint("retrieval_run_id", "rank"), {"schema": "customer_service"})
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    retrieval_run_id: Mapped[UUID] = mapped_column(ForeignKey("customer_service.retrieval_runs.id"))
    matched_kind: Mapped[str] = mapped_column(String)
    matched_qa_id: Mapped[str | None] = mapped_column(ForeignKey("content.qa_entries.qa_id"))
    matched_chunk_id: Mapped[str | None] = mapped_column(ForeignKey("content.chunks.chunk_id"))
    expanded_parent_document_id: Mapped[str | None] = mapped_column(ForeignKey("content.documents.document_id"))
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class AIGeneration(Base):
    __tablename__ = "ai_generations"
    __table_args__ = {"schema": "customer_service"}
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("customer_service.conversations.id"))
    triggering_message_id: Mapped[UUID | None] = mapped_column(ForeignKey("customer_service.messages.id"))
    retrieval_run_id: Mapped[UUID] = mapped_column(ForeignKey("customer_service.retrieval_runs.id"))
    prior_generation_id: Mapped[UUID | None] = mapped_column(ForeignKey("customer_service.ai_generations.id"))
    operator_id: Mapped[UUID] = mapped_column(ForeignKey("customer_service.operator_users.id"))
    status: Mapped[str] = mapped_column(String)
    draft_text: Mapped[str] = mapped_column(Text)
    abstention_reason: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    trigger: Mapped[str] = mapped_column(String)
    manual_search_text: Mapped[str | None] = mapped_column(Text)
    dynamic_pattern_used: Mapped[bool] = mapped_column(Boolean, default=False)
    instruction_text: Mapped[str | None] = mapped_column(Text)
    category_slug: Mapped[str | None] = mapped_column(ForeignKey("content.categories.slug"))
    marked_incorrect_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    marked_incorrect_by_operator_id: Mapped[UUID | None] = mapped_column(ForeignKey("customer_service.operator_users.id"))
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    escalated_by_operator_id: Mapped[UUID | None] = mapped_column(ForeignKey("customer_service.operator_users.id"))


class MessageSelection(Base):
    __tablename__ = "message_selections"
    __table_args__ = (UniqueConstraint("ai_generation_id", "message_id"), {"schema": "customer_service"})
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    ai_generation_id: Mapped[UUID] = mapped_column(ForeignKey("customer_service.ai_generations.id"))
    message_id: Mapped[UUID] = mapped_column(ForeignKey("customer_service.messages.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class QADynamicBinding(Base):
    __tablename__ = "qa_dynamic_bindings"
    __table_args__ = {"schema": "content"}
    qa_id: Mapped[str] = mapped_column(ForeignKey("content.qa_entries.qa_id"), primary_key=True)
    source_table: Mapped[str] = mapped_column(Text)
    filter: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_columns: Mapped[list] = mapped_column(JSONB)
    row_limit: Mapped[int] = mapped_column(Integer, default=4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class DynamicFixtureRow(Base):
    """V2-6 mechanism-demonstration fixture only — proves the resolver/
    allowlist mechanism against a real table. Not a production dynamic-data
    source; no production Q&A entry is bound to it. A real source (e.g. for
    a future dynamic-appointment-availability feature) would be its own
    table, registered in knowledge/dynamic_binding.py's allowlist only when
    that separate feature is authorized (spec.md §6, ROADMAP.md)."""

    __tablename__ = "knowledge_dynamic_fixture"
    __table_args__ = {"schema": "content"}
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    category: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text)
    ordinal: Mapped[int] = mapped_column(Integer)


class AIGenerationSource(Base):
    __tablename__ = "ai_generation_sources"
    __table_args__ = (UniqueConstraint("ai_generation_id", "use_order"), {"schema": "customer_service"})
    ai_generation_id: Mapped[UUID] = mapped_column(ForeignKey("customer_service.ai_generations.id"), primary_key=True)
    retrieval_hit_id: Mapped[UUID] = mapped_column(ForeignKey("customer_service.retrieval_hits.id"), primary_key=True)
    use_order: Mapped[int] = mapped_column(Integer)


class AppointmentOfferPresentation(Base):
    """005 (GB-1): one row per offer shown to a customer by a resolved
    appointment_availability generation (up to 4). Append-only — never
    updated; a later resolution inserts a fresh set tied to its own new
    ai_generation_id. See specs/005-dynamic-pricing-and-guided-booking/
    data-model.md §1."""

    __tablename__ = "appointment_offer_presentations"
    __table_args__ = (UniqueConstraint("ai_generation_id", "display_order"), {"schema": "customer_service"})
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    ai_generation_id: Mapped[UUID] = mapped_column(ForeignKey("customer_service.ai_generations.id"))
    slot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("scheduling.schedule_slots.slot_id"))
    display_order: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class MessageCitation(Base):
    __tablename__ = "message_citations"
    __table_args__ = {"schema": "customer_service"}
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    message_id: Mapped[UUID] = mapped_column(ForeignKey("customer_service.messages.id"))
    knowledge_document_id: Mapped[str] = mapped_column(ForeignKey("content.documents.document_id"))
    knowledge_chunk_id: Mapped[str | None] = mapped_column(ForeignKey("content.chunks.chunk_id"))
    display_title: Mapped[str] = mapped_column(Text)
    display_section: Mapped[str | None] = mapped_column(Text)
    display_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class EvaluationCase(Base):
    """V3-5: durable, category-tagged evaluation case. Storage only — no
    automated re-run mechanism in V3 (spec.md §7); actual_status/actual_notes
    are set only by a reviewer's manual re-check. No FK path into
    conversations/ai_generations by design — isolation from production
    metrics is structural (plan.md §3.3)."""

    __tablename__ = "evaluation_cases"
    __table_args__ = {"schema": "content"}
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    category_slug: Mapped[str | None] = mapped_column(ForeignKey("content.categories.slug"))
    question: Mapped[str] = mapped_column(Text)
    expected_status: Mapped[str] = mapped_column(Text)
    expected_evidence_ids: Mapped[list | None] = mapped_column(JSONB)
    actual_status: Mapped[str | None] = mapped_column(Text)
    actual_notes: Mapped[str | None] = mapped_column(Text)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_operator_id: Mapped[UUID] = mapped_column(ForeignKey("customer_service.operator_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class ConversationSatisfactionResponse(Base):
    """V3-12: optional, customer-only, post-close satisfaction survey
    response. One row per conversation; a missing row means "skipped," never
    backfilled (plan.md §3.4)."""

    __tablename__ = "conversation_satisfaction_responses"
    __table_args__ = {"schema": "customer_service"}
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("customer_service.conversations.id"), unique=True)
    score: Mapped[int] = mapped_column(Integer)
    resolved: Mapped[bool] = mapped_column(Boolean)
    category_slug: Mapped[str | None] = mapped_column(ForeignKey("content.categories.slug"))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = {"schema": "customer_service"}
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    event_type: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    actor_type: Mapped[str] = mapped_column(String)
    actor_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    conversation_id: Mapped[UUID | None] = mapped_column(ForeignKey("customer_service.conversations.id"))
    correlation_id: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[dict] = mapped_column(JSONB, default=dict)
