# Requirement Traceability Checklist — Dynamic Appointment Availability

Maps `spec.md` §3's confirmed outcomes to `tasks.md` phases/tasks and
`acceptance.md` sections. V1/V2/V3's own traceability is unchanged and
still governs everything this feature leaves untouched.

| Outcome | Primary tasks | Acceptance area |
|---|---|---|
| AA-1 Resolver allowlist, not a generic binding | T040, T042 | H |
| AA-2 Read-only, on-demand, no freshness machinery | T030, T032 | E, G |
| AA-3 Deterministic parameter extraction | T020, T021 | B |
| AA-4 Structured, timezone-aware evidence | T031 | A |
| AA-5 Deterministic template rendering, never LLM-composed | T031 | A |
| AA-6 Explicit operator send only | (unchanged V1 invariant) | I |
| AA-7 Append-only audit with safe provenance | T041 | (security checklist) |
| AA-8 Manual fallback for unavailable/empty/failed data | T031, T032 | F |

## `spec.md` §4 acceptance outcomes to `acceptance.md` sections

| # | Outcome | Acceptance area |
|---|---|---|
| 1 | Real-data deterministic answer | A |
| 2 | Specialty filtering | B |
| 3 | Sunday/holiday business-day redirect | C |
| 4 | Saturday-hours rule | D |
| 5 | No manual reseed needed | E |
| 6 | Zero-match abstain | F |
| 7 | No booking/identity/billing access | G |
| 8 | Unimplemented-resolver regression | H |
| 9 | V1/V2/V3 regression spot-check | I |

## Non-functional coverage

| Requirement | Primary tasks/tests | Acceptance area |
|---|---|---|
| No new infrastructure (Article VIII) | T030, `plan.md` §4/§11 | E |
| `scheduling` schema shape unchanged (D-024 dormancy preserved) | T010, `data-model.md` | G |
| Idempotency under concurrent resolution | T032 | E |
| Audit coverage for the new resolver | T041 | (security checklist) |

## Executable evidence (populated as tasks land)

| Coverage | Evidence |
|---|---|
| ORM mapping correctness | `app/tests/test_appointment_availability_*.py` (planned, T011) |
| Deterministic keyword extraction | `app/tests/test_appointment_availability_keywords.py` (planned, T021) |
| Slot-ensure idempotency + resolver correctness | `app/tests/test_appointment_availability_resolver.py` (planned, T032) |
| Dispatch/regression (generic path + unimplemented resolvers) | `app/tests/smoke_v2_dynamic_pattern.py` unmodified (planned check, T042) |
| End-to-end real HTTP smoke | `app/tests/smoke_v4_appointment_availability.py` (planned, T051) |
