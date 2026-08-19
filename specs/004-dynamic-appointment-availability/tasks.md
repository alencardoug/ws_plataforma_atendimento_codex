# Tasks: Dynamic Appointment Availability

Execution rule: complete in dependency order. No task in this package writes
to `scheduling.appointments`/`appointment_events`, `identity.*`, or
`billing.*`, or implements `price_lookup`/`payment_simulator`/
`insurance_lookup` — those remain out of scope per `spec.md` §6. The query
path (`scheduling/availability.py`) never writes anything, under any
circumstance — the only write path in this entire feature is
`scheduling/seeding.py`, reachable only through the one new operator
endpoint (Phase 4).

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
  before implementation starts. Done 2026-08-18, revised same day after the
  human's second clarification round split the design into a read-only
  query path (AA-2, revised) and a new explicit operator-triggered seed
  action (AA-9) — `analysis.md` updated to review the revised design, not
  just the original one; 1 finding repaired pre-revision
  (`Professional.active` filtering), re-confirmed still correct in the
  revised `scheduling/seeding.py`.

**Gate:** `analysis.md`'s pre-implementation section shows no unresolved
contradiction. **Passed.**

## Phase 1 — Scheduling read model [AA-2]

- [ ] **T010** `app/customer_care/scheduling/__init__.py`,
  `scheduling/models.py` — `Specialty`, `Professional`,
  `ProfessionalSpecialty`, `Unit`, `ScheduleSlot` ORM classes
  (`data-model.md` §1). No migration.
- [ ] **T011 [P]** Unit test: each class round-trips against the real
  seeded `scheduling` data (`SELECT` the 3 seeded specialties, 9
  professionals, confirm FK joins resolve) — proves the mapping is correct
  before anything is built on top of it.

**Gate:** backend `ruff`/`mypy`/`pytest`; T011 passes against the real
local database.

## Phase 2 — Deterministic parameter extraction [AA-3]

- [ ] **T020** `scheduling/availability.py`: `SPECIALTY_KEYWORDS`,
  `DATE_KEYWORDS`, `PERIOD_KEYWORDS`, `extract_parameters(query_text) ->
  ExtractedParameters` (`plan.md` §5). Pure function, no database, no I/O.
- [ ] **T021 [P]** `test_appointment_availability_keywords.py` — every
  keyword, mixed case, no-match-on-any-dimension, and a realistic full
  customer sentence per specialty (matching the tone of the existing Q&A
  wording, e.g. "Tem vaga de mastologia amanhã de manhã?").

**Gate:** T021 passes; no database required for this phase's tests.

## Phase 3 — Query resolver, purely read-only [AA-1, AA-4, AA-5, AA-8]

- [ ] **T030** `scheduling/availability.py`:
  `resolve_appointment_availability(session, query_text) -> DynamicResolution`
  (`plan.md` §4) — a single `SELECT` against `schedule_slots` (joined to
  `Specialty`/`Professional`/`ProfessionalSpecialty`/`Unit`), filtered by
  whatever `extract_parameters()` (T020) matched, rendering the
  deterministic template (`plan.md` §6), raising `DynamicResolutionError`
  (reusing `knowledge/dynamic_binding.py`'s existing exception type) on
  zero matches. **Contains no `INSERT`/`UPDATE`/`DELETE` statement and
  never imports `scheduling/seeding.py`** — this is the core invariant the
  human's second clarification round introduced.
- [ ] **T031 [P]** `test_appointment_availability_resolver.py` — real-
  database integration tests: specialty filter correctness; period
  (manhã/tarde) filter correctness; zero-match raises with a diagnostic
  (never customer-facing) cause; rendered text contains no raw
  table/column name; **a structural test asserts the
  `scheduling.availability` module source contains no
  `insert(`/`update(`/`delete(`/`pg_insert(` construct** (acceptance
  outcome 4).

**Gate:** T031 passes against the real local database; the structural
no-write test passes; rendered output spot-checked to contain no internal
implementation detail.

## Phase 4 — Seed action: the only write path [AA-9]

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
  matches real customer phrasings per specialty/day/period. Record the
  final entry list and rationale for every change in this task's evidence.
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

## Phase 8 — Acceptance automation and DONE

- [ ] **T080** Write `acceptance.md` covering `spec.md` §4's 10 acceptance
  outcomes as executable scenarios, following V1/V2/V3's Execution-record
  format.
- [ ] **T081** `checklists/{requirements,security,traceability}.md`
  finalized against the implemented state.
- [ ] **T082** `analysis.md` — final post-implementation cross-artifact
  convergence review (spec/plan/data-model/tasks/acceptance), following
  V2 §6 / V3 §6's method: diff against the real implementation, not just
  against each other. Update `PROJECT_STATE.md`/`ROADMAP.md`/`DECISIONS.md`
  to record this feature's closure.

**Gate:** backend `ruff`/`mypy`/`pytest`; frontend
`eslint`/`tsc --noEmit`/`vitest`/`vite build` (this feature now has a real
frontend surface, unlike the first plan draft — Phase 6's button); the
full `smoke_*` suite (pre-existing + this feature's new script) all pass;
`acceptance.md`'s Execution record covers all 10 `spec.md` §4 outcomes.

## Dependency summary

```text
Phase 0 (SDD gates)
  -> Phase 1 (scheduling read model)
  -> Phase 2 (parameter extraction) [P, independent of Phase 1]
  -> Phase 3 (query resolver, read-only, needs Phase 1 + Phase 2)
  -> Phase 4 (seed action, the only write path, needs Phase 1)
       [P, independent of Phase 3 — different files, disjoint concerns]
  -> Phase 5 (wire query path into ai/router.py, needs Phase 3)
  -> Phase 6 (operator button, needs Phase 4's endpoint to exist)
  -> Phase 7 (Q&A content cleanup, needs Phase 5 + Phase 6 working end-to-end
       so the demo has real data to answer from)
  -> Phase 8 (acceptance automation + DONE)
```
