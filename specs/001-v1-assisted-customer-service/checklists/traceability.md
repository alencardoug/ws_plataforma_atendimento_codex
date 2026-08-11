# Requirement Traceability Checklist

The coding agent should expand this into an implementation/test matrix during T002.

| Requirement family | Primary tasks | Acceptance area |
|---|---|---|
| Anonymous session FR-001..007 | T040-T048 | A/B/I |
| Operator auth FR-010..011 | T050-T054 | B/I |
| Queue/capacity FR-012..016 | T060-T066 | B |
| Mode/take-over FR-020..024 | T160-T165 | D/E |
| Messaging FR-030..035 | T070-T074, T140-T144 | C/D/E/I |
| N1 search FR-040..042 | T105-T110 | E |
| N2 drafts FR-050..055 | T120-T144 | C/D/G/H |
| Ingestion FR-060..066 | T080-T091 | A/F |
| Retrieval FR-070..074 | T100-T110 | F |
| Grounding/abstention FR-080..084 | T120-T135 | G/H |
| Citations FR-090..094 | T150-T156 | F/I |
| Audit FR-100..104 | T030-T031, T170 | C/D/J |

## Non-functional coverage

| Requirement | Primary tasks/tests | Acceptance area |
|---|---|---|
| NFR-001 performance | T171, T197-T198; timed RAG/generation acceptance | C/J |
| NFR-002 concurrency | T048, T065-T066, T191 | B |
| NFR-003 AI/RAG resilience | T074, T135, T196 | H |
| NFR-004 persistence/restart | T027-T028, T174 | A/J |
| NFR-005 security | T032-T035, T042, T047, T054, T143, T155-T156 | I |
| NFR-006 privacy/logging | T035, T175 | I/J |
| NFR-007 generation traceability | T023-T025, T104, T121-T126, T144, T171 | C/F/J |
| NFR-008 critical negative tests | T047, T054, T066, T110, T133-T135, T143, T155-T156 | I/J |
| NFR-009 modular monolith | T010-T012, T020 | A/J |
| NFR-010 future channel boundary | T010 and convergence review T199 | J |
| NFR-011 accessibility | T182 plus frontend/E2E gates T197 | J |

## Executable evidence

| Coverage | Evidence |
|---|---|
| Security primitives / invalid hierarchy | `app/tests/test_security_and_ingestion.py` |
| Six clients, IDOR, auth negatives, manual send | `app/tests/smoke_core.py` |
| Concurrent max-four invariant | `app/tests/smoke_concurrent_capacity.py` |
| Dual RAG, parent lineage, citation policy, hidden draft, take-over | `app/tests/smoke_n2.py` |
| N1 flag and AI failure/manual fallback | `app/tests/smoke_resilience.py` |
| Idempotency and changed-content re-embedding | `app/tests/smoke_ingestion_changed.py` |
| Real OpenAI adapter integration | `app/tests/smoke_real_provider.py` |
| Safe rendering and route components | `frontend/src/main.test.tsx` |
| Six independent browsers, N2 explicit send/take-over, N1 manual flow | `frontend/e2e/v1.spec.ts` |
