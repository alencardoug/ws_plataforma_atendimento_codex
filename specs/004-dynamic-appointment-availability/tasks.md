# Tasks: Dynamic Appointment Availability

Execution rule: complete in dependency order. No task in this package writes
to `scheduling.appointments`/`appointment_events`, `identity.*`, or
`billing.*`, or implements `price_lookup`/`payment_simulator`/
`insurance_lookup` — those remain out of scope per `spec.md` §6. The query
path (`scheduling/availability.py`) never writes anything, under any
circumstance. There are exactly four places anything is written in this
feature: T009's one-time migration (seeding the new generalist specialty),
T090's one-time migration (the booking-script columns — both applied once
by Alembic, not a runtime code path), `scheduling/seeding.py` (reachable
only through the one new operator endpoint, Phase 4), and
`booking_script/service.py`'s `send_scripted_message()` (reachable only
through `advance_booking_script()`, Phase 9 — the one function in the
whole codebase authorized to send a customer-visible message without an
operator click, Constitution Amendment 1.1.0/D-031). No other task writes
anything.

Legend: `[P]` parallelizable after its listed dependency;
`[AA-x]` primary confirmed-outcome mapping (`spec.md` §3).

## Phase 0 — SDD gates

- [x] **T000** Read the constitution, `spec.md`, `plan.md`, `data-model.md`,
  V1/V2's own `plan.md`/`data-model.md` sections on the legacy `scheduling`
  schema, and the current `ai/router.py`/`knowledge/dynamic_binding.py`
  implementation this plan extends. Confirm every table/column/function
  name `plan.md` cites against the real `db/init/001_schema.sql`/
  `002_seed_and_schedule.sql` source, not from memory. Done during
  `plan.md`/`data-model.md` authoring — every cited name was confirmed
  against the real source, not guessed (`analysis.md` §3).
- [x] **T001** Run cross-artifact review of `spec.md` vs `plan.md` vs
  `data-model.md`; record findings/repairs in this package's `analysis.md`
  before implementation starts. Done 2026-08-18, revised three times more
  the same day: after the second round split the design into a read-only
  query path (AA-2, revised) and a new explicit operator-triggered seed
  action (AA-9); after the fourth round corrected "no specialty named" to
  mean a seeded generalist specialty (AA-3a); after the fifth round added
  AA-10 (the booking script) and, with it, Constitution Amendment 1.1.0 —
  `analysis.md` §10 covers this latest, largest revision, including a
  dedicated review of the autonomous-send exception's containment. 1
  finding repaired pre-revision (`Professional.active` filtering),
  re-confirmed still correct in the current `scheduling/seeding.py`.

**Gate:** `analysis.md`'s pre-implementation section shows no unresolved
contradiction. **Passed.**

## Phase 1 — Scheduling read model + generalist specialty [AA-2, AA-3a]

- [ ] **T009** New Alembic migration (`data-model.md` §5): seed the
  `oncologia-geral` generalist specialty, its 3 professionals, and their
  `professional_specialties` rows, exact values as specified. Data-only,
  forward-only, `downgrade()` raises (matching this codebase's convention).
- [ ] **T010** `app/customer_care/scheduling/__init__.py`,
  `scheduling/models.py` — `Specialty`, `Professional`,
  `ProfessionalSpecialty`, `Unit`, `ScheduleSlot` ORM classes
  (`data-model.md` §1). No schema migration for these — only T009's
  data-only one.
- [ ] **T011 [P]** Unit test: each class round-trips against the real
  seeded `scheduling` data (`SELECT` all 4 specialties — the original 3
  plus T009's new one — and all 12 professionals, confirm FK joins
  resolve) — proves the mapping is correct before anything is built on top
  of it.

**Gate:** backend `ruff`/`mypy`/`pytest`; migration applies cleanly on top
of the current database; T011 passes against the real local database.

## Phase 2 — Deterministic parameter extraction [AA-3, AA-3a]

- [ ] **T020** `scheduling/availability.py`: `GENERALIST_SLUG`,
  `SPECIALTY_KEYWORDS`, `DATE_KEYWORDS`, `PERIOD_KEYWORDS`,
  `extract_parameters(query_text) -> ExtractedParameters` (`plan.md` §5).
  Pure function, no database, no I/O. `specialty_slug` always resolves to
  a real slug — defaults to `GENERALIST_SLUG` when no diagnosis-specific
  keyword matches, never `None`/unfiltered.
- [ ] **T021 [P]** `test_appointment_availability_keywords.py` — every
  diagnosis-specific keyword; explicit generalist keywords; **a query with
  no known specialty keyword at all resolves to `GENERALIST_SLUG`**; mixed
  case; a realistic full customer sentence per specialty (matching the
  tone of the existing Q&A wording, e.g. "Tem vaga de mastologia amanhã de
  manhã?").

**Gate:** T021 passes; no database required for this phase's tests.

## Phase 3 — Query resolver, purely read-only [AA-1, AA-4, AA-5, AA-8]

- [ ] **T030** `scheduling/availability.py`:
  `resolve_appointment_availability(session, query_text) -> DynamicResolution`
  (`plan.md` §4) — a single `SELECT` against `schedule_slots` (joined to
  `Specialty`/`Professional`/`ProfessionalSpecialty`/`Unit`), always
  filtered by `extract_parameters()`'s (T020) resolved `specialty_slug`
  (never unfiltered), further narrowed by whatever date/period matched,
  rendering the deterministic template (`plan.md` §6), raising
  `DynamicResolutionError` (reusing `knowledge/dynamic_binding.py`'s
  existing exception type) on zero matches. **Contains no
  `INSERT`/`UPDATE`/`DELETE` statement and never imports
  `scheduling/seeding.py`** — this is the core invariant the human's
  second clarification round introduced.
- [ ] **T031 [P]** `test_appointment_availability_resolver.py` — real-
  database integration tests: specialty filter correctness for each of the
  4 seeded specialties (including the new generalist one, T009); **a query
  with no specialty keyword returns only the generalist's slots, never a
  mix of the other 3**; period (manhã/tarde) filter correctness;
  zero-match raises with a diagnostic (never customer-facing) cause;
  rendered text contains no raw table/column name; **a structural test
  asserts the `scheduling.availability` module source contains no
  `insert(`/`update(`/`delete(`/`pg_insert(` construct** (acceptance
  outcome 4).

**Gate:** T031 passes against the real local database; the structural
no-write test passes; rendered output spot-checked to contain no internal
implementation detail.

## Phase 4 — Seed action: the AA-9 write path [AA-9]

- [ ] **T040** `scheduling/seeding.py`: `ensure_seed_availability(session)
  -> SeedResult`, `count_available_on()`, `create_slots_on()` (`plan.md`
  §4b) — computes `d1`/`d7` via `scheduling.next_business_day()`, counts
  available slots on each, creates only what's missing (bounded to
  `1×D+1`/`3×D+7`) within 08:00-18:00, only for `active=true` professionals
  (`analysis.md` finding 1, re-applied here since this is now where that
  logic lives).
- [ ] **T041 [P]** `test_appointment_seeding.py` — real-database
  integration tests: from zero, creates exactly 1×D+1/3×D+7 within
  08:00-18:00; a second immediate call creates zero more and reports
  `already_sufficient=True`; a partial state creates exactly what's
  missing; a deactivated professional never receives a generated slot;
  D+1/D+7 correctly skip Sunday/holidays via `next_business_day()`;
  concurrent calls never exceed the target (`data-model.md` §4).
- [ ] **T042** `scheduling/router.py`: `POST
  /operator/scheduling/ensure-availability` (`CurrentOperator`-gated, not
  conversation-scoped) calling T040, emitting the new
  `scheduling.availability_seeded` audit event, returning the exact
  Portuguese message the human specified ("Já tem 4 vagas disponíveis." /
  a created-count message). Registered in `bootstrap.py`.
- [ ] **T043 [P]** `EVENT_CATALOG.md` gains one new row for
  `scheduling.availability_seeded`. `contracts/openapi.yaml` (new file for
  this package) documents the one new route.

**Gate:** backend `ruff`/`mypy`/`pytest`; T041 passes; live HTTP
verification against a rebuilt backend container: calling the endpoint
from zero creates exactly 4 slots (1+3), a second call is a no-op with the
exact specified message, and an anonymous/customer-token credential gets
`401`.

## Phase 5 — Wire the query path into `ai/router.py` [AA-1]

- [ ] **T050** `dynamic_pattern_result()` gains the `NAMED_RESOLVERS`
  dispatch and a `query_text` parameter (`plan.md` §2); both call sites
  (`generate_draft()`, `select_evidence()`) updated to pass the right text
  (joined selected-message-bodies+manual-search-text, and the originating
  `RetrievalRun.query_text`, respectively).
- [ ] **T051** `ai.dynamic_pattern_resolved`'s audit payload gains optional
  `specialty_slug`/`slot_count` when the resolver used is
  `appointment_availability` (`plan.md` §7); `EVENT_CATALOG.md` gains a
  note, not a new row (distinct from T043's new row for the seed event).
- [ ] **T052 [P]** Regression: `smoke_v2_dynamic_pattern.py` and its
  `qa_dynamic_bindings`-based fixture still pass unmodified — the
  fallthrough for entries with no `dynamic_resolver` set is unaffected.
  Also confirm a QA entry with `dynamic_resolver` set to an
  **unimplemented** name (`price_lookup` etc., no `NAMED_RESOLVERS` entry,
  no `qa_dynamic_bindings` row) still abstains exactly as before — this is
  the acceptance outcome 8 regression proof.

**Gate:** backend `ruff`/`mypy`/`pytest`; T052 passes; live HTTP
verification: a real customer message naming a specialty and day, against
data seeded by Phase 4's endpoint, produces a real, deterministic,
non-LLM answer.

## Phase 6 — Operator-workspace button [AA-9 UI]

- [ ] **T060** `frontend/src/main.tsx`: one new button + `aria-live`
  status line in `OperatorPage`, outside the `{selected ? ... : ...}`
  conditional (usable with no conversation selected), calling Phase 4's
  endpoint and displaying its returned `message` (`plan.md` §4b).
- [ ] **T061 [P]** `frontend/src/main.test.tsx`: click calls the endpoint,
  renders the returned message, works with no conversation selected, and
  (mocking a second, no-op response) shows the exact idempotent message.

**Gate:** frontend `eslint`/`tsc --noEmit`/`vitest`/`vite build` all pass;
live Playwright/manual verification against the rebuilt containers: click
the button twice, see the created-count message then the idempotent
"já tem 4 vagas disponíveis" message.

## Phase 7 — Q&A content cleanup [spec.md §5 item 3]

- [ ] **T070** Evaluate each of the 14 seeded `agenda` entries against the
  resolver actually built in Phases 1-5. Soft-deactivate
  (`is_active = false`, via the existing operator CRUD endpoint) any entry
  describing behavior this feature does not implement (booking, holds,
  identity, payment confirmation — expected to be the 5 identified in
  `spec.md` §5 item 3, but re-evaluate rather than assuming the list is
  final). Create/edit the in-scope entries as needed so retrieval reliably
  matches real customer phrasings per specialty/day/period. **Also seed the
  2 new "primeira consulta" (generalist) entries authored verbatim in
  `plan.md` §8**, after T009's migration has run (human-identified coverage
  gap, 2026-08-18: no existing entry covers a customer who suspects cancer
  but doesn't yet know which specialty applies — corrected same day to
  route to the new seeded generalist specialty, not an unfiltered search)
  — confirm neither entry's wording matches any of the 3
  diagnosis-specific `SPECIALTY_KEYWORDS` terms, so both correctly resolve
  to `GENERALIST_SLUG`. Record the final entry list and rationale for
  every change in this task's evidence.
- [ ] **T071 [P]** `smoke_v4_appointment_availability.py` — real
  end-to-end HTTP smoke against the rebuilt containers: call the seed
  endpoint (Phase 4) to guarantee real data exists, then a real customer
  message, `ANSWER` status, `model == "not-applicable"`, real (synthetic)
  slot data in `draft_text`, confirm no LLM provider call occurred, confirm
  `price_lookup`/`payment_simulator`/`insurance_lookup` entries (if any
  remain seeded) still abstain.

**Gate:** T071 passes; the full pre-existing `smoke_*` suite (V1/V2/V3, per
`specs/003-v3-measured-n2/tasks.md`'s own T121 precedent) still passes
unmodified — this feature must not regress anything.

## Phase 8 — Booking-script foundation [AA-10]

This phase and Phase 9 implement the one exception to Constitution Article
III (Amendment 1.1.0, `DECISIONS.md` D-031) — extra scrutiny applies to
every task here, matching `plan.md` §8b/§13's own emphasis.

- [ ] **T090** New Alembic migration (`data-model.md` §7):
  `conversations.booking_script_step` and `messages.autonomous_source`,
  both nullable `text` with a `CHECK` constraint enumerating their only
  legal values at the database level. Additive, forward-only,
  `downgrade()` raises.
- [ ] **T091** `app/customer_care/booking_script/__init__.py`,
  `parsing.py` — `extract_cpf()` (Pydantic-validated, digit-count-only,
  never the real CPF algorithm), `extract_payment_confirmation()`
  (word-boundary sim/não regex), `detect_booking_intent()` (`plan.md`
  §8b). Pure functions, no database, no I/O.
- [ ] **T092 [P]** `test_booking_script_parsing.py` — the human's own two
  CPF examples and two payment examples verbatim, plus every case
  `plan.md` §10 lists (10/11/12-digit inputs, sim/não case variants, a
  message matching neither or both, booking-intent positive/negative).

**Gate:** backend `ruff`/`mypy`/`pytest`; migration applies cleanly;
T092 passes with no database required.

## Phase 9 — Booking-script service, wiring, and containment [AA-10]

- [ ] **T093** `booking_script/service.py`: `send_scripted_message()` (the
  one function in the codebase allowed to create a customer-visible
  `Message` with no operator-auth dependency, `plan.md` §8b),
  `advance_booking_script()` (the state machine), `has_recent_resolved_availability()`,
  `lookup_recent_specialty_price()`. Every send emits
  `booking_script.autonomous_message_sent` (`data-model.md` §8) — no raw
  CPF/payment-reply text in the payload, ever.
- [ ] **T094** `anonymous_access/router.py`'s `send_customer_message()`
  gains the one call to `advance_booking_script()`, in the same
  transaction, before `session.commit()` (`plan.md` §8b "Trigger"). Not
  wired into the typing-heartbeat endpoint or any GET/poll path.
- [ ] **T095 [P]** `test_booking_script_flow.py` — real-database
  integration tests: the full happy-path script verbatim; the
  invalid-CPF-then-valid branch; the não-then-sim branch (question
  repeats verbatim); no prior resolved availability → script never
  starts; a second booking-intent message after a completed flow starts a
  fresh one; every sent message carries `autonomous_source =
  "booking_script"` and its audit event; the raw CPF and payment answer
  are absent from every table afterward.
- [ ] **T096 [P]** `test_booking_script_containment.py` — the structural
  negative test (`plan.md` §9/§13): every other
  `Message(author_type="OPERATOR", ...)` construction site in the
  codebase is reached only through an authenticated-operator dependency;
  `send_scripted_message` is imported only within `booking_script/`.
- [ ] **T097 [P]** `docs/architecture/EVENT_CATALOG.md` gains the new
  `booking_script.autonomous_message_sent` row, flagged prominently as
  the one event type marking a non-operator-gated send.
  `smoke_v4_booking_script.py` — real end-to-end HTTP smoke: real
  availability resolution, a real booking-intent customer message, the
  script's messages appear with zero operator action, full CPF/payment
  happy path via real customer message posts, confirm the exact final
  message, confirm no `identity.*`/`billing.*`/`scheduling.appointments`
  row was ever created.
- [ ] **T098 [P, optional]** `frontend/src/main.tsx`: a small visual
  marker (e.g. "automático") on messages with `autonomous_source` set, so
  an operator can tell at a glance which messages they didn't send
  themselves — a transparency nice-to-have, not required by any
  acceptance outcome (`plan.md` §12).

**Gate:** backend `ruff`/`mypy`/`pytest`; T095/T096 pass; live HTTP
verification against a rebuilt backend container reproduces the human's
exact script, including both retry branches; the containment test
(T096) passes, proving the exception has not spread beyond
`booking_script/`.

## Phase 10 — Acceptance automation and DONE

- [ ] **T080** Write `acceptance.md` covering `spec.md` §4's 15 acceptance
  outcomes as executable scenarios, following V1/V2/V3's Execution-record
  format.
- [ ] **T081** `checklists/{requirements,security,traceability}.md`
  finalized against the implemented state.
- [ ] **T082** `analysis.md` — final post-implementation cross-artifact
  convergence review (spec/plan/data-model/tasks/acceptance), following
  V2 §6 / V3 §6's method: diff against the real implementation, not just
  against each other. **Explicitly re-verify AA-10's containment** — the
  autonomous-send exception must be provably scoped to exactly one
  function, reachable from exactly one trigger. Update
  `PROJECT_STATE.md`/`ROADMAP.md`/`DECISIONS.md` to record this feature's
  closure (and D-031's move from "specification pending" to
  "implemented").

**Gate:** backend `ruff`/`mypy`/`pytest`; frontend
`eslint`/`tsc --noEmit`/`vitest`/`vite build` (this feature now has a real
frontend surface, unlike the first plan draft — Phase 6's button, and
optionally Phase 9's badge); the full `smoke_*` suite (pre-existing + this
feature's new scripts) all pass; `acceptance.md`'s Execution record covers
all 15 `spec.md` §4 outcomes.

## Dependency summary

```text
Phase 0 (SDD gates)
  -> Phase 1 (migration + scheduling read model)
  -> Phase 2 (parameter extraction) [P, independent of Phase 1 — GENERALIST_SLUG
       is a Python constant, not a DB lookup; only Phase 3's query and Phase 7's
       Q&A seeding actually need T009's migration to have run]
  -> Phase 3 (query resolver, read-only, needs Phase 1 + Phase 2)
  -> Phase 4 (seed action, one of two write paths, needs Phase 1)
       [P, independent of Phase 3 — different files, disjoint concerns]
  -> Phase 5 (wire query path into ai/router.py, needs Phase 3)
  -> Phase 6 (operator button, needs Phase 4's endpoint to exist)
  -> Phase 7 (Q&A content cleanup, needs Phase 5 + Phase 6 working end-to-end
       so the demo has real data to answer from)
  -> Phase 8 (booking-script foundation: migration + parsing, needs Phase 1
       for scheduling models the price lookup will need in Phase 9)
  -> Phase 9 (booking-script service + wiring, needs Phase 8 + Phase 5
       working end-to-end — advance_booking_script's
       has_recent_resolved_availability() reads real AA-1..AA-9 generations)
  -> Phase 10 (acceptance automation + DONE)
```
