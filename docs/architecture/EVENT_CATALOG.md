# Audit Event Catalog

Audit events are append-only facts. Payloads should use stable identifiers and minimal metadata rather than duplicating sensitive bodies.

V2 changes are marked inline; see `specs/002-v2-commercial-product-experience/plan.md` §14 for rationale.

| Event | Required metadata |
|---|---|
| `conversation.created` | conversation_id, channel |
| `conversation.claimed` | conversation_id, operator_id, active_count_after |
| `conversation.released` | conversation_id, operator_id |
| `conversation.closed` | conversation_id, actor_type, actor_id? |
| `conversation.taken_over` | conversation_id, operator_id, from_mode=N2, to_mode=N1, reason? |
| ~~`conversation.typing_heartbeat`~~ | **Deliberately not audited** (V2-7) — the customer typing-heartbeat endpoint (`POST /public/conversations/{id}/typing`, roughly every 2.5s while the customer has non-empty draft text) fires too frequently to be a meaningful audit fact and carries no product-facing decision of its own; it only updates `last_customer_typing_at`/`last_customer_activity_at` and may trigger `ai.draft_generated` (which *is* audited) as a side effect. This is an explicit scope boundary, not an oversight — see `plan.md` §14. |
| `message.customer_received` | conversation_id, message_id, length |
| `message.operator_sent` | conversation_id, message_id, operator_id, source_generation_id?, modified_from_draft? |
| `rag.search_started` | conversation_id, retrieval_run_id, trigger_message_id |
| `rag.search_completed` | retrieval_run_id, hit_count, duration_ms |
| `rag.search_failed` | retrieval_run_id, error_class |
| `ai.draft_generated` | ai_generation_id, conversation_id, retrieval_run_id, model, duration_ms, prior_generation_id?, reason_code?, **trigger (V2: `AUTOMATIC`\|`MANUAL_DRAFT`\|`MANUAL_EVIDENCE`)** |
| ~~`ai.draft_regenerated`~~ | **Removed in V2** — there is no separate regenerate action (`spec.md` V2-7); re-invoking draft generation against the current selection emits `ai.draft_generated` with `prior_generation_id` set instead. V1-only. |
| `ai.draft_abstained` | ai_generation_id, reason_code |
| `ai.draft_accepted` | ai_generation_id, operator_id |
| `ai.draft_edited` | ai_generation_id, operator_id, final_message_id? |
| **`ai.dynamic_pattern_resolved`** (V2-6) | ai_generation_id — emitted alongside `ai.draft_generated` when `dynamic_pattern_used=true` |
| **`ai.dynamic_pattern_fallback`** (V2-6) | ai_generation_id, cause (audit-only diagnostic string, e.g. table/column not found — never customer-visible) — emitted alongside `ai.draft_abstained` when a `dynamic_data_required` entry's resolution fails or has no binding configured |
| `knowledge.manual_search` | operator_id, conversation_id?, retrieval_run_id |
| `knowledge.ingestion_started` | ingestion_run_id, source_type |
| `knowledge.ingestion_completed` | ingestion_run_id, inserted, updated, embedded, skipped |
| `knowledge.ingestion_failed` | ingestion_run_id, error_class |
| **`knowledge.qa_created`** (V2-8) | qa_id, operator_id |
| **`knowledge.qa_updated`** (V2-8) | qa_id, operator_id |
| **`knowledge.qa_deactivated`** (V2-8) | qa_id, operator_id |
| **`knowledge.clinical_document_created`** (V2-8) | document_id, operator_id |
| **`knowledge.clinical_document_updated`** (V2-8) | document_id, operator_id |
| **`knowledge.clinical_document_deactivated`** (V2-8) | document_id, operator_id |
| **`knowledge.clinical_chunk_created`** (V2-8) | chunk_id, document_id, operator_id |
| **`knowledge.clinical_chunk_updated`** (V2-8) | chunk_id, document_id, operator_id |
| **`knowledge.clinical_chunk_deactivated`** (V2-8) | chunk_id, document_id, operator_id |
| `auth.login_succeeded` | operator_id, request_id |
| `auth.login_failed` | normalized identifier fingerprint?; never password |
| **`anonymous_access.token_validation_rate_limited`** (V2-2) | correlation_id — emitted when a source IP is currently locked out (`plan.md` §13.1); deliberately carries no client IP, attempted token, or attempted `conversation_id` in the payload (the attempted `conversation_id` may not correspond to a real conversation, so it is never used as this event's FK-constrained `conversation_id` column either) |

## Event properties

Every event:

- `id`
- `event_type`
- `occurred_at`
- `actor_type`
- `actor_id` nullable
- `conversation_id` nullable
- `correlation_id` nullable
- `payload_json`

Application APIs provide no update/delete operation for audit events.
