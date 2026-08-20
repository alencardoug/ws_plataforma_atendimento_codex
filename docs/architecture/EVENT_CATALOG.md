# Audit Event Catalog

Audit events are append-only facts. Payloads should use stable identifiers and minimal metadata rather than duplicating sensitive bodies.

V2 changes are marked inline; see `specs/002-v2-commercial-product-experience/plan.md` §14 for rationale.
V3 changes are marked inline; see `specs/003-v3-measured-n2/plan.md` §19 for rationale. V3-2 (quick-approve) and
V3-6 (regenerate-with-instruction) needed no new event type: quick-approve reuses `ai.draft_accepted`
(it sends the draft through the same `send_operator_message` path as any other unmodified send), and
regenerate-with-instruction extends `ai.draft_generated`/`ai.draft_abstained`'s existing payload with
`instruction_text` rather than introducing a separate event.

| Event | Required metadata |
|---|---|
| `conversation.created` | conversation_id, channel |
| `conversation.claimed` | conversation_id, operator_id, active_count_after |
| `conversation.released` | conversation_id, operator_id |
| `conversation.closed` | conversation_id, actor_type, actor_id? |
| `conversation.taken_over` | conversation_id, operator_id, from_mode=N2, to_mode=N1, reason? |
| **`conversation.satisfaction_submitted`** (V3-12) | conversation_id, actor_type=CUSTOMER, score, resolved, category_slug? — optional, never blocks/delays the close it follows |
| ~~`conversation.typing_heartbeat`~~ | **Deliberately not audited** (V2-7) — the customer typing-heartbeat endpoint (`POST /public/conversations/{id}/typing`, roughly every 2.5s while the customer has non-empty draft text) fires too frequently to be a meaningful audit fact and carries no product-facing decision of its own; it only updates `last_customer_typing_at`/`last_customer_activity_at` and may trigger `ai.draft_generated` (which *is* audited) as a side effect. This is an explicit scope boundary, not an oversight — see `plan.md` §14. |
| `message.customer_received` | conversation_id, message_id, length |
| `message.operator_sent` | conversation_id, message_id, operator_id, source_generation_id?, modified_from_draft? |
| `rag.search_started` | conversation_id, retrieval_run_id, trigger_message_id |
| `rag.search_completed` | retrieval_run_id, hit_count, duration_ms |
| `rag.search_failed` | retrieval_run_id, error_class |
| `ai.draft_generated` | ai_generation_id, conversation_id, retrieval_run_id, model, duration_ms, prior_generation_id?, reason_code?, trigger (`AUTOMATIC`\|`MANUAL_DRAFT`\|`MANUAL_EVIDENCE`), **instruction_text? (V3-6)** — never customer-facing, same treatment as `manual_search_text` |
| ~~`ai.draft_regenerated`~~ | **Removed in V2** — there is no separate regenerate action (`spec.md` V2-7); re-invoking draft generation against the current selection emits `ai.draft_generated` with `prior_generation_id` set instead. V1-only. |
| `ai.draft_abstained` | ai_generation_id, reason_code, **instruction_text? (V3-6)** |
| `ai.draft_accepted` | ai_generation_id, operator_id — **also the canonical event for V3-2's quick-approve (no separate event type — it sends the draft through this exact path)** |
| `ai.draft_edited` | ai_generation_id, operator_id, final_message_id? |
| **`generation.marked_incorrect`** (V3-1) | ai_generation_id, operator_id — idempotent, retroactive, reachable from any generation in a conversation's history, not only the latest |
| **`generation.escalated`** (V3-1) | ai_generation_id, operator_id — redefined from the roadmap's original framing: a content-gap signal ("operator could not answer using what is already standardized"), not a routing/handoff request to a specialist (that remains V5's separate, unbuilt workflow); tag only, no queue |
| **`ai.dynamic_pattern_resolved`** (V2-6) | ai_generation_id — emitted alongside `ai.draft_generated` when `dynamic_pattern_used=true` |
| **`ai.dynamic_pattern_fallback`** (V2-6) | ai_generation_id, cause (audit-only diagnostic string, e.g. table/column not found — never customer-visible) — emitted alongside `ai.draft_abstained` when a `dynamic_data_required` entry's resolution fails or has no binding configured |
| **`ai.clinical_deflection_applied`** (2026-08-19, human decision) | ai_generation_id — emitted alongside `ai.draft_generated` when the clinical-question reranker (`GenerationProvider.rerank_clinical`) replaces a dynamic-pattern or LLM-composed candidate with the fixed clinical-deflection text (`CLINICAL_DEFLECTION_TEXT`). Scoped to the non-GB, non-`full_parent_draft` branch only — a matched clinical parent document is never second-guessed |
| `knowledge.manual_search` | operator_id, conversation_id?, retrieval_run_id |
| `knowledge.ingestion_started` | ingestion_run_id, source_type |
| `knowledge.ingestion_completed` | ingestion_run_id, inserted, updated, embedded, skipped |
| `knowledge.ingestion_failed` | ingestion_run_id, error_class |
| **`knowledge.category_created`** (V3-8) | slug, operator_id — the shared registry `content.qa_entries.category` and `content.documents.cancer_type` both key off (`plan.md` §3.1) |
| **`knowledge.qa_created`** (V2-8) | qa_id, operator_id |
| **`knowledge.qa_updated`** (V2-8) | qa_id, operator_id |
| **`knowledge.qa_deactivated`** (V2-8) | qa_id, operator_id |
| **`knowledge.clinical_document_created`** (V2-8) | document_id, operator_id |
| **`knowledge.clinical_document_updated`** (V2-8) | document_id, operator_id |
| **`knowledge.clinical_document_deactivated`** (V2-8) | document_id, operator_id |
| **`knowledge.clinical_chunk_created`** (V2-8) | chunk_id, document_id, operator_id |
| **`knowledge.clinical_chunk_updated`** (V2-8) | chunk_id, document_id, operator_id |
| **`knowledge.clinical_chunk_deactivated`** (V2-8) | chunk_id, document_id, operator_id |
| **`evaluation.case_created`** (V3-5) | case_id, operator_id — not conversation-scoped; `content.evaluation_cases` has no FK path to/from `conversations`/`ai_generations` (structural isolation) |
| **`evaluation.case_reviewed`** (V3-5) | case_id, actual_status, operator_id — set only by a reviewer's manual re-check; no automated process calls this (no re-run mechanism in V3) |
| `auth.login_succeeded` | operator_id, request_id |
| `auth.login_failed` | normalized identifier fingerprint?; never password |
| **`anonymous_access.token_validation_rate_limited`** (V2-2) | correlation_id — emitted when a source IP is currently locked out (`plan.md` §13.1); deliberately carries no client IP, attempted token, or attempted `conversation_id` in the payload (the attempted `conversation_id` may not correspond to a real conversation, so it is never used as this event's FK-constrained `conversation_id` column either) |
| **`scheduling.availability_seeded`** (dynamic appointment availability, AA-9) | created_d1, created_d7, already_sufficient; operator is in the standard audit `actor_id` column — emitted by `POST /operator/scheduling/ensure-availability`, the sole write-triggering endpoint for `scheduling.schedule_slots`; not conversation-scoped (no `ai_generation_id`/`conversation_id` — this action isn't about any one customer) |
| **`scheduling.wide_availability_seeded`** (006/SV-4) | specialty_count, business_day_count, slots_created; emitted by `POST /operator/scheduling/ensure-wide-availability` — a separate, wider one-time bulk fill (every specialty, every business day through 2026-12-30) from `ensure-availability`'s own D+1/D+7 generalist-only scope above; not conversation-scoped |
| **`scheduling.booking_recorded`** (007/BS-4) | conversation_id, source (`guided_booking`\|`booking_script`), specialty_slug, has_slot_detail — emitted by both write triggers (`guided_booking.py`'s `interpret_payment_reply`, `booking_script/service.py`'s completion step) once a booking flow completes. Never the completion message's own body text, never CPF/payment content |
| **`ai.date_intent_extracted`** (006/ND-4) | query_text_hash (never the raw customer text — Constitution Article VI), prompt_version, intent_resolved — emitted only when `extract_parameters()`'s LLM date-intent fallback actually fires (its own pre-filter found no keyword match but apparent date/time language); `intent_resolved` distinguishes "the model returned a usable date" from "returned nothing usable," both of which fall through to the same safe manual/insufficient-match path (ND-3) |
| **`booking_script.autonomous_message_sent`** ⚠ (dynamic appointment availability, AA-10, Constitution Amendment 1.1.0) | conversation_id, message_id, step — **never** the customer's raw CPF or payment-question reply, and never the sent message's own body. `actor_type = "SYSTEM"`, the only event type in the entire catalog marking a message sent with no operator click. `SELECT * FROM audit_events WHERE event_type = 'booking_script.autonomous_message_sent'` is, by construction, a complete and exhaustive list of every autonomously-sent message in the system. |

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
