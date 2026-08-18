# V3 Requirement Traceability Checklist

Maps `spec.md` §2's confirmed outcomes to `tasks.md` phases/tasks and
`acceptance.md` sections. V1/V2's own traceability
(`specs/002-v2-commercial-product-experience/checklists/traceability.md`,
extending V1's) is unchanged and still governs V1/V2-inherited behavior.

| Outcome | Primary tasks | Acceptance area |
|---|---|---|
| V3-1 Operator feedback taxonomy | T030-T035 (mark-incorrect/escalate/classify_generation); approve/edit reuse V1's existing T141 (`ai.draft_accepted`/`ai.draft_edited`), no new tasks | B |
| V3-2 Quick-approve action | T040-T042 | C |
| V3-3 Human Correction Rate | T110-T111 | D |
| V3-4 Read-only management metrics | T110-T112 | E |
| V3-5 Evaluation datasets/suites | T070-T074 | F |
| V3-6 Regenerate-with-instruction | T050-T056 | G |
| V3-7 Clear/reset control | T090, T093 | H |
| V3-8 Guided knowledge-CRUD inputs | T020-T024 (category registry), T060-T064 (tables/columns/transformar-em-Q&A) | I |
| V3-9 Automatic-draft countdown | T080-T082 | J |
| V3-10 Scroll to top on evidence selection | T091, T093 | K |
| V3-11 Confirm before closing a conversation | T092-T093 | L |
| V3-12 Post-conversation satisfaction survey | T100-T104 | M |

## `spec.md` §5 acceptance outcomes to `acceptance.md` sections

| # | Outcome | Acceptance area |
|---|---|---|
| 1 | Eight taxonomy tags observable, `edit`/`escalate` derivation exact | B |
| 2 | Quick-approve unmodified send, negative auto-trigger test | C |
| 3 | HCR computed from durable facts, reproducible, by category | D |
| 4 | Read-only metrics surface, server-side enforced | E |
| 5 | Evaluation case isolation from production metrics | F |
| 6 | Regenerate-with-instruction internal-only, audited | G |
| 7 | V1/V2 acceptance spot-check | P |
| 8 | Clear/reset scope (no durable-row side effects) | H |
| 9 / 9a | Guided knowledge-CRUD correctness; transformar-em-Q&A pre-fill/confirm | I |
| 10 | Countdown reset/no-negative/no-self-trigger | J |
| 11 | Scroll-to-top scope and no fight with poll re-renders | K |
| 12 | Close-confirmation no-partial-side-effect | L |
| 13 | Satisfaction survey non-blocking, durable, correctly attributed | M |

## Non-functional coverage

| Requirement | Primary tasks/tests | Acceptance area |
|---|---|---|
| Category-registry FK integrity (both taxonomies) | T010-T012, T017 | A |
| No new infrastructure (no scheduler for countdown) | T080, `plan.md` §12/§23 | A, O |
| Evaluation-case structural isolation | T014, T074 | F |
| Column-introspection allowlist enforcement | T061, T064 | I, N |
| Audit coverage for new event types | T031, T032, T053, T102, T120 | N, O |
| `classify_generation()` / SQL query agreement (no drift) | T030, T111 | O |
| Quick-approve staleness guard | T040, T042 | C |

## Executable evidence (to be populated as tests land)

| Coverage | Evidence |
|---|---|
| `classify_generation()` taxonomy derivation | `app/tests/test_v3_taxonomy.py` (planned, T034) |
| Mark-incorrect/escalate endpoints | `app/tests/smoke_v3_taxonomy_hcr.py` (planned, T131) |
| Quick-approve + staleness guard | `app/tests/smoke_v3_taxonomy_hcr.py` (planned, T131) |
| Regenerate-with-instruction provider passthrough | `app/tests/test_v3_regenerate_instruction.py` (planned, T056) |
| Category registry migration/backfill | `app/tests/test_v3_category_migration.py` (planned, T017) |
| Guided knowledge-CRUD + transformar-em-Q&A | `app/tests/smoke_v3_knowledge_guided.py` (planned, T131) |
| Evaluation-case isolation | `app/tests/test_v3_evaluation_cases.py` (planned, T074) |
| Countdown indicator | `frontend/e2e/v3.spec.ts` (planned, T132) |
| Scroll-to-top / clear-reset / confirm-close | `frontend/e2e/v3.spec.ts` (planned, T132) |
| Satisfaction survey | `app/tests/smoke_v3_satisfaction.py` (planned, T131) |
| Documented metrics queries vs. `classify_generation()` agreement | `app/tests/test_v3_metrics_queries.py` (planned, T111) |
