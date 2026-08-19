# Dynamic Appointment Availability Acceptance Protocol

This is the executable definition of DONE for this feature, supplementary to
`spec.md` §4. It extends V1/V2/V3's own acceptance packages (unchanged) and
does not repeat scenarios this feature leaves untouched. Revised 2026-08-18
same day as the spec's second clarification round — the query path (§A-C)
and the seed action (§D-F) are now two clearly separated pieces with
different triggers and different write permissions.

## A. Deterministic, real-data answer [AA-4, AA-5, outcome 1]

1. As an operator, generate a draft against a customer message matching one
   of the in-scope `agenda` Q&A entries; verify the resulting generation has
   `status = ANSWER`, `model = "not-applicable"`, `dynamic_pattern_used =
   true`, and `draft_text` containing real (synthetic) slot data — specialty
   display name, professional name, unit, a real future date/time in
   `America/Sao_Paulo`, price, and a "(simulação)" marker.
2. Confirm no LLM/embedding provider call occurred for this generation
   (provider mock/spy records zero invocations, or `duration_ms` is
   consistent with a pure-database resolution).

## B. Specialty filtering [AA-3, outcome 2]

1. A message naming a real specialty (e.g. "mastologia") returns only that
   specialty's slots.
2. A message naming no specialty returns slots across all seeded
   specialties with availability.
3. A message naming a specialty with no seeded professional/availability
   falls through to §F (abstain), never a wrong specialty's slots.
4. The two "primeira consulta" entries (`spec.md` §5 item 9, `plan.md`
   §8) — deliberately naming no specialty — resolve via the same
   all-specialties path as B.2, not a dedicated code path of their own.

## C. Query path is purely read-only [AA-2, outcome 4]

1. Static/structural check: `scheduling/availability.py`'s source contains
   no `insert(`/`update(`/`delete(`/`pg_insert(` construct, and does not
   import `scheduling/seeding.py`.
2. Live check: exercise the query path repeatedly (including against zero
   matching slots) and confirm `schedule_slots`'s row count is unchanged
   before/after — the query path cannot ever be the cause of a new row,
   even indirectly.

## D. Seed action: idempotent D+1/D+7 target [AA-9, outcome 5]

1. Starting from zero seeded slots on the computed `d1`/`d7` dates, one call
   to the seed endpoint creates exactly 1 slot on `d1` and 3 on `d7`, all
   within 08:00-18:00 `America/Sao_Paulo`, and reports the created counts.
2. A second immediate call makes zero further writes and reports exactly
   "Já tem 4 vagas disponíveis." (the literal message the human specified).
3. A partial state (e.g. `d1` already has 1, `d7` has only 1 of 3) results
   in creating exactly the 2 missing `d7` slots and none on `d1`, and the
   reported message reflects only what was actually created.
4. Two concurrent calls never together exceed the 1×D+1/3×D+7 target
   (`data-model.md` §4) — verified by issuing them concurrently in a test
   and asserting the final count is exactly at target, not over.

## E. Seed action: business-day and business-hours correctness [AA-9, outcome 5]

1. `d1`/`d7` are computed via the existing `scheduling.next_business_day()`
   — if the naive `today + 1`/`today + 7` date is a Sunday or holiday, the
   actual seeded date is the correct next business day.
2. Every slot the seed action creates has `starts_at` between 08:00 and
   18:00 `America/Sao_Paulo` inclusive of the start, exclusive of 18:00
   itself as a start time — never outside that window.
3. A deactivated professional (`active = false`) never receives a
   generated slot (`analysis.md` finding 1).

## F. Zero-match abstain [AA-8, outcome 6]

1. A query that matches no available slot (e.g. an exhausted/unseeded
   combination) produces the existing `ABSTAIN`/`DYNAMIC_DATA_UNAVAILABLE`
   path — `draft_text` empty, no internal cause string anywhere in the
   customer-facing response, matching D-028's existing negative test
   pattern exactly.

## G. Scope isolation — no booking/identity/billing access [outcome 7]

1. Static/structural check: no import of `scheduling.appointments`/
   `appointment_events`, `identity.*`, or `billing.*` ORM classes or raw
   table names anywhere in `scheduling/models.py`, `scheduling/availability.py`,
   or `scheduling/seeding.py`.
2. Live check: after exercising both the query path and the seed action
   end-to-end, confirm row counts in `scheduling.appointments`,
   `identity.patients`, and `billing.payments` are unchanged (still zero,
   or whatever they were before — never incremented).

## H. Unimplemented-resolver regression [AA-1, outcome 8]

1. A Q&A entry with `dynamic_resolver = 'price_lookup'` (or
   `payment_simulator`/`insurance_lookup`) and `dynamic_data_required =
   true`, no `qa_dynamic_bindings` row, continues to abstain exactly as it
   did before this feature — proves the `NAMED_RESOLVERS` fallthrough
   introduced no accidental widening of what resolves.
2. A Q&A entry with `dynamic_data_required = true`, `dynamic_resolver =
   NULL`, and a real `qa_dynamic_bindings` row (V2's generic mechanism)
   still resolves exactly as before — proves the dispatch change is
   additive, not a replacement of the generic path.

## I. Seed endpoint authorization [AA-9, outcome 9]

1. An anonymous or customer-token credential gets `401` from
   `POST /operator/scheduling/ensure-availability`.
2. Any authenticated operator (not just one assigned to a specific
   conversation) can call it successfully — it is deliberately not
   conversation/assignment-scoped (`plan.md` §9).
3. It never creates a slot outside 08:00-18:00 and never creates more than
   the exact number needed — a negative test proves it cannot be made to
   over-create by calling it repeatedly or concurrently (§D.4).

## J. V1/V2/V3 regression spot-check [outcome 10]

- the full pre-existing `smoke_*` suite (V1/V2/V3) passes unmodified
  against the rebuilt backend image;
- `smoke_v2_dynamic_pattern.py` specifically (the closest existing
  precedent to this feature) passes unmodified;
- the pre-existing frontend suite (`v1.spec.ts`/`v2.spec.ts`/`v3.spec.ts`,
  `main.test.tsx`'s existing tests) is unaffected by this feature's new
  button and endpoint — `eslint`/`tsc`/`vitest`/`vite build` all still pass,
  and no existing Playwright scenario's behavior changes (the new button
  lives outside any conditional those scenarios exercise).

## K. Quality gates

- backend `ruff`/`mypy customer_care`/`pytest` all pass, including every
  new test file this feature adds;
- frontend `eslint`/`tsc --noEmit`/`vitest`/`vite build` all pass — this
  feature has a real frontend surface now (`plan.md` §1, revised), unlike
  the first plan draft;
- `contracts/openapi.yaml` (new file for this package) documents the one
  new `POST /operator/scheduling/ensure-availability` route and matches the
  live route table — the query path itself still needs no contract entry
  (unchanged, no new/changed customer-facing route or response schema for
  it);
- no material spec/plan/code divergence remains (`analysis.md`).

## Execution record

*(Populated once Phase 1-8 implementation lands, following V1/V2/V3's
Execution-record format — evidence per section, real command output, real
live-verification results. Not yet executed — this document currently
records the pre-implementation acceptance protocol only, per `AGENTS.md`'s
required SDD flow: acceptance criteria exist before implementation begins.)*
