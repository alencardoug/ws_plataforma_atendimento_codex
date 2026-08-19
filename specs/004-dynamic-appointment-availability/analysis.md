# Cross-Artifact Analysis: Dynamic Appointment Availability

## 1. Method

Read `spec.md`, `plan.md`, `data-model.md`, `tasks.md`, and `acceptance.md`
together; checked every cited table/column/function/constraint name in
`plan.md`/`data-model.md` against the real source
(`db/init/001_schema.sql`, `002_seed_and_schedule.sql`,
`app/customer_care/infrastructure/models.py`, `ai/router.py`,
`knowledge/dynamic_binding.py`), not from memory, matching V1/V2/V3's own
pre-implementation `analysis.md` method (`tasks.md` T001).

This document covers two review rounds the same day: §2-5 are the
*original* round (the query path still auto-generated near-future slots as
part of resolution); §6-7 are the *revision* round after the human's
second clarification split that into a read-only query path plus a
separate seed action. §5's verdict is superseded by §7's; §2's finding and
§3's checks remain valid facts about the schema/code, re-confirmed still
applicable in §6.

## 2. Findings and repairs

1. **`ensure_near_future_slots()`'s original pseudocode iterated every
   `professional_specialties` row regardless of `Professional.active`.**
   `data-model.md` §1 correctly lists `active` as a mapped field, but
   `plan.md` §4's slot-generation loop did not filter on it — a
   deactivated professional would still have kept getting new near-future
   slots generated and offered to customers, which is wrong (a deactivated
   professional should stop being schedulable, the same way `is_active`
   already gates every other entity's visibility in this codebase — `V1`
   knowledge-base soft-delete, `V3` category `is_active`). Caught before
   any code exists, per Constitution Article I ("specification precedes
   implementation... if implementation reveals a required behavioral
   change, update the spec/plan/tasks before continuing" — same principle
   applied one step earlier, during planning itself). Fixed in `plan.md` §4
   (the loop now joins through `Professional` and filters
   `active.is_(True)`) and reflected in `tasks.md` T030/T032.

## 3. Checks that passed without repair

- Every table/column/function `plan.md`/`data-model.md` cites
  (`scheduling.specialties`/`professionals`/`professional_specialties`/
  `units`/`schedule_slots`/`holidays`, `scheduling.next_business_day()`,
  the `UNIQUE (professional_id, starts_at)` constraint, the `slot_status`
  enum's `available`/`held`/`booked`/`blocked` values) was verified against
  the real `db/init/001_schema.sql` DDL and matches exactly.
- `content.qa_entries.dynamic_resolver` was verified as already
  ORM-mapped (`infrastructure/models.py:141`) and already write-only in
  application code (`knowledge/ingest.py`, confirmed no read site exists
  today) — `spec.md` §2's claim about the current gap is accurate, not
  assumed.
- The `dynamic_pattern_result()` dispatch change (`plan.md` §2) was checked
  against its two real call sites (`generate_draft()`, `select_evidence()`)
  — both already have a natural source of query text to pass through
  (`query` in the former, `RetrievalRun.query_text` via `hit.retrieval_run_id`
  in the latter), so no call site needs new input it doesn't already have
  access to.
- The fallthrough behavior for `dynamic_resolver` values this cycle does
  not implement (`price_lookup`/`payment_simulator`/`insurance_lookup`) was
  traced through `resolve_dynamic_pattern(session, qa)`'s existing code
  path: with no `qa_dynamic_bindings` row for any of them, it already
  raises `DynamicResolutionError` today — confirming `spec.md` acceptance
  outcome 8 and `plan.md` §2's claim that "no special-casing is needed."
- `data-model.md`'s claim that no Alembic migration is required was checked
  against the actual current schema — every column/constraint this feature
  reads or writes already exists.
- `acceptance.md`'s 9 lettered sections (A-J including quality gates) map
  1:1 onto `spec.md` §4's 9 numbered acceptance outcomes via
  `checklists/traceability.md` — no orphaned outcome, no acceptance section
  without a spec outcome behind it.

## 4. Residual risks / deferred decisions (not contradictions, but open)

- **(Superseded by §6) `TARGET_D1=1`/`TARGET_D7=3` and the 08:00-18:00
  seeding window are demo constants**, not derived from any real clinical
  scheduling policy — acceptable for this synthetic/demo system
  (Constitution Article VI) but should not be read as a realistic staffing
  model if this pattern is ever extended toward a real deployment.
- **The deterministic keyword vocabulary (`plan.md` §5) only covers the 3
  seeded specialties' known synonyms and a small set of Portuguese date/
  period phrases.** A customer phrasing outside that vocabulary simply
  gets no dimension filtered on (falls back to "all specialties, nearest
  available slots") rather than a wrong match — a safe default, but a real
  limitation worth knowing about, not a defect to fix now (`spec.md` §5
  resolution 1 explicitly chose this trade-off over building genuine NLU).
- **Q&A content cleanup's exact final entry list (Phase 7, T070) is
  deliberately left to implementation time**, not fixed here — the human
  explicitly prioritized evaluating against the real, working resolver over
  pre-deciding chunk wording (`spec.md` §5 resolution 3).

## 5. Verdict (first design, superseded — see §6)

No unresolved contradiction between `spec.md`, `plan.md`, `data-model.md`,
`tasks.md`, and `acceptance.md` as of this review; the one finding in §2 was
repaired in place before any implementation began. This verdict covered the
*original* design (query path auto-generates near-future slots as a side
effect of resolution). That design was superseded the same day by the
human's second clarification round — see §6.

## 6. Revision review — second clarification round (2026-08-18, same day)

The human split what had been one combined behavior into two: the query
path (AA-2) is now purely read-only, and a new, separate, explicit
operator-triggered seed action (AA-9) reinstates the D+1/D+7 rule with
exact idempotent semantics (1 slot on D+1, 3 on D+7, 08:00-18:00). All five
artifacts (`spec.md`, `plan.md`, `data-model.md`, `tasks.md`,
`acceptance.md`) and both checklists were rewritten for this split before
this re-review.

### Re-checked for the revision

- **No leftover reference to the old combined design.** Grepped for
  `ensure_near_future_slots` (the old function name) across all five
  artifacts after the rewrite — zero remaining references; every mention
  is now either `resolve_appointment_availability` (query, read-only) or
  `ensure_seed_availability`/`create_slots_on` (seed, the only write path).
- **The query path's "never writes" claim is independently testable, not
  just asserted.** `plan.md` §4/§9, `data-model.md` §1, and
  `acceptance.md` §C all describe the same structural test (grep/introspect
  `scheduling/availability.py` for write constructs and for an import of
  `scheduling/seeding.py`) — one verification method, stated consistently
  three times, not three different claims that could drift apart.
- **AA-9's flat (not per-specialty) counting was checked against `spec.md`
  §6's own new exclusion bullet** ("the seed action creating/counting
  slots for any specialty other than 'however many happen to exist'") —
  `plan.md` §4b's `count_available_on()`/`create_slots_on()` indeed count
  and create without any specialty filter, matching that exclusion exactly
  rather than silently reintroducing per-specialty semantics.
- **The new endpoint's route prefix was checked against the existing
  convention** (`knowledge/router.py`'s `/operator/knowledge` prefix
  pattern) and corrected in `plan.md` §4b during this review — the
  original pseudocode had the full path in the route decorator instead of
  using an `APIRouter(prefix=...)`, which every other operator router in
  this codebase uses. A documentation-only fix, caught before any code
  exists.
- **`Professional.active` filtering (§2 finding 1) still applies in the
  new location.** That logic now lives in `scheduling/seeding.py`'s
  `create_slots_on()`/`active_professional_specialty_pairs()` rather than
  the old `ensure_near_future_slots()` — re-confirmed present in `plan.md`
  §4b and reflected in `tasks.md` T040/T041.
- **`acceptance.md`'s now-11 lettered sections (A-K) map 1:1 onto `spec.md`
  §4's 10 numbered outcomes** via `checklists/traceability.md` (K is
  quality gates, not its own numbered outcome — consistent with V1/V2/V3's
  own pattern of an unnumbered quality-gates section) — no orphaned
  outcome, no section without an outcome behind it.
- **The frontend surface this revision adds (one button, one status line)
  was checked against `tasks.md`'s gate list** — Phase 6's gate now
  requires `eslint`/`tsc --noEmit`/`vitest`/`vite build`, and Phase 8's
  final gate was updated to include them too (the first design's plan
  explicitly said "no frontend gate applies," which is no longer true and
  has been corrected everywhere it was stated: `plan.md` §1/§13,
  `tasks.md` Phase 6/8 gates, `acceptance.md` §J/§K).

### New residual risk from this revision

- **The seed action's flat, specialty-agnostic count (1×D+1/3×D+7 total,
  not per-specialty) means a customer asking about a specific specialty
  could still get zero results even right after a successful seed call**,
  if all 4 seeded slots happened to land on a different specialty. This is
  the human's explicit, deliberate design choice (not a defect) — the seed
  button is described as guaranteeing "4 vagas disponíveis," not "4 vagas
  por especialidade." Worth knowing operationally (an operator demoing a
  specific specialty may need to check what actually got created), not
  worth fixing without a new instruction, since it would change the
  button's specified behavior.

## 7. Verdict (current)

No unresolved contradiction between `spec.md`, `plan.md`, `data-model.md`,
`tasks.md`, and `acceptance.md` as of this revised review; §2's finding and
§6's five re-checks/one fix are all repaired in place before any
implementation began. `checklists/requirements.md`'s final item
("cross-artifact analysis reports no material contradiction") is satisfied
by this document. This feature is ready to move from artifact authoring
into `tasks.md` Phase 1 implementation, per `AGENTS.md`'s required SDD
flow.
