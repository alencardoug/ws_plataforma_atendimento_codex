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

## 5. `knowledge_documents`

| Field | Notes |
|---|---|
| id UUID PK | |
| external_id text UNIQUE | source stable ID |
| knowledge_type enum | `ADMIN_QA`, `CLINICAL` |
| title text | |
| source_label text nullable | |
| source_uri text nullable | internal/public source ref |
| version text nullable | |
| content_hash text | |
| customer_citation_allowed bool | default false for admin, explicit/true for approved clinical |
| is_active bool | |
| metadata_json jsonb | bounded source metadata |
| created_at/updated_at | |

## 6. `knowledge_chunks`

| Field | Notes |
|---|---|
| id UUID PK | |
| document_id FK | |
| external_id text | unique within source/document |
| chunk_role enum | `QNA`, `PARENT`, `CHILD` |
| parent_chunk_id self-FK nullable | required for clinical CHILD |
| question text nullable | for QNA |
| content text | Q&A answer, parent body, or child body |
| search_text text | material used for embedding |
| section_path text nullable | |
| content_hash text | |
| embedding vector(D) nullable | only QNA/CHILD normally |
| embedding_model text nullable | |
| embedding_dimension int nullable | |
| embedded_at timestamptz nullable | |
| is_active bool | |
| metadata_json jsonb | |
| created_at/updated_at | |

Constraints:

- `QNA`: no parent required; question recommended; embedding required after ingestion success.
- `PARENT`: no parent; embedding optional/not required V1.
- `CHILD`: `parent_chunk_id` required and parent role must be PARENT at application validation.
- unique `(document_id, external_id)`.

Vector index: create on searchable rows using the chosen V1 embedding dimension/operator class.

## 7. `retrieval_runs`

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

## 8. `retrieval_hits`

| Field | Notes |
|---|---|
| id UUID PK | |
| retrieval_run_id FK | |
| matched_chunk_id FK | QNA or CHILD |
| expanded_parent_chunk_id FK nullable | clinical |
| rank int | |
| score numeric/float | normalized/documented semantics |
| created_at | |

Unique `(retrieval_run_id, rank)` and preferably `(retrieval_run_id, matched_chunk_id)`.

## 9. `ai_generations`

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

## 10. `ai_generation_sources`

Recommended normalized relation.

| Field | Notes |
|---|---|
| ai_generation_id FK | |
| retrieval_hit_id FK | |
| use_order int | |

PK/unique on generation + hit.

## 11. `message_citations`

Only customer-visible citation attachments.

| Field | Notes |
|---|---|
| id UUID PK | |
| message_id FK | operator final message |
| knowledge_document_id FK | source |
| knowledge_chunk_id FK nullable | typically clinical parent |
| display_title text | snapshot approved display |
| display_section text nullable | |
| display_url text nullable | only approved public URL |
| created_at | |

Server creates only after checking source exposure policy.

## 12. `audit_events`

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

## 13. Future entities explicitly absent

Do not create V1 tables for:

- saved customer profile;
- CPF/password credential;
- supervisor;
- team autonomy policy;
- manager dashboard;
- dynamic ETA;
- escalation workflow;
- appointment booking state.
