# Requirement Traceability Checklist — Dynamic Appointment Availability

Maps `spec.md` §3's confirmed outcomes to `tasks.md` phases/tasks and
`acceptance.md` sections. V1/V2/V3's own traceability is unchanged and
still governs everything this feature leaves untouched. Revised 2026-08-18
twice more: once for the split into a read-only query path and a separate
operator-triggered seed action (AA-9), and again after AA-3a (the seeded
generalist specialty) replaced the original "no specialty → unfiltered"
design.

| Outcome | Primary tasks | Acceptance area |
|---|---|---|
| AA-1 Resolver allowlist, not a generic binding | T050, T052 | H |
| AA-2 Purely read-only query path | T030, T031 | C |
| AA-3 Deterministic parameter extraction | T020, T021 | B |
| AA-3a Seeded generalist specialty, not an unfiltered fallback | T009, T020, T031 | 0, B |
| AA-4 Structured, timezone-aware evidence | T030 | A |
| AA-5 Deterministic template rendering, never LLM-composed | T030 | A |
| AA-6 Explicit operator send only | (unchanged V1 invariant) | J |
| AA-7 Append-only audit with safe provenance | T042, T051 | (security checklist) |
| AA-8 Manual fallback for unavailable/empty/failed data | T030, T031 | F |
| AA-9 Explicit, idempotent, operator-triggered D+1/D+7 seeding | T040, T041, T042, T060, T061 | D, E, I |

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
| 10 | V1/V2/V3 regression spot-check (incl. frontend gates) | J |

## Non-functional coverage

| Requirement | Primary tasks/tests | Acceptance area |
|---|---|---|
| No new infrastructure (Article VIII) | T040, `plan.md` §4b/§11 | E |
| `scheduling` schema shape unchanged (D-024 dormancy preserved) | T010, `data-model.md` | G |
| New migration applies cleanly, additive only | T009, `data-model.md` §5 | 0 |
| Idempotency + bounded creation under concurrent seed calls | T041 | D |
| Audit coverage for the resolver and the seed action | T042, T051 | (security checklist) |
| Frontend button accessibility/behavior | T060, T061 | J |

## Executable evidence (populated as tasks land)

| Coverage | Evidence |
|---|---|
| Migration correctness (4 specialties, 12 professionals) | `app/tests/test_appointment_availability_*.py` (planned, T011) |
| ORM mapping correctness | `app/tests/test_appointment_availability_*.py` (planned, T011) |
| Deterministic keyword extraction (incl. generalist default) | `app/tests/test_appointment_availability_keywords.py` (planned, T021) |
| Query-path correctness + no-write structural proof | `app/tests/test_appointment_availability_resolver.py` (planned, T031) |
| Seed action idempotency/bounds/business-day correctness | `app/tests/test_appointment_seeding.py` (planned, T041) |
| Dispatch/regression (generic path + unimplemented resolvers) | `app/tests/smoke_v2_dynamic_pattern.py` unmodified (planned check, T052) |
| Seed endpoint auth + button behavior | `frontend/src/main.test.tsx` (planned, T061) |
| End-to-end real HTTP smoke (query + seed) | `app/tests/smoke_v4_appointment_availability.py` (planned, T071) |
