# V1 Data Model

Names are conceptual; implementation naming may vary if semantics remain exact.

## 1. `operator_users`

| Field | Notes |
|---|---|
| id UUID PK | stable operator ID |
| email CITEXT/normalized text UNIQUE | login identifier |
| password_hash text | never plaintext |
| display_name text | demo operator label |
| is_active bool | default true |
| created_at timestamptz | |
| updated_at timestamptz | |

## 2. `conversations`

| Field | Notes |
|---|---|
| id UUID PK | |
| channel enum/text | V1 `WEB` |
| status enum | `WAITING`, `ACTIVE`, `CLOSED` |
| anonymous_token_digest text UNIQUE | no raw token |
| initial_mode enum | `N1`, `N2` snapshot |
| effective_mode enum | `N1`, `N2`; only downward N2->N1 in V1 |
| taken_over_at timestamptz nullable | |
| created_at timestamptz | |
| closed_at timestamptz nullable | |
| last_message_at timestamptz nullable | queue ordering |

Indexes: status/last_message_at, effective_mode.

## 3. `conversation_assignments`

Tracks assignment history.

| Field | Notes |
|---|---|
| id UUID PK | |
| conversation_id FK | |
| operator_id FK | |
| claimed_at timestamptz | |
| released_at timestamptz nullable | active if null |
| release_reason nullable | `CLOSED`, `RELEASED`, etc. |

Constraint: at most one active assignment per conversation. Capacity <=4/operator is a transactional domain rule using configured limit.

## 4. `messages`

Only customer-visible conversation messages belong here.

| Field | Notes |
|---|---|
| id UUID PK | |
| conversation_id FK | |
| author_type enum | `CUSTOMER`, `OPERATOR` |
| operator_id FK nullable | set for operator message |
| body text | final visible text |
| source_generation_id FK nullable | provenance only for operator messages |
| created_at timestamptz | |

Important: there is no `AI` author in V1 customer messages.

## 5. Existing canonical knowledge tables

The repository already has a populated knowledge model. V1 adopts and evolves
it in place instead of creating parallel `knowledge_documents` /
`knowledge_chunks` copies. Names below are implementation-canonical.

### 5.1 `content.documents` — clinical parents

| Field | Notes |
|---|---|
| document_id text PK | existing stable parent/source ID |
| title text | |
| version text | existing source version |
| patient_markdown_path text | existing repository source path; internal only |
| content_markdown text | V1 parent-body snapshot loaded from source file |
| content_hash text | |
| customer_citation_allowed bool | true only for approved clinical parent projection |
| is_active bool | |
| metadata jsonb | existing bounded source metadata |
| created_at/updated_at | |

Existing clinical/review fields are retained. `patient_markdown_path` is never
customer-visible.

### 5.2 `content.chunks` — clinical children

| Field | Notes |
|---|---|
| chunk_id text PK | existing stable child ID |
| parent_document_id FK | required reference to `content.documents.document_id` |
| ordinal int | unique within parent |
| heading text | section heading/path |
| content_markdown text | child grounding/search body |
| content_hash text | |
| embedding vector(1536) nullable | existing representation; model must match |
| embedding_provider text nullable | |
| embedding_model text nullable | |
| embedding_dimension int nullable | |
| embedded_at timestamptz nullable | |
| is_active bool | |
| metadata jsonb | existing metadata |
| created_at/updated_at | |

Constraints:

- every child references an existing clinical parent document;
- unique `(parent_document_id, ordinal)` (already present);
- embedding metadata/dimension matches the vector and configured model;
- ingestion success requires an embedding for every active child.

The parent is a document, not a synthetic chunk. Retrieval expands a matched
child through `parent_document_id` and uses the parent's snapshotted body.

### 5.3 `content.qa_entries` — flat administrative Q&A

| Field | Notes |
|---|---|
| qa_id text PK | existing stable ID |
| category text | existing grouping |
| question text | searchable question |
| answer_markdown text | grounding content |
| content_hash text | canonical content hash |
| customer_citation_allowed bool | default and V1 invariant `false` |
| embedding vector(1536) nullable | existing representation; model must match |
| embedding_provider/model/dimension | traceability |
| embedded_at timestamptz nullable | |
| is_active bool | |
| metadata jsonb | existing bounded metadata |

Administrative Q&A has no parent relation. Ingestion success requires an
embedding for every active Q&A row.

## 6. `retrieval_runs`

| Field | Notes |
|---|---|
| id UUID PK | |
| conversation_id FK nullable | manual search may optionally be conversation-scoped |
| triggering_message_id FK nullable | N2 draft |
| operator_id FK | requester |
| purpose enum | `N2_DRAFT`, `N1_MANUAL_SEARCH`, `N2_MANUAL_SEARCH` |
| query_text text | can reference message; persisted for reproducibility in demo |
| embedding_model text | |
| top_k int | |
| status enum | `STARTED`, `COMPLETED`, `FAILED` |
| duration_ms int nullable | |
| error_code text nullable | |
| created_at/completed_at | |

## 7. `retrieval_hits`

| Field | Notes |
|---|---|
| id UUID PK | |
| retrieval_run_id FK | |
| matched_kind enum/text | `ADMIN_QA` or `CLINICAL_CHILD` |
| matched_qa_id FK nullable | administrative match |
| matched_chunk_id FK nullable | clinical child match |
| expanded_parent_document_id FK nullable | clinical expansion |
| rank int | |
| score numeric/float | normalized/documented semantics |
| created_at | |

Exactly one matched target is set. Unique `(retrieval_run_id, rank)` and a
run/target uniqueness rule prevent duplicate hits.

## 8. `ai_generations`

| Field | Notes |
|---|---|
| id UUID PK | |
| conversation_id FK | |
| triggering_message_id FK | |
| retrieval_run_id FK | |
| prior_generation_id self-FK nullable | regeneration lineage |
| operator_id FK | requester |
| status enum | `ANSWER`, `ABSTAIN`, `FAILED` |
| draft_text text | internal only |
| abstention_reason text nullable | |
| provider text | |
| model text | |
| prompt_version text | |
| used_source_ids jsonb or relation | preferred relation below |
| input_tokens int nullable | |
| output_tokens int nullable | |
| duration_ms int nullable | |
| created_at | |

No update required after creation except if implementation uses a short-lived processing state. Final successful generations should be immutable.

## 9. `ai_generation_sources`

Recommended normalized relation.

| Field | Notes |
|---|---|
| ai_generation_id FK | |
| retrieval_hit_id FK | |
| use_order int | |

PK/unique on generation + hit.

## 10. `message_citations`

Only customer-visible citation attachments.

| Field | Notes |
|---|---|
| id UUID PK | |
| message_id FK | operator final message |
| knowledge_document_id FK | `content.documents`; clinical sources only in V1 |
| knowledge_chunk_id FK nullable | supporting child provenance |
| display_title text | snapshot approved display |
| display_section text nullable | |
| display_url text nullable | only approved public URL |
| created_at | |

Server creates only after checking source exposure policy.

## 11. `audit_events`

| Field | Notes |
|---|---|
| id UUID PK | |
| event_type text | controlled catalog |
| occurred_at timestamptz | |
| actor_type text | `CUSTOMER`, `OPERATOR`, `SYSTEM` |
| actor_id UUID nullable | |
| conversation_id UUID nullable | |
| correlation_id text nullable | |
| payload_json jsonb | no full message bodies by default |

No application update/delete methods.

## 12. Future entities explicitly absent

Do not create V1 tables for:

- saved customer profile;
- CPF/password credential;
- supervisor;
- team autonomy policy;
- manager dashboard;
- dynamic ETA;
- escalation workflow;
- appointment booking state.
