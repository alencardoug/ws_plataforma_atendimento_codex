# V2 Data Model

This is a delta over `specs/001-v1-assisted-customer-service/data-model.md`,
which remains canonical for every table/field not listed here. Names are
conceptual; implementation naming may vary if semantics remain exact. See
`plan.md` §3 for the rationale behind each change.

## 1. `conversations` (new columns)

| Field | Notes |
|---|---|
| `last_customer_activity_at` timestamptz nullable | updated on customer message send and on the typing heartbeat (`plan.md` §7.2); drives the 8-second automatic-trigger debounce |
| `last_customer_typing_at` timestamptz nullable | updated only by the typing heartbeat; drives the `is_customer_typing` derived signal, kept separate from the debounce clock so a stale heartbeat cannot itself extend the 8s window |
| `auto_draft_covers_through_message_id` FK → `messages.id`, nullable | newest customer message already covered by an `AUTOMATIC`-trigger generation; prevents re-triggering the same activity run on every poll |

No column is added for token-validation attempts — rate limiting (`plan.md`
§13.1) is keyed by request source, not by conversation, so a new
conversation cannot reset an attacker's counter.

## 2. `message_selections` (new table)

The persisted record of exactly which messages a generation used — this is
what `spec.md` §4 calls a generation's "selected conversation-message IDs,
stable ordering." Ordering is derived from each referenced message's
`created_at`; no separate ordinal column.

| Field | Notes |
|---|---|
| `id` UUID PK | |
| `ai_generation_id` FK → `ai_generations.id` | |
| `message_id` FK → `messages.id` | |
| `created_at` timestamptz | |

Constraint: unique `(ai_generation_id, message_id)`. Populated for every
generation regardless of `trigger` (§3) — for `AUTOMATIC`, from the resolved
consecutive customer-message run; for `MANUAL_DRAFT`, from whatever the
operator had checked; `MANUAL_EVIDENCE` generations do not populate this
table (that path is explicitly independent of message-context selection, per
V2-3/V2-4).

## 3. `ai_generations` (new/changed columns)

| Field | Notes |
|---|---|
| `trigger` enum `AUTOMATIC` \| `MANUAL_DRAFT` \| `MANUAL_EVIDENCE` | which V2-7/V2-3 path produced this generation |
| `manual_search_text` text nullable | the manual-search box content used as input, when applicable (`MANUAL_DRAFT`, `MANUAL_EVIDENCE`) |
| `dynamic_pattern_used` bool default false | true only when `draft_text` is a resolved `plan.md` §9.2 pattern substitution, not LLM output — lets audit/traceability distinguish the two without inspecting text heuristically |
| `triggering_message_id` FK → `messages.id`, **now nullable** (was NOT NULL in V1) | `MANUAL_EVIDENCE` generations (`plan.md` §5) have no single triggering customer message — evidence selection, not a message, drives them. For `AUTOMATIC`/`MANUAL_DRAFT`, this continues to hold the most recent selected customer message for quick display; `message_selections` (§2) remains the authoritative full set for both trigger types |

`status` gains no new enum value at the schema level; `ABSTAIN` with
`abstention_reason = DYNAMIC_DATA_UNAVAILABLE` (`plan.md` §9.3) is a value
within the existing `abstention_reason` domain, not a new column.

## 4. `content.qa_dynamic_bindings` (new table)

One optional binding per Q&A entry, authored through V2-8's CRUD screen
(`plan.md` §10), resolved per `plan.md` §9.2.

| Field | Notes |
|---|---|
| `qa_id` FK → `content.qa_entries.qa_id`, unique | one binding per entry |
| `source_table` text | must match a key in the server-side table allowlist (`plan.md` §9.2); never a raw identifier built into SQL |
| `filter` jsonb | static `{column: value}` equality filter, e.g. `{"specialty": "Cardiologia", "availability": "positive"}` |
| `output_columns` jsonb | ordered `[{column, variable_name}, ...]` mapping table columns to `{{variable_name}}` placeholders in `answer_markdown` |
| `row_limit` int default 4 | matches the existing "up to four offers" phrasing already present in the V1 demo Q&A content |
| `created_at` / `updated_at` timestamptz | |

`content.qa_entries.answer_markdown` is unchanged in type (still text); an
entry with a binding row simply contains `{{variable_name}}` placeholders
instead of literal prose. An entry with `dynamic_data_required = true` and no
row in this table is exactly V1's original finding condition, now closed by
the fallback in `plan.md` §9.3 rather than by data-model shape — no new
"unconfigured" state needs its own column.

## 5. Fields deliberately not added

- No raw-token column anywhere (`plan.md` §4; V2-2 confirms the token is not
  a recovery mechanism, so there is no requirement to look a conversation up
  by token after issuance beyond the existing digest-compare validation).
- No persisted "is typing" event log — `last_customer_typing_at` is
  overwritten in place; typing is a live signal, not a durable fact worth an
  audit trail entry (`plan.md` §14 documents this exception explicitly).
- No new operator role/permission table — V2-8 CRUD reuses the existing
  `operator_users` authentication as-is (`plan.md` §13.2).
- No new customer-facing entity for "resume via token" — deliberately absent
  per V2-2.

## 6. Constraints and integrity notes

- `message_selections.message_id` must belong to the same conversation as
  `message_selections.ai_generation_id.conversation_id` — enforced at the
  application layer (validated before insert, per `plan.md` §6), not by a
  cross-table FK PostgreSQL cannot express directly; add an application-level
  integration test for this instead of relying on schema alone.
- `qa_dynamic_bindings.source_table` is validated against the allowlist at
  write time (V2-8 CRUD) *and* at resolution time (`plan.md` §9.2) — both
  checks are required; the write-time check catches operator mistakes early, the
  resolution-time check is the actual security boundary and must not be
  skipped even if the write-time check already passed once (an allowlist
  entry could theoretically be removed from a later deploy).
- Soft-delete (`is_active = false`) on `content.qa_entries`,
  `content.documents`, and `content.chunks` (V2-8, all three columns already
  exist in V1) must continue to preserve referential integrity for
  historical `ai_generation_sources` and `message_citations` rows — no
  cascade delete is introduced.
