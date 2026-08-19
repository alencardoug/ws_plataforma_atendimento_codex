# Data Model: Dynamic Pricing and Guided Booking Selection

Governing plan: `plan.md` §3/§5. Two additive migrations; no edit to any
already-applied migration, `db/init/*.sql`, or `scheduling.*` table shape.

## 1. New table: `customer_service.appointment_offer_presentations`

One row per offer shown to a customer by a resolved
`appointment_availability` generation (up to 4 per generation, AA-2's
existing `LIMIT 4`). Append-only — never updated, never deleted (a later
resolution simply inserts a new set tied to its own new
`ai_generation_id`).

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | `gen_random_uuid()` default, matching every other table in this schema |
| `ai_generation_id` | `uuid` FK → `customer_service.ai_generations.id` | the resolving generation that showed this offer |
| `slot_id` | `uuid` FK → `scheduling.schedule_slots.slot_id` | which specific slot this offer was — **not** a copy of specialty/time/price; those are read live from the slot/join at query time via `slot_id`, so this table never drifts from `scheduling.*`'s own data |
| `display_order` | `smallint` | 1-4, the order the customer actually saw it in (`_render_offers`'s existing row order) |
| `description` | `text` | the one-line summary embedded for GB-2 matching (`plan.md` §5.1's `_offer_description`) — distinct from AA-2's multi-line customer-facing block; short enough to embed cheaply and compare cleanly |
| `embedding` | `vector(1536)` | same dimension/model convention as `content.qa_entries.embedding`/`content.knowledge_chunks.embedding` (`AI_EMBEDDING_DIMENSION`) |
| `created_at` | `timestamptz` | `now()` default |

Constraints:

- `UNIQUE (ai_generation_id, display_order)` — matches
  `ai_generation_sources`'s own `(ai_generation_id, use_order)` unique
  pattern.
- `FOREIGN KEY (ai_generation_id) REFERENCES customer_service.ai_generations(id)`,
  `FOREIGN KEY (slot_id) REFERENCES scheduling.schedule_slots(slot_id)` —
  this is the one new cross-schema FK in the codebase from
  `customer_service` into `scheduling`; both schemas already live in the
  same database/migration history (004 put `scheduling.*` there), so this
  is a normal FK, not a new architectural boundary.
- `CHECK (display_order BETWEEN 1 AND 4)`.

Index: `(ai_generation_id)` (covered by the unique constraint above, no
separate index needed) plus a per-conversation lookup path — see §2.

### Why `slot_id` and not a denormalized copy

`interpret_slot_choice` (`plan.md` §5.2) only ever needs the `description`
and `embedding` columns to find the match, and the caller that acts on a
match (composing the confirmation-question draft, GB-2) needs the offer's
human-readable specifics — both already fully covered by joining `slot_id`
back to `scheduling.schedule_slots`/`specialties`/`professionals`/`units`
at read time, the same join `resolve_appointment_availability` already
performs. Denormalizing price/time text into this table would create a
second source of truth that could drift if a slot's data were ever
corrected — read-through-the-FK is simpler and matches how
`ai_generation_sources` treats `retrieval_hit_id` (a pointer, not a copy).

## 2. Query support: "latest unconfirmed offer set for a conversation"

`plan.md` §5.2's `latest_unconfirmed_offer_generation_id(session, conversation_id)`:

```sql
SELECT aop.ai_generation_id
FROM customer_service.appointment_offer_presentations aop
JOIN customer_service.ai_generations g ON g.id = aop.ai_generation_id
WHERE g.conversation_id = :conversation_id
ORDER BY g.created_at DESC
LIMIT 1
```

"Unconfirmed" is not a stored flag — it falls out of the branch ordering
in `generate_draft()` (`plan.md` §5.2): once a slot choice is confirmed
(GB-4 affirmative), the conversation's next real customer message either
satisfies `detect_booking_intent()` (AA-10 starts, and
`conversation.booking_script_step` becomes non-`None` — a state
`generate_draft()` can check directly to stop offering guided-selection
branches at all once a real booking script is in progress) or doesn't (the
customer changed their mind or asked something else, in which case falling
through to ordinary RAG composition is correct anyway, same as GB-3). No
new "confirmed" boolean is needed on this table or on `AIGeneration`.

Composite index for this query:
`(conversation_id)` — added via the `ai_generations` side, since this
table doesn't itself carry `conversation_id` (avoids a second denormalized
copy, same reasoning as §1): the migration adds
`CREATE INDEX ON customer_service.appointment_offer_presentations (ai_generation_id)`
and relies on `ai_generations`'s own existing `conversation_id` index for
the join — confirmed present already (`20260814_...` migration family).

## 3. `ai_generations.trigger`: two new allowed values

The existing `CHECK (trigger IN ('AUTOMATIC', 'MANUAL_DRAFT', 'MANUAL_EVIDENCE'))`
(`20260814_0001_v2_selection_triggers_dynamic_pattern.py`) is widened,
additively, to also allow:

- `'GUIDED_SLOT_SELECTION'` — GB-2's output.
- `'GUIDED_CONFIRMATION'` — GB-4's output.

This reuses the `trigger` column's existing purpose (what kind of thing
produced this generation) rather than adding a new boolean/marker column —
the same choice `dynamic_pattern_used` already made for AA-1/V2-6's
resolver-vs-LLM distinction. `generate_draft()`'s GB-4 check (`plan.md`
§5.3, "was the immediately preceding sent message a GB-2 confirmation
question") needs no new lookup mechanism at all: `Message` already carries
`source_generation_id` (a direct FK to `ai_generations.id`, set whenever a
sent message originated from a draft). The check is simply "does this
conversation's most recent `OPERATOR` message have
`source_generation_id` pointing at a generation with
`trigger = 'GUIDED_SLOT_SELECTION'`, with at least one customer message
after it" — an existing, already-indexed relationship, not new
infrastructure. (An earlier draft of this document proposed matching
`draft_text` against `Message.body` by content/timing — unnecessary once
`source_generation_id` was checked; corrected during this feature's
pre-implementation cross-artifact review.)

`GENERATION.category_slug` remains `NULL` for both new trigger values —
`derive_category_slug()` (V3-1/V3-3/V3-4) is unchanged; a guided-selection
generation isn't grounded in any `content.qa_entries`/clinical-document
category, so leaving it uncategorized (already a valid, handled state
today — `teste_humano.md` §3.11 notes "sem categoria" as an explicit row,
never silently dropped) is correct, not a gap.

## 4. `resolve_appointment_availability` signature change

`plan.md` §5.1 requires the caller (`dynamic_pattern_result`) to persist
exactly the rows shown, so `resolve_appointment_availability` returns them
instead of only a `DynamicResolution`:

```python
def resolve_appointment_availability(session: Session, query_text: str) -> tuple[DynamicResolution, Sequence[_SlotRow]]:
    ...
    return DynamicResolution(...), rows
```

`resolve_price_lookup` (PL, `plan.md` §4) does **not** change shape — it
has nothing analogous to persist (a single price fact, not a set of
offers a customer will later refer back to). `NAMED_RESOLVERS`'s value
type widens to
`Callable[[DbSession, str], DynamicResolution | tuple[DynamicResolution, Sequence[Any]]]`,
and `dynamic_pattern_result` unpacks by `isinstance(result, tuple)` rather
than by hardcoding which resolver name returns which shape — implemented
this way instead of an earlier draft's name-based special-case (`qa.dynamic_resolver
== "appointment_availability"`), since checking the actual return shape
avoids repeating the resolver name as a magic string in two places and
keeps the dispatch code correct automatically if a future named resolver
also needs to persist something. This keeps the persistence-on-success
behavior scoped to whichever resolver actually returns a row set, without
forcing every named resolver to return one it has no use for.

## 5. No other schema change

Confirmed unaffected: `scheduling.*` (all tables, all columns),
`conversations.booking_script_step`, `messages.autonomous_source`, the
`messages_check` CHECK constraint, `content.qa_entries`'s column shape
(PM only updates row *values*, not columns), `content.qa_dynamic_bindings`,
`content.knowledge_dynamic_fixture`.

## 6. Migration summary

Two new, additive, forward-only Alembic migrations:

1. `NNNNNNNN_000X_create_appointment_offer_presentations.py` — §1's table
   plus its index and constraints.
2. `NNNNNNNN_000X_widen_ai_generations_trigger_check.py` — §3's CHECK
   constraint widening (`DROP CONSTRAINT` + `ADD CONSTRAINT`, the same
   technique 004 used for `messages_check`'s own narrow widening).

Exact filenames/timestamps assigned in `tasks.md` at implementation time,
per the project's existing Alembic numbering convention.
