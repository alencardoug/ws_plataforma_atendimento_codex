# Data Model: Appointment-Availability Continuity + Operator Booking-Offer Action

Confirmed against the live local database (`docker exec … psql`), not
assumed.

## 1. `customer_service.system_settings` — one new column

```sql
ALTER TABLE customer_service.system_settings
    ADD COLUMN availability_floor_checked_at timestamptz NULL;
```

- Nullable, no default. `NULL` means "the low-water-mark check has never
  run" — `ensure_generalist_floor()` treats that as "run now" (its time
  gate is `last is not None and (now - last) < interval`).
- Not operator-settable — it is written only by `ensure_generalist_floor()`
  itself. It is **not** added to `autonomy_settings_dict()` /
  `SetAutonomySettingsIn` (it is bookkeeping, not policy).
- Current `system_settings` columns (for reference, live schema): `id`,
  `autonomy_window_seconds`, `autonomy_kill_switch_enabled`, `updated_at`,
  `updated_by_operator_id`, `n5_kill_switch_enabled`,
  `automatic_trigger_idle_seconds`. This cycle adds exactly one more.

ORM (`infrastructure/models.py`, `SystemSettings`):

```python
availability_floor_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

## 2. `customer_service.ai_generations.trigger` — widen the single CHECK

Live constraint (verified):

```
ai_generations_trigger_check CHECK (trigger = ANY (ARRAY[
  'AUTOMATIC','MANUAL_DRAFT','MANUAL_EVIDENCE',
  'GUIDED_SLOT_SELECTION','GUIDED_CONFIRMATION','GUIDED_CPF_CONFIRMED',
  'GUIDED_BOOKING_COMPLETE','GUIDED_SLOT_RESELECTION']))
```

There is **exactly one** CHECK constraint on this column (unlike
`messages.autonomous_source`, which feature 010 found had two). Migration:

```sql
ALTER TABLE customer_service.ai_generations DROP CONSTRAINT ai_generations_trigger_check;
ALTER TABLE customer_service.ai_generations ADD CONSTRAINT ai_generations_trigger_check CHECK (
    trigger IN (
        'AUTOMATIC','MANUAL_DRAFT','MANUAL_EVIDENCE',
        'GUIDED_SLOT_SELECTION','GUIDED_CONFIRMATION','GUIDED_CPF_CONFIRMED',
        'GUIDED_BOOKING_COMPLETE','GUIDED_SLOT_RESELECTION',
        'MANUAL_BOOKING_OFFER'
    )
);
```

`downgrade()` restores the prior 8-value list (safe: no
`MANUAL_BOOKING_OFFER` rows can exist at downgrade time in any environment
that also reverts the code).

No ORM change — `AIGeneration.trigger` is already `Mapped[str]` free text.

### Why `MANUAL_BOOKING_OFFER` and not a reused value

- **not `AUTOMATIC`** — `maybe_open_autonomous_window()` gates autonomous
  send on `trigger == "AUTOMATIC"` (or a GB flow trigger). A manually
  requested draft must never be autonomously sendable (Constitution
  Amendment 1.2.0 clause (b)). A distinct value makes that structural,
  not conditional.
- **not `MANUAL_DRAFT` / `MANUAL_EVIDENCE`** — those already carry
  behavior in `classify_generation()` (`MANUAL_EVIDENCE` → the `search`
  tag) and in the "regenerate" chain logic in `draft()`. OB is neither a
  free-text search nor a regenerate; a new value keeps the taxonomy
  honest and greppable.
- **not a `GUIDED_*` value** — those are GB-flow state markers consumed by
  `guided_booking.py`'s `_GB_ALL_FLOW_TRIGGERS` and by
  `_N5_ELIGIBLE_GB_TRIGGERS`; reusing one would make an OB generation
  falsely eligible for N5 autonomous send and would confuse GB's
  own "is the flow still pending" queries.

## 3. `ai_generations` rows OB produces

| field | ANSWER case | ABSTAIN case |
|---|---|---|
| `status` | `ANSWER` | `ABSTAIN` |
| `draft_text` | `resolution.pattern_text` (the rendered offer block) | `""` |
| `abstention_reason` | `NULL` | `DYNAMIC_DATA_UNAVAILABLE` |
| `provider` | `dynamic-pattern-resolver` | `dynamic-pattern-resolver` |
| `model` | `not-applicable` | `not-applicable` |
| `trigger` | `MANUAL_BOOKING_OFFER` | `MANUAL_BOOKING_OFFER` |
| `dynamic_pattern_used` | `true` | `false` |
| `retrieval_run_id` | the real `retrieve()` run for this call | same |
| `operator_id` | the requesting operator | same |
| `triggering_message_id` | last trailing customer message id, or `NULL` | same |
| `prior_generation_id` | `NULL` (OB is not a regenerate) | `NULL` |
| `category_slug` | `derive_category_slug()` result (usually `agenda`) | `NULL` |
| `prompt_version` | `not-applicable` | `not-applicable` |

- `AIGenerationSource`: on ANSWER, one row `use_order=1` to the evidence
  item whose `matched_qa_id` is an `appointment_availability` QA **iff**
  that hit is present in the retrieval run's top-k; otherwise none (the
  resolution is still valid — attribution is best-effort, matching how a
  dynamic resolution behaves today when its QA is not rank-1). On ABSTAIN:
  none.
- `AppointmentOfferPresentation`: on ANSWER, one row per offered slot via
  the existing `persist_presented_offers()` — identical to a
  resolver-driven offer, so `interpret_slot_choice()` (005/GB-1) works on
  the customer's next reply with zero change.

## 4. `schedule_slots` — no schema change

AC reuses the existing table and the existing `seeding.py` insert paths
(`create_slots_on()`, `create_wide_slots_on()` via
`ensure_wide_availability()`), all already `ON CONFLICT DO NOTHING` on
`(professional_id, starts_at)`. No new column, index, or constraint.

## 5. New audit event types (Article IX)

Registered in `docs/architecture/EVENT_CATALOG.md`:

| Event | `actor_type` | Payload |
|---|---|---|
| `scheduling.availability_bootstrap_seeded` | `SYSTEM` | `wide_slots_created`, `specialty_count`, `business_day_count`, `generalist_d1_created`, `generalist_d7_created` — emitted once per `run_bootstrap_seed()` call (startup hook or `python -m`). Not conversation-scoped. |
| `scheduling.availability_floor_topped_up` | `SYSTEM` | `before` (`{date: count}` for D+1 and D+7), `created`, `target`, `min` — emitted by `ensure_generalist_floor()` **only when it actually created slots**. A no-op check emits nothing. Not conversation-scoped. |

Neither payload carries any message body, CPF, or customer content
(Article VI). Existing `scheduling.availability_seeded` /
`scheduling.wide_availability_seeded` (the operator buttons) are
unchanged — the bootstrap event is deliberately distinct so an auditor
can tell "seeded at stack startup" from "an operator clicked the button".

## 6. No other schema change

- No new tables.
- `pending_autonomous_sends` — untouched. OB never creates a row here
  (its trigger is not autonomous-eligible); AC never touches it.
- `messages` — untouched. OB creates no `messages` row; the operator's
  ordinary send does that afterward through the existing path.
- `content.categories`, `qa_entries`, `qa_dynamic_bindings` — untouched.
  The `appointment_availability` binding on QA-011/012/087/088 etc. is
  already correct in the live DB (verified: `dynamic_data_required = t`,
  `dynamic_resolver = 'appointment_availability'`, embeddings present).
