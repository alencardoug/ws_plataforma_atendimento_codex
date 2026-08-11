"""Adopt the content corpus and create Customer Care V1 tables.

Revision ID: 20260810_0001
Revises: None
"""

from alembic import op

revision = "20260810_0001"
down_revision = None
branch_labels = None
depends_on = None


DDL = r"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS content;
CREATE SCHEMA IF NOT EXISTS customer_service;

CREATE TABLE IF NOT EXISTS content.documents (
    document_id text PRIMARY KEY,
    title text NOT NULL,
    document_type text NOT NULL DEFAULT 'orientacao_clinica',
    cancer_type text,
    care_phase text,
    procedure_slug text,
    audience text[] NOT NULL DEFAULT ARRAY['paciente','familiar'],
    language text NOT NULL DEFAULT 'pt-BR',
    responsible_physician text NOT NULL DEFAULT 'Não informado',
    version text NOT NULL,
    status text NOT NULL DEFAULT 'published',
    created_at date NOT NULL DEFAULT CURRENT_DATE,
    last_reviewed_at date NOT NULL DEFAULT CURRENT_DATE,
    next_review_at date NOT NULL DEFAULT CURRENT_DATE,
    patient_markdown_path text NOT NULL,
    dynamic_data_required boolean NOT NULL DEFAULT false,
    dynamic_resolver text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
ALTER TABLE content.documents ADD COLUMN IF NOT EXISTS content_markdown text;
ALTER TABLE content.documents ADD COLUMN IF NOT EXISTS content_hash text;
ALTER TABLE content.documents ADD COLUMN IF NOT EXISTS customer_citation_allowed boolean NOT NULL DEFAULT true;
ALTER TABLE content.documents ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
ALTER TABLE content.documents ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

CREATE TABLE IF NOT EXISTS content.chunks (
    chunk_id text PRIMARY KEY,
    parent_document_id text NOT NULL REFERENCES content.documents(document_id) ON DELETE CASCADE,
    ordinal integer NOT NULL CHECK (ordinal > 0),
    heading text NOT NULL,
    content_markdown text NOT NULL,
    retrieval_intents text[] NOT NULL DEFAULT '{}',
    symptoms text[] NOT NULL DEFAULT '{}',
    urgency text NOT NULL DEFAULT 'educativo',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1536),
    UNIQUE(parent_document_id, ordinal)
);
ALTER TABLE content.chunks ADD COLUMN IF NOT EXISTS content_hash text;
ALTER TABLE content.chunks ADD COLUMN IF NOT EXISTS embedding_provider text;
ALTER TABLE content.chunks ADD COLUMN IF NOT EXISTS embedding_model text;
ALTER TABLE content.chunks ADD COLUMN IF NOT EXISTS embedding_dimension integer;
ALTER TABLE content.chunks ADD COLUMN IF NOT EXISTS embedded_at timestamptz;
ALTER TABLE content.chunks ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
ALTER TABLE content.chunks ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE content.chunks ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx ON content.chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS content.qa_entries (
    qa_id text PRIMARY KEY,
    category text NOT NULL,
    question text NOT NULL,
    answer_markdown text NOT NULL,
    retrieval_intents text[] NOT NULL DEFAULT '{}',
    dynamic_data_required boolean NOT NULL DEFAULT false,
    dynamic_resolver text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1536)
);
ALTER TABLE content.qa_entries ADD COLUMN IF NOT EXISTS content_hash text;
ALTER TABLE content.qa_entries ADD COLUMN IF NOT EXISTS customer_citation_allowed boolean NOT NULL DEFAULT false;
ALTER TABLE content.qa_entries ADD COLUMN IF NOT EXISTS embedding_provider text;
ALTER TABLE content.qa_entries ADD COLUMN IF NOT EXISTS embedding_model text;
ALTER TABLE content.qa_entries ADD COLUMN IF NOT EXISTS embedding_dimension integer;
ALTER TABLE content.qa_entries ADD COLUMN IF NOT EXISTS embedded_at timestamptz;
ALTER TABLE content.qa_entries ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
ALTER TABLE content.qa_entries ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE content.qa_entries ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();
CREATE INDEX IF NOT EXISTS qa_embedding_hnsw_idx ON content.qa_entries USING hnsw (embedding vector_cosine_ops);

CREATE TABLE customer_service.operator_users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), email text NOT NULL UNIQUE,
    password_hash text NOT NULL, display_name text NOT NULL, is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE customer_service.conversations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), channel text NOT NULL DEFAULT 'WEB' CHECK(channel='WEB'),
    status text NOT NULL DEFAULT 'WAITING' CHECK(status IN ('WAITING','ACTIVE','CLOSED')),
    anonymous_token_digest text NOT NULL UNIQUE, initial_mode text NOT NULL CHECK(initial_mode IN ('N1','N2')),
    effective_mode text NOT NULL CHECK(effective_mode IN ('N1','N2')), taken_over_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(), closed_at timestamptz, last_message_at timestamptz
);
CREATE INDEX conversations_queue_idx ON customer_service.conversations(status, last_message_at, created_at);
CREATE TABLE customer_service.conversation_assignments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), conversation_id uuid NOT NULL REFERENCES customer_service.conversations(id),
    operator_id uuid NOT NULL REFERENCES customer_service.operator_users(id), claimed_at timestamptz NOT NULL DEFAULT now(),
    released_at timestamptz, release_reason text
);
CREATE UNIQUE INDEX one_active_assignment_per_conversation ON customer_service.conversation_assignments(conversation_id) WHERE released_at IS NULL;
CREATE INDEX active_assignments_by_operator ON customer_service.conversation_assignments(operator_id) WHERE released_at IS NULL;
CREATE TABLE customer_service.messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), conversation_id uuid NOT NULL REFERENCES customer_service.conversations(id),
    author_type text NOT NULL CHECK(author_type IN ('CUSTOMER','OPERATOR')), operator_id uuid REFERENCES customer_service.operator_users(id),
    body text NOT NULL CHECK(length(body)>0), source_generation_id uuid, created_at timestamptz NOT NULL DEFAULT now(),
    CHECK((author_type='CUSTOMER' AND operator_id IS NULL) OR (author_type='OPERATOR' AND operator_id IS NOT NULL))
);
CREATE TABLE customer_service.retrieval_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), conversation_id uuid REFERENCES customer_service.conversations(id),
    triggering_message_id uuid REFERENCES customer_service.messages(id), operator_id uuid NOT NULL REFERENCES customer_service.operator_users(id),
    purpose text NOT NULL CHECK(purpose IN ('N2_DRAFT','N1_MANUAL_SEARCH','N2_MANUAL_SEARCH')), query_text text NOT NULL,
    embedding_model text NOT NULL, top_k integer NOT NULL CHECK(top_k>0), status text NOT NULL CHECK(status IN ('STARTED','COMPLETED','FAILED')),
    duration_ms integer, error_code text, created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz
);
CREATE TABLE customer_service.retrieval_hits (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), retrieval_run_id uuid NOT NULL REFERENCES customer_service.retrieval_runs(id),
    matched_kind text NOT NULL CHECK(matched_kind IN ('ADMIN_QA','CLINICAL_CHILD')), matched_qa_id text REFERENCES content.qa_entries(qa_id),
    matched_chunk_id text REFERENCES content.chunks(chunk_id), expanded_parent_document_id text REFERENCES content.documents(document_id),
    rank integer NOT NULL CHECK(rank>0), score double precision NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(retrieval_run_id, rank),
    CHECK((matched_kind='ADMIN_QA' AND matched_qa_id IS NOT NULL AND matched_chunk_id IS NULL AND expanded_parent_document_id IS NULL)
       OR (matched_kind='CLINICAL_CHILD' AND matched_qa_id IS NULL AND matched_chunk_id IS NOT NULL AND expanded_parent_document_id IS NOT NULL))
);
CREATE TABLE customer_service.ai_generations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), conversation_id uuid NOT NULL REFERENCES customer_service.conversations(id),
    triggering_message_id uuid NOT NULL REFERENCES customer_service.messages(id), retrieval_run_id uuid NOT NULL REFERENCES customer_service.retrieval_runs(id),
    prior_generation_id uuid REFERENCES customer_service.ai_generations(id), operator_id uuid NOT NULL REFERENCES customer_service.operator_users(id),
    status text NOT NULL CHECK(status IN ('ANSWER','ABSTAIN','FAILED')), draft_text text NOT NULL, abstention_reason text,
    provider text NOT NULL, model text NOT NULL, prompt_version text NOT NULL, input_tokens integer, output_tokens integer,
    duration_ms integer, created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE customer_service.messages ADD CONSTRAINT messages_source_generation_fk FOREIGN KEY(source_generation_id) REFERENCES customer_service.ai_generations(id);
CREATE TABLE customer_service.ai_generation_sources (
    ai_generation_id uuid NOT NULL REFERENCES customer_service.ai_generations(id), retrieval_hit_id uuid NOT NULL REFERENCES customer_service.retrieval_hits(id),
    use_order integer NOT NULL, PRIMARY KEY(ai_generation_id, retrieval_hit_id), UNIQUE(ai_generation_id, use_order)
);
CREATE TABLE customer_service.message_citations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), message_id uuid NOT NULL REFERENCES customer_service.messages(id),
    knowledge_document_id text NOT NULL REFERENCES content.documents(document_id), knowledge_chunk_id text REFERENCES content.chunks(chunk_id),
    display_title text NOT NULL, display_section text, display_url text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE customer_service.audit_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), event_type text NOT NULL, occurred_at timestamptz NOT NULL DEFAULT now(),
    actor_type text NOT NULL CHECK(actor_type IN ('CUSTOMER','OPERATOR','SYSTEM')), actor_id uuid,
    conversation_id uuid REFERENCES customer_service.conversations(id), correlation_id text, payload_json jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE OR REPLACE FUNCTION customer_service.reject_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'audit_events are append-only'; END $$;
CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON customer_service.audit_events
FOR EACH ROW EXECUTE FUNCTION customer_service.reject_audit_mutation();
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("The adopted V1 baseline is forward-only")
