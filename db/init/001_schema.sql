CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE SCHEMA IF NOT EXISTS governance;
CREATE SCHEMA IF NOT EXISTS content;
CREATE SCHEMA IF NOT EXISTS scheduling;
CREATE SCHEMA IF NOT EXISTS identity;
CREATE SCHEMA IF NOT EXISTS billing;

CREATE TYPE content.document_status AS ENUM ('draft', 'published', 'retired');
CREATE TYPE scheduling.slot_status AS ENUM ('available', 'held', 'booked', 'blocked');
CREATE TYPE scheduling.appointment_status AS ENUM ('held', 'awaiting_payment', 'confirmed', 'cancelled', 'no_show', 'completed');
CREATE TYPE billing.payment_status AS ENUM ('created', 'confirmed', 'refunded', 'partially_refunded', 'failed');

CREATE TABLE governance.sources (
    source_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL,
    organization text NOT NULL,
    url text NOT NULL UNIQUE,
    accessed_at date NOT NULL DEFAULT CURRENT_DATE,
    source_type text NOT NULL,
    notes text
);

CREATE TABLE governance.policies (
    policy_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_code text NOT NULL,
    version text NOT NULL,
    title text NOT NULL,
    body_markdown text NOT NULL,
    effective_from date NOT NULL,
    simulated boolean NOT NULL DEFAULT true,
    UNIQUE (policy_code, version)
);

CREATE TABLE content.documents (
    document_id text PRIMARY KEY,
    title text NOT NULL,
    document_type text NOT NULL,
    cancer_type text,
    care_phase text,
    procedure_slug text,
    audience text[] NOT NULL DEFAULT ARRAY['paciente','familiar'],
    language text NOT NULL DEFAULT 'pt-BR',
    responsible_physician text NOT NULL,
    version text NOT NULL,
    status content.document_status NOT NULL DEFAULT 'published',
    created_at date NOT NULL,
    last_reviewed_at date NOT NULL,
    next_review_at date NOT NULL,
    patient_markdown_path text NOT NULL,
    dynamic_data_required boolean NOT NULL DEFAULT false,
    dynamic_resolver text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (document_id, version)
);

CREATE TABLE content.document_sources (
    document_id text NOT NULL REFERENCES content.documents(document_id) ON DELETE CASCADE,
    source_id uuid NOT NULL REFERENCES governance.sources(source_id),
    PRIMARY KEY (document_id, source_id)
);

CREATE TABLE content.chunks (
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
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('portuguese', coalesce(heading,'') || ' ' || coalesce(content_markdown,''))
    ) STORED,
    UNIQUE (parent_document_id, ordinal)
);

CREATE INDEX chunks_parent_idx ON content.chunks(parent_document_id);
CREATE INDEX chunks_metadata_idx ON content.chunks USING gin(metadata);
CREATE INDEX chunks_search_idx ON content.chunks USING gin(search_vector);
CREATE INDEX chunks_embedding_hnsw_idx ON content.chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE content.qa_entries (
    qa_id text PRIMARY KEY,
    category text NOT NULL,
    question text NOT NULL,
    answer_markdown text NOT NULL,
    retrieval_intents text[] NOT NULL DEFAULT '{}',
    dynamic_data_required boolean NOT NULL DEFAULT false,
    dynamic_resolver text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1536),
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('portuguese', coalesce(question,'') || ' ' || coalesce(answer_markdown,''))
    ) STORED
);

CREATE INDEX qa_category_idx ON content.qa_entries(category);
CREATE INDEX qa_search_idx ON content.qa_entries USING gin(search_vector);
CREATE INDEX qa_embedding_hnsw_idx ON content.qa_entries USING hnsw (embedding vector_cosine_ops);

CREATE TABLE scheduling.units (
    unit_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    timezone text NOT NULL DEFAULT 'America/Sao_Paulo',
    simulated boolean NOT NULL DEFAULT true
);

CREATE TABLE scheduling.specialties (
    specialty_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug text NOT NULL UNIQUE,
    display_name text NOT NULL,
    description text NOT NULL,
    simulated boolean NOT NULL DEFAULT true
);

CREATE TABLE scheduling.professionals (
    professional_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name text NOT NULL,
    registration_display text,
    simulated boolean NOT NULL DEFAULT true,
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE scheduling.professional_specialties (
    professional_id uuid NOT NULL REFERENCES scheduling.professionals(professional_id),
    specialty_id uuid NOT NULL REFERENCES scheduling.specialties(specialty_id),
    fixed_price_cents integer NOT NULL CHECK (fixed_price_cents >= 0),
    appointment_duration_minutes integer NOT NULL DEFAULT 60 CHECK (appointment_duration_minutes > 0),
    PRIMARY KEY (professional_id, specialty_id)
);

CREATE TABLE scheduling.holidays (
    holiday_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    holiday_date date NOT NULL,
    name text NOT NULL,
    scope text NOT NULL CHECK (scope IN ('national','state','municipal','institutional')),
    state_code char(2),
    city_code text,
    unit_id uuid REFERENCES scheduling.units(unit_id),
    is_business_day boolean NOT NULL DEFAULT false,
    simulated boolean NOT NULL DEFAULT false
);

CREATE UNIQUE INDEX holidays_natural_key_idx ON scheduling.holidays (
    holiday_date, scope, coalesce(state_code,''), coalesce(city_code,''), coalesce(unit_id::text,'')
);

CREATE TABLE scheduling.schedule_slots (
    slot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_id uuid NOT NULL REFERENCES scheduling.units(unit_id),
    specialty_id uuid NOT NULL REFERENCES scheduling.specialties(specialty_id),
    professional_id uuid NOT NULL REFERENCES scheduling.professionals(professional_id),
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL,
    status scheduling.slot_status NOT NULL DEFAULT 'available',
    simulated boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (ends_at > starts_at),
    UNIQUE (professional_id, starts_at)
);

CREATE TABLE scheduling.slot_offers (
    offer_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slot_id uuid NOT NULL REFERENCES scheduling.schedule_slots(slot_id) ON DELETE CASCADE,
    specialty_id uuid NOT NULL REFERENCES scheduling.specialties(specialty_id),
    offer_window text NOT NULL CHECK (offer_window IN ('NEXT_DAY','SEVEN_DAYS')),
    reference_date date NOT NULL,
    eligible_from timestamptz NOT NULL,
    eligible_until timestamptz NOT NULL,
    generation_batch_id uuid NOT NULL,
    UNIQUE (slot_id, offer_window, reference_date)
);

CREATE INDEX slot_offers_lookup_idx ON scheduling.slot_offers(specialty_id, offer_window, reference_date);

CREATE TABLE identity.patients (
    patient_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name text NOT NULL,
    cpf_ciphertext bytea NOT NULL,
    cpf_hash text NOT NULL UNIQUE,
    cpf_last4 char(4) NOT NULL,
    phone text NOT NULL,
    email text NOT NULL,
    birth_date date,
    insurance_name text,
    city text,
    state_code char(2),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE identity.consent_records (
    consent_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id uuid NOT NULL REFERENCES identity.patients(patient_id),
    purpose text NOT NULL,
    policy_version text NOT NULL,
    accepted boolean NOT NULL,
    accepted_at timestamptz NOT NULL DEFAULT now(),
    channel text NOT NULL CHECK (channel IN ('telegram','web','api'))
);

CREATE TABLE scheduling.appointments (
    appointment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    protocol text NOT NULL UNIQUE,
    slot_id uuid NOT NULL UNIQUE REFERENCES scheduling.schedule_slots(slot_id),
    patient_id uuid NOT NULL REFERENCES identity.patients(patient_id),
    status scheduling.appointment_status NOT NULL DEFAULT 'held',
    hold_expires_at timestamptz NOT NULL,
    reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    confirmed_at timestamptz,
    cancelled_at timestamptz,
    cancellation_reason text
);

CREATE TABLE scheduling.appointment_events (
    event_id bigserial PRIMARY KEY,
    appointment_id uuid NOT NULL REFERENCES scheduling.appointments(appointment_id),
    event_type text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE billing.payments (
    payment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id uuid NOT NULL UNIQUE REFERENCES scheduling.appointments(appointment_id),
    amount_cents integer NOT NULL CHECK (amount_cents >= 0),
    status billing.payment_status NOT NULL DEFAULT 'created',
    provider text NOT NULL DEFAULT 'pagamento_ficticio',
    payment_url text NOT NULL DEFAULT 'https://www.pagamento_fictico.cancercenter.com',
    simulated boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    confirmed_at timestamptz,
    refunded_cents integer NOT NULL DEFAULT 0
);

CREATE TABLE billing.payment_events (
    event_id bigserial PRIMARY KEY,
    payment_id uuid NOT NULL REFERENCES billing.payments(payment_id),
    event_type text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now()
);
