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
| `auth.login_succeeded` | operator_id, request_id |
| `auth.login_failed` | normalized identifier fingerprint?; never password |

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
