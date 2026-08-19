# Dynamic Appointment Availability Acceptance Protocol

This is the executable definition of DONE for this feature, supplementary to
`spec.md` §4. It extends V1/V2/V3's own acceptance packages (unchanged) and
does not repeat scenarios this feature leaves untouched. Revised 2026-08-18
three times the same day: after the second round split the query path
(§A-C) and the seed action (§D-F) into two clearly separated pieces with
different triggers and different write permissions; after the fourth round
added the generalist specialty (AA-3a, §0); after the fifth round added
the booking script (AA-10, §L-O) — the one section group in this document
that verifies an exception to Constitution Article III rather than an
ordinary feature behavior.

## 0. Environment [correction, AA-3a]

1. T008's schema-creation migration (`data-model.md` §5) applies cleanly
   on top of the V1/V2/V3-migrated database, which has **no** pre-existing
   `scheduling` schema (verified against both local and production before
   this feature's implementation — `db/init/001_schema.sql`/
   `002_seed_and_schedule.sql` were never wired into any automated init
   path). Creates the schema, its tables/enum/function, and the original 3
   specialties/9 professionals/holidays seed data.
2. T009's generalist-specialty migration (`data-model.md` §6) applies
   cleanly immediately after T008, purely additive (new reference rows in
   the tables T008 just created, no schema change).
3. After applying both, `scheduling.specialties` has exactly 4 rows (the
   original 3 plus `oncologia-geral`), and its 3 new professionals'
   `professional_specialties` rows carry the specified price/duration.
4. Neither migration creates `slot_offers`, `available_offers`,
   `ensure_demo_availability()`, `appointments`, `appointment_events`, or
   any `identity.*`/`billing.*`/`governance.*` object — spot-check these
   remain absent after both migrations apply.
5. Existing V1/V2/V3 data/rows (`content.*`, `customer_service.*`) are
   unaffected — spot-check row counts before/after.

## A. Deterministic, real-data answer [AA-4, AA-5, outcome 1]

1. As an operator, generate a draft against a customer message matching one
   of the in-scope `agenda` Q&A entries; verify the resulting generation has
   `status = ANSWER`, `model = "not-applicable"`, `dynamic_pattern_used =
   true`, and `draft_text` containing real (synthetic) slot data — specialty
   display name, professional name, unit, a real future date/time in
   `America/Sao_Paulo`, price, and a "(simulação)" marker.
2. Confirm no LLM generation call occurred: `model = "not-applicable"`
   and the bounded `duration_ms` check in the real HTTP smoke is
   consistent with pure database resolution. Integration acceptance uses
   the real Postgres stack, not a mocked database.

## B. Specialty filtering [AA-3, outcome 2]

1. A message naming a real specialty (e.g. "mastologia") returns only that
   specialty's slots.
2. A message naming no specialty — or explicitly asking for a generalist —
   returns only the seeded generalist specialty's (`oncologia-geral`)
   slots, never a mix across the 3 diagnosis-specific specialties, and
   never zero results just because nothing specific was named.
3. A message naming a specialty with no seeded professional/availability
   falls through to §F (abstain), never a wrong specialty's slots.
4. The two "primeira consulta" entries (`spec.md` §5 item 9, `plan.md`
   §8) — deliberately naming no diagnosis-specific specialty — resolve to
   the generalist specialty via the same default path as B.2, not a
   dedicated code path of their own.

## C. Query path is purely read-only [AA-2, outcome 4]

1. Static/structural check: `scheduling/availability.py`'s source contains
   no `insert(`/`update(`/`delete(`/`pg_insert(` construct, and does not
   import `scheduling/seeding.py`.
2. Live check: exercise the query path repeatedly (including against zero
   matching slots) and confirm `schedule_slots`'s row count is unchanged
   before/after — the query path cannot ever be the cause of a new row,
   even indirectly.

## D. Seed action: idempotent D+1/D+7 target, scoped to the generalist specialty [AA-9, outcome 5]

**Correction (2026-08-19, human decision: "faça este botão ir para a
oncologia geral"):** every count/creation below is scoped to the
generalist specialty (`oncologia-geral`, AA-3a) specifically — both the
"already sufficient" check and any created slots. Originally flat across
all 4 specialties; live verification showed that always seeded
`mastologia-oncologica` only (lowest professional UUIDs), never the
generalist specialty most customer queries actually fall back to.

1. Starting from zero seeded **generalist-specialty** slots on the
   computed `d1`/`d7` dates, one call to the seed endpoint creates exactly
   1 slot on `d1` and 3 on `d7`, all within 08:00-18:00
   `America/Sao_Paulo` and all tied to the `oncologia-geral` specialty and
   one of its 3 seeded professionals, and reports the created counts.
2. A second immediate call makes zero further writes and reports exactly
   "Já tem 4 vagas disponíveis." (the literal message the human specified).
3. A partial state (e.g. `d1` already has 1, `d7` has only 1 of 3,
   counting only generalist-specialty slots) results in creating exactly
   the 2 missing `d7` slots and none on `d1`, and the reported message
   reflects only what was actually created.
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
3. A deactivated generalist-specialty professional (`active = false`)
   never receives a generated slot (`analysis.md` finding 1; scope
   corrected 2026-08-19 to the generalist specialty's own 3 professionals,
   since those are the only candidates the seed action considers now).

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
   end-to-end, confirm `scheduling.appointments`, `identity.patients`, and
   `billing.payments` are absent or, if a future authorized migration has
   created them, their row counts are unchanged — never incremented.

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

## L. Booking script: exact scripted flow [AA-10, outcome 10]

1. The full happy-path sequence (`spec.md` AA-10) plays out verbatim: both
   valid-on-first-try steps (CPF, payment) produce exactly the specified
   messages in order, with zero operator action.
2. The invalid-CPF-then-valid branch: "123456a8910" (10 digits) produces
   "CPF inválido..." and the flow stays on the same step; "123.456..789.10"
   (11 digits) then produces "CPF 123.456.789-10 confirmado" and advances.
3. The não-then-sim branch: "Então, não paguei" re-asks the identical
   payment question (not a modified prompt, not an escalated one); "tabom
   simm paguei" then advances to "Verificando pagamento".
4. The script never runs LLM inference at any step — every message is a
   literal, pre-written string (interpolated only with the formatted CPF
   or the real seeded price).

## M. Booking script: input parsing correctness [AA-10, outcome 11-12]

1. `extract_cpf()`: any message yielding exactly 11 digits after removing
   non-digit characters is valid; 10 or 12 digits is invalid; the
   *real* Brazilian CPF check-digit algorithm is never applied — a
   digit sequence that would fail real CPF validation still passes here
   if it has exactly 11 digits (proving this is format-only, matching the
   human's explicit "é uma simulação" instruction).
2. `extract_payment_confirmation()`: every "sim" variant the human listed
   affirms; every "não" variant, any unrecognized reply, and any reply
   matching both patterns simultaneously all fail to affirm and cause a
   re-ask with no retry limit — verified with at least 10 consecutive
   non-affirmative replies still re-asking correctly (no hidden cap).

## N. Booking script: no real persistence [AA-10, outcome 13]

1. After a full run (success and both retry branches), no table contains
   the submitted CPF/payment message bodies. The HTTP path persists fixed
   disclosure markers for those two customer steps; check `Message` and
   `AuditEvent` directly. The formatted CPF appears only in the exact,
   fixed `"CPF ... confirmado"` output required by AA-10, never in a
   structured identity/profile field or audit payload.
2. Only `Conversation.booking_script_step` changes during the flow, and it
   only ever holds one of its two enumerated values or `NULL` — enforced
   at the database level by a `CHECK` constraint, not only in application
   code.
3. No `scheduling.appointments`/`schedule_slots.status` row is created or
   changed by the script — "Agendamento realizado" is a sentence, not a
   state transition (§G already covers this structurally; this item
   confirms it live, end to end, through the actual script).

## O. Booking script: autonomous-send containment [AA-10, outcome 14]

1. A structural test enumerates every `Message(author_type="OPERATOR",
   ...)` construction site in the codebase and confirms each one (other
   than `send_scripted_message`) is reached only through a function with
   an authenticated-operator dependency in its call chain.
2. `send_scripted_message` is imported only within `booking_script/` —
   grep-verified, not just asserted.
3. Every message it sends carries `Message.autonomous_source =
   "booking_script"` and a corresponding
   `booking_script.autonomous_message_sent` audit event — a single query
   against either can enumerate every autonomously-sent message in the
   system, completely, with nothing missed.
4. `advance_booking_script()` is called from exactly one place
   (`send_customer_message()`) — not the typing-heartbeat endpoint, not
   any GET/poll path, not any operator-authenticated endpoint.
5. A message expressing booking intent in a conversation with no prior
   resolved `appointment_availability` generation never starts the
   script — the trigger cannot fire out of context.

## P. V1/V2/V3 regression spot-check [outcome 15]

- the full pre-existing `smoke_*` suite (V1/V2/V3) passes unmodified
  against the rebuilt backend image;
- `smoke_v2_dynamic_pattern.py` specifically (the closest existing
  precedent to this feature) passes unmodified;
- the pre-existing frontend suite (`v1.spec.ts`/`v2.spec.ts`/`v3.spec.ts`,
  `main.test.tsx`'s existing tests) is unaffected by this feature's new
  button, endpoint, and booking script — `eslint`/`tsc`/`vitest`/
  `vite build` all still pass, and no existing Playwright scenario's
  behavior changes (the new button lives outside any conditional those
  scenarios exercise; the booking script only reacts to messages
  containing its own specific trigger phrasing).

## Q. Quality gates

- backend `ruff`/`mypy customer_care`/`pytest` all pass, including every
  new test file this feature adds;
- frontend `eslint`/`tsc --noEmit`/`vitest`/`vite build` all pass — this
  feature has a real frontend surface now (`plan.md` §1, revised), unlike
  the first plan draft;
- `contracts/openapi.yaml` (new file for this package) documents the one
  new `POST /operator/scheduling/ensure-availability` route and matches the
  live route table — the query path itself and the booking script still
  need no contract entry (unchanged, no new/changed customer-facing route
  or response schema for either);
- no material spec/plan/code divergence remains (`analysis.md`), including
  a specific re-check that AA-10's autonomous-send exception has not
  spread beyond `booking_script/` (`analysis.md` §18).

## Execution record

**Executed:** 2026-08-19, against the implementation based on commit
`1810d1a`, with the Phase 10 convergence corrections in the closing
commit. Backend/frontend images were rebuilt with `docker compose build
backend frontend` and recreated with `docker compose up -d
--force-recreate backend frontend`; the real `pgvector/pgvector:pg17`
container was healthy and Alembic reported head `20260819_0004`. No
integration test used a mocked database.

| Area | Result | Real evidence |
|---|---|---|
| 0 | PASS | Live Postgres: 4 specialties, 12 professionals, 3 generalist links at 60000 cents/45 min; excluded scheduling/identity/billing tables absent; both AA-10 `CHECK`s present; Alembic at `20260819_0004`. |
| A | PASS | `smoke_v4_appointment_availability.py`: real seed + resolver returned `ANSWER`, `model=not-applicable`, real slot/price text, bounded database-only duration. |
| B | PASS | `test_appointment_availability_keywords.py` and resolver integration tests cover named specialties and `oncologia-geral` default; smoke resolved the no-specialty query from real seeded data. |
| C | PASS | Resolver structural no-write tests passed; source review found only SQLAlchemy `select`; repeated real-database tests did not create slots. |
| D | PASS | Real Postgres seed tests passed for empty, partial, repeated, and concurrent calls; advisory transaction lock holds the exact 1/3 generalist target. |
| E | PASS | Business-day/holiday, São Paulo boundary, 08:00-18:00, and inactive-generalist-professional tests passed. |
| F | PASS | Zero-match integration path returned `ABSTAIN`/`DYNAMIC_DATA_UNAVAILABLE` without exposing the internal cause. |
| G | PASS | Static imports and live V4 smokes confirmed no appointments/identity/billing access; all excluded tables are absent in the real database. |
| H | PASS | V4 availability smoke confirmed `price_lookup` still abstains; `test_dynamic_pattern_dispatch.py` and unmodified `smoke_v2_dynamic_pattern.py` confirmed allowlist/generic-path regression safety. |
| I | PASS | Endpoint integration/smoke confirmed operator bearer security and customer/anonymous rejection; repeat/concurrent bounds passed. Live OpenAPI exposes only `POST /api/v1/operator/scheduling/ensure-availability` with `operatorBearer`. |
| L | PASS | `smoke_v4_booking_script.py` reproduced the exact 10-message autonomous script, including invalid→valid CPF and não→sim branches, with zero operator clicks. |
| M | PASS | Parsing suite passed all CPF/payment/intent cases, including digit-count-only CPF and unlimited non-affirmative retries. |
| N | PASS | Convergence found and repaired a false-green test: raw sensitive customer messages had previously been persisted by the baseline message path. The route now parses request-local input and persists fixed markers; real HTTP smoke plus DB assertions prove submitted CPF/payment strings are absent from `Message`/`AuditEvent`. No booking/status/identity/payment row exists. |
| O | PASS | Independently rerun `pytest -q tests/test_booking_script_containment.py`: **4 passed**. AST proof found exactly one ungated construction (`send_scripted_message`), no external import, and exactly one trigger (`send_customer_message`). DB `messages_check` independently limits null-operator messages to `autonomous_source='booking_script'`. |
| P | PASS | All 16 repository `smoke_*.py` scripts passed against the rebuilt stack, including V1/V2/V3 and both V4 scripts. Full Playwright: **11 passed, 1 skipped by design** (N1-only scenario). Existing E2E tests needed bounded real-provider timeouts and stable locators; no product behavior was weakened. |
| Q | PASS | Backend `ruff`, `mypy`, and real-Postgres `pytest` passed (**119 tests**). Frontend ESLint, TypeScript, Vitest (**17 tests**), production build, and full Playwright passed. Contract/live-route and final cross-artifact checks passed. |

### Full-suite inventory and execution notes

- The repository contains **16** scripts matching `app/tests/smoke_*.py`:
  `smoke_core`, `smoke_n2`, `smoke_concurrent_capacity`,
  `smoke_ingestion_changed`, `smoke_resilience`, `smoke_real_provider`,
  four V2 scripts, four V3 scripts, and the two V4 scripts
  (`smoke_v4_appointment_availability.py`,
  `smoke_v4_booking_script.py`). All 16 passed. The handoff request said
  "3 novos smoke_v4", but commit `1810d1a` and the task/package inventory
  contain two; execution continued only after the human explicitly said
  "Prossiga", and this discrepancy is preserved here rather than hidden.
- `smoke_ingestion_changed.py` intentionally exercises a changed-content
  ingestion path. The approved corpus was restored afterward through the
  real provider (`embedded=658`, `inserted=0`, `skipped=57`, `updated=1`).
- Historical smoke fixtures that require an exact four-active slate were
  run from a clean synthetic conversation state and in dependency order.
  The reset touched only synthetic interaction tables; operators,
  knowledge, scheduling data, and Alembic state were preserved.
- The first full Playwright run exposed real-provider latency beyond old
  5s/15s assertion budgets and two live-locator assumptions. The tests
  were corrected to use bounded 20s/45s waits, capture the selected queue
  label before polling can reorder it, and compare message bodies rather
  than whole action-bearing panels. The final complete run passed 11/11
  applicable scenarios; the sole skip is the suite's intentional
  maturity-mode branch.
