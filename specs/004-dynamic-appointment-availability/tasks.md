# Tasks: Dynamic Appointment Availability

Execution rule: complete in dependency order. No task in this package writes
to `scheduling.appointments`/`appointment_events`, `identity.*`, or
`billing.*`, or implements `price_lookup`/`payment_simulator`/
`insurance_lookup` — those remain out of scope per `spec.md` §6.

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
  before implementation starts. Done 2026-08-18 (`analysis.md`, 1 finding
  repaired: `ensure_near_future_slots()` did not filter on
  `Professional.active`, fixed in `plan.md` §4 before any code existed).

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

## Phase 3 — Slot-ensure and resolver [AA-2, AA-4, AA-5, AA-8]

- [ ] **T030** `scheduling/availability.py`: `ensure_near_future_slots()`
  (`plan.md` §4) — idempotent insert against `schedule_slots` for the next
  `BUSINESS_DAYS_AHEAD` business days, reusing
  `scheduling.next_business_day()` via a scalar SQL call. Only
  `active=true` professionals are considered (`plan.md` §4,
  `analysis.md` finding 1).
- [ ] **T031** `resolve_appointment_availability(session, query_text) ->
  DynamicResolution` — calls T030, queries filtered slots, renders the
  deterministic template (`plan.md` §6), raises `DynamicResolutionError`
  (reusing `knowledge/dynamic_binding.py`'s existing exception type) on zero
  matches.
- [ ] **T032 [P]** `test_appointment_availability_resolver.py` — real-
  database integration tests: idempotency of T030 (call twice, same row
  count); a deactivated professional (`active=false`) never gets new slots
  generated; specialty filter correctness; Saturday-hours-only correctness;
  Sunday/holiday date phrase resolves via `next_business_day()`; zero-match
  raises with a diagnostic (never customer-facing) cause; rendered text
  contains no raw table/column name.

**Gate:** T032 passes against the real local database; rendered output
spot-checked to contain no internal implementation detail.

## Phase 4 — Wire into `ai/router.py` [AA-1]

- [ ] **T040** `dynamic_pattern_result()` gains the `NAMED_RESOLVERS`
  dispatch and a `query_text` parameter (`plan.md` §2); both call sites
  (`generate_draft()`, `select_evidence()`) updated to pass the right text
  (joined selected-message-bodies+manual-search-text, and the originating
  `RetrievalRun.query_text`, respectively).
- [ ] **T041** `ai.dynamic_pattern_resolved`'s audit payload gains optional
  `specialty_slug`/`slot_count` when the resolver used is
  `appointment_availability` (`plan.md` §7); `EVENT_CATALOG.md` gains a
  note, not a new row.
- [ ] **T042 [P]** Regression: `smoke_v2_dynamic_pattern.py` and its
  `qa_dynamic_bindings`-based fixture still pass unmodified — the
  fallthrough for entries with no `dynamic_resolver` set is unaffected.
  Also confirm a QA entry with `dynamic_resolver` set to an
  **unimplemented** name (`price_lookup` etc., no `NAMED_RESOLVERS` entry,
  no `qa_dynamic_bindings` row) still abstains exactly as before — this is
  the acceptance outcome 8 regression proof.

**Gate:** backend `ruff`/`mypy`/`pytest`; T042 passes; live HTTP
verification against a rebuilt backend container: a real customer message
naming a specialty and day produces a real, deterministic, non-LLM answer.

## Phase 5 — Q&A content cleanup [spec.md §5.3, §8]

- [ ] **T050** Evaluate each of the 14 seeded `agenda` entries against the
  resolver actually built in Phases 1-4. Soft-deactivate
  (`is_active = false`, via the existing operator CRUD endpoint) any entry
  describing behavior this feature does not implement (booking, holds,
  identity, payment confirmation — expected to be the 5 identified in
  `spec.md` §5.3, but re-evaluate rather than assuming the list is final).
  Create/edit the in-scope entries as needed so retrieval reliably matches
  real customer phrasings per specialty/day/period. Record the final entry
  list and rationale for every change in this task's evidence.
- [ ] **T051 [P]** `smoke_v4_appointment_availability.py` — real end-to-end
  HTTP smoke against the rebuilt containers: a real customer message,
  `ANSWER` status, `model == "not-applicable"`, real (synthetic) slot data
  in `draft_text`, confirm no LLM provider call occurred, confirm
  `price_lookup`/`payment_simulator`/`insurance_lookup` entries (if any
  remain seeded) still abstain.

**Gate:** T051 passes; the full pre-existing `smoke_*` suite (V1/V2/V3, per
`specs/003-v3-measured-n2/tasks.md`'s own T121 precedent) still passes
unmodified — this feature must not regress anything.

## Phase 6 — Acceptance automation and DONE

- [ ] **T060** Write `acceptance.md` covering `spec.md` §4's 9 acceptance
  outcomes as executable scenarios, following V1/V2/V3's Execution-record
  format.
- [ ] **T061** `checklists/{requirements,security,traceability}.md`
  finalized against the implemented state.
- [ ] **T062** `analysis.md` — final post-implementation cross-artifact
  convergence review (spec/plan/data-model/tasks/acceptance), following
  V2 §6 / V3 §6's method: diff against the real implementation, not just
  against each other. Update `PROJECT_STATE.md`/`ROADMAP.md`/`DECISIONS.md`
  to record this feature's closure.

**Gate:** backend `ruff`/`mypy`/`pytest`; the full `smoke_*` suite
(pre-existing + this feature's new script) all pass; `acceptance.md`'s
Execution record covers all 9 `spec.md` §4 outcomes. **This feature has no
frontend surface** — no `eslint`/`tsc`/`vitest`/`vite build`/Playwright gate
applies (`plan.md` §13: no new endpoint, no new frontend change); a spot
check that the existing operator evidence view renders this resolver's
output correctly (it is ordinary `draft_text`, nothing new to render) is
sufficient and does not require a new `*.spec.ts` file.

## Dependency summary

```text
Phase 0 (SDD gates)
  -> Phase 1 (scheduling read model)
  -> Phase 2 (parameter extraction) [P, independent of Phase 1]
  -> Phase 3 (slot-ensure + resolver, needs Phase 1 + Phase 2)
  -> Phase 4 (wire into ai/router.py, needs Phase 3)
  -> Phase 5 (Q&A content cleanup, needs Phase 4 working end-to-end)
  -> Phase 6 (acceptance automation + DONE)
```
