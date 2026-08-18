# Dynamic Appointment Availability Acceptance Protocol

This is the executable definition of DONE for this feature, supplementary to
`spec.md` §4. It extends V1/V2/V3's own acceptance packages (unchanged) and
does not repeat scenarios this feature leaves untouched.

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

## C. Business-day/holiday handling [outcome 3]

1. Force (via a test-only reference date or a seeded holiday) a query whose
   naive target date is a Sunday or a holiday; verify the returned date is
   the correct next business day per `scheduling.next_business_day()`, and
   the customer-facing text reflects that resolved date, never the raw
   Sunday/holiday date.

## D. Saturday-hours rule [outcome 4]

1. A query resolving to a Saturday only returns slots within
   `SLOT_HOURS_SATURDAY` — never a weekday-hour slot mistakenly generated
   for a Saturday.

## E. Freshness without manual reseed [AA-2, outcome 5]

1. Advance the effective "today" across multiple resolutions (or run the
   resolver on two different real days in CI/manual testing); verify each
   resolution still returns real, future, non-stale slots with no manual
   reseed step, no scheduler, and no stale-date slot ever returned.
2. Call `ensure_near_future_slots()` twice in immediate succession; verify
   the second call inserts zero new rows (idempotency).

## F. Zero-match abstain [AA-8, outcome 6]

1. A query that matches no available slot (e.g. an exhausted/unseeded
   combination) produces the existing `ABSTAIN`/`DYNAMIC_DATA_UNAVAILABLE`
   path — `draft_text` empty, no internal cause string anywhere in the
   customer-facing response, matching D-028's existing negative test
   pattern exactly.

## G. Scope isolation — no booking/identity/billing access [outcome 7]

1. Static/structural check: no import of `scheduling.appointments`/
   `appointment_events`, `identity.*`, or `billing.*` ORM classes or raw
   table names anywhere in `scheduling/models.py` or
   `scheduling/availability.py`.
2. Live check: after exercising this feature's full resolver path
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

## I. V1/V2/V3 regression spot-check [outcome 9]

- the full pre-existing `smoke_*` suite (V1/V2/V3) passes unmodified
  against the rebuilt backend image;
- `smoke_v2_dynamic_pattern.py` specifically (the closest existing
  precedent to this feature) passes unmodified;
- no frontend file changed (`plan.md` §13) — `eslint`/`tsc`/`vitest`/
  `vite build`/`playwright test` are unaffected by construction, not
  merely "happened to still pass."

## J. Quality gates

- backend `ruff`/`mypy customer_care`/`pytest` all pass, including every
  new test file this feature adds;
- no `contracts/openapi.yaml` change needed (`plan.md` §1) — confirmed no
  drift by construction (no new/changed route or response schema);
- no material spec/plan/code divergence remains (`analysis.md`).

## Execution record

*(Populated once Phase 1-6 implementation lands, following V1/V2/V3's
Execution-record format — evidence per section, real command output, real
live-verification results. Not yet executed — this document currently
records the pre-implementation acceptance protocol only, per `AGENTS.md`'s
required SDD flow: acceptance criteria exist before implementation begins.)*
