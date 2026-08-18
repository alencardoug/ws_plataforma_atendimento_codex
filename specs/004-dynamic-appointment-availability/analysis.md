# Cross-Artifact Analysis: Dynamic Appointment Availability

## 1. Method

Read `spec.md`, `plan.md`, `data-model.md`, `tasks.md`, and `acceptance.md`
together; checked every cited table/column/function/constraint name in
`plan.md`/`data-model.md` against the real source
(`db/init/001_schema.sql`, `002_seed_and_schedule.sql`,
`app/customer_care/infrastructure/models.py`, `ai/router.py`,
`knowledge/dynamic_binding.py`), not from memory, matching V1/V2/V3's own
pre-implementation `analysis.md` method (`tasks.md` T001).

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

- **`BUSINESS_DAYS_AHEAD = 3` and the fixed slot hours are demo constants**,
  not derived from any real clinical scheduling policy — acceptable for
  this synthetic/demo system (Constitution Article VI) but should not be
  read as a realistic staffing model if this pattern is ever extended
  toward a real deployment.
- **The deterministic keyword vocabulary (`plan.md` §5) only covers the 3
  seeded specialties' known synonyms and a small set of Portuguese date/
  period phrases.** A customer phrasing outside that vocabulary simply
  gets no dimension filtered on (falls back to "all specialties, nearest
  available slots") rather than a wrong match — a safe default, but a real
  limitation worth knowing about, not a defect to fix now (`spec.md` §5
  resolution 1 explicitly chose this trade-off over building genuine NLU).
- **Q&A content cleanup's exact final entry list (Phase 5, T050) is
  deliberately left to implementation time**, not fixed here — the human
  explicitly prioritized evaluating against the real, working resolver over
  pre-deciding chunk wording (`spec.md` §5 resolution 3).

## 5. Verdict (pre-implementation)

No unresolved contradiction between `spec.md`, `plan.md`, `data-model.md`,
`tasks.md`, and `acceptance.md` as of this review; the one finding in §2 was
repaired in place before any implementation began.
`checklists/requirements.md`'s final item ("cross-artifact analysis reports
no material contradiction") is satisfied by this document. This feature is
ready to move from artifact authoring into `tasks.md` Phase 1
implementation, per `AGENTS.md`'s required SDD flow.
