# Requirement Traceability Checklist — Dynamic Appointment Availability

Maps `spec.md` §3's confirmed outcomes to `tasks.md` phases/tasks and
`acceptance.md` sections. V1/V2/V3's own traceability is unchanged and
still governs everything this feature leaves untouched. Revised 2026-08-18
three times: for the split into a read-only query path and a separate
operator-triggered seed action (AA-9); for AA-3a (the seeded generalist
specialty); for AA-10 (the booking script) and Constitution Amendment 1.1.0.
Revised again 2026-08-19 (T008, the `scheduling`-schema-creation migration
found necessary during the post-V3 production sync — `spec.md` §2
correction).

| Outcome | Primary tasks | Acceptance area |
|---|---|---|
| AA-1 Resolver allowlist, not a generic binding | T050, T052 | H |
| AA-2 Purely read-only query path | T030, T031 | C |
| AA-3 Deterministic parameter extraction | T020, T021 | B |
| Scheduling schema creation (correction, prerequisite for AA-2/AA-3a/AA-9) | T008 | 0 |
| AA-3a Seeded generalist specialty, not an unfiltered fallback | T009, T020, T031 | 0, B |
| AA-4 Structured, timezone-aware evidence | T030 | A |
| AA-5 Deterministic template rendering, never LLM-composed | T030 | A |
| AA-6 Explicit operator send only (except AA-10) | (unchanged V1 invariant) | P |
| AA-7 Append-only audit with safe provenance | T042, T051 | (security checklist) |
| AA-8 Manual fallback for unavailable/empty/failed data | T030, T031 | F |
| AA-9 Explicit, idempotent, operator-triggered D+1/D+7 seeding | T040, T041, T042, T060, T061 | D, E, I |
| AA-10 Simulated identity/payment script (Constitution Amendment 1.1.0) | T090-T098 | L, M, N, O |

## `spec.md` §4 acceptance outcomes to `acceptance.md` sections

| # | Outcome | Acceptance area |
|---|---|---|
| 1 | Real-data deterministic answer | A |
| 2 | Specialty filtering (incl. generalist default) | B |
| 3 | Sunday/holiday business-day redirect (seed action) | E |
| 4 | Query path never writes | C |
| 5 | Seed action idempotency + exact target | D, E |
| 6 | Zero-match abstain | F |
| 7 | No booking/identity/billing access | G |
| 8 | Unimplemented-resolver regression | H |
| 9 | Seed endpoint authorization + creation bounds | I |
| 10 | Booking script exact scripted flow | L |
| 11 | Booking script CPF parsing correctness | M |
| 12 | Booking script payment-confirmation parsing correctness | M |
| 13 | Booking script never persists CPF/payment answer | N |
| 14 | Booking script autonomous-send containment | O |
| 15 | V1/V2/V3 regression spot-check (incl. frontend gates) | P |

## Non-functional coverage

| Requirement | Primary tasks/tests | Acceptance area |
|---|---|---|
| No new infrastructure (Article VIII) | T040, T093, `plan.md` §4b/§8b/§11 | E |
| `scheduling` activation scoped to authorized objects; deferred schemas/tables remain absent | T008, T010, `data-model.md` §5 | 0, G |
| Four migrations apply cleanly, additive/narrow, in order | T008, T009, T090, T093, `data-model.md` §5/§6/§8 | 0 |
| Idempotency + bounded creation under concurrent seed calls | T041 | D |
| Audit coverage for the resolver, seed action, and booking script | T042, T051, T093 | (security checklist) |
| Frontend button accessibility/behavior | T060, T061 | P |
| Autonomous-send containment (Constitution Amendment 1.1.0) | T096, T082, `analysis.md` §18 | O |
| Raw AA-10 input non-retention | T095, T097, T082 | N |

## Executable evidence (populated as tasks land)

| Coverage | Evidence |
|---|---|
| Migration correctness (schema creation, 4 specialties, 12 professionals; booking-script columns/CHECK) | `app/tests/test_appointment_availability_models.py`, live Postgres catalog query, migrations T008/T009/T090/T093 |
| ORM mapping correctness | `app/tests/test_appointment_availability_models.py` (passing) |
| Deterministic keyword extraction (incl. generalist default) | `app/tests/test_appointment_availability_keywords.py` (passing) |
| Query-path correctness + no-write structural proof | `app/tests/test_appointment_availability_resolver.py` (passing) |
| Seed action idempotency/bounds/business-day correctness | `app/tests/test_appointment_seeding.py` (passing, real Postgres including concurrency) |
| Dispatch/regression (generic path + unimplemented resolvers) | `app/tests/test_dynamic_pattern_dispatch.py` plus unmodified `smoke_v2_dynamic_pattern.py` (passing) |
| Seed endpoint auth + button behavior | backend integration coverage and `frontend/src/main.test.tsx` (17/17 suite passing) |
| End-to-end real HTTP smoke (query + seed) | `app/tests/smoke_v4_appointment_availability.py` (T071, passing) |
| CPF/payment/booking-intent parsing correctness | `app/tests/test_booking_script_parsing.py` (passing) |
| Booking script full flow + raw-input non-retention | `app/tests/test_booking_script_flow.py` (passing) |
| Autonomous-send containment (structural) | `app/tests/test_booking_script_containment.py` (4/4 independently rerun in T082) |
| End-to-end real HTTP smoke (booking script) | `app/tests/smoke_v4_booking_script.py` (passing, with direct DB assertions) |
| Full regressions | 16/16 `smoke_*.py`; Playwright 11 passed/1 intentional skip; backend 119; frontend Vitest 17 |
