# Audit Event Catalog — V1

Audit events are append-only facts. Payloads should use stable identifiers and minimal metadata rather than duplicating sensitive bodies.

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
| `ai.draft_generated` | ai_generation_id, conversation_id, retrieval_run_id, model, duration_ms |
| `ai.draft_regenerated` | new_generation_id, prior_generation_id |
| `ai.draft_abstained` | ai_generation_id, reason_code |
| `ai.draft_accepted` | ai_generation_id, operator_id |
| `ai.draft_edited` | ai_generation_id, operator_id, final_message_id? |
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
