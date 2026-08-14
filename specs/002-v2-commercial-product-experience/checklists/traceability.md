# V2 Requirement Traceability Checklist

Maps `spec.md` §2's confirmed outcomes to `tasks.md` phases/tasks and
`acceptance.md` sections. V1's own traceability
(`specs/001-v1-assisted-customer-service/checklists/traceability.md`) is
unchanged and still governs V1-inherited behavior.

| Outcome | Primary tasks | Acceptance area |
|---|---|---|
| V2-1 Professional UX | T100-T105 | H |
| V2-2 Token format/rate limiting | T020-T027 | B, I |
| V2-3 "Buscar evidências" | T050-T057 | E, I |
| V2-4 Message-context selection | T030-T036 | C, I |
| V2-5 Customer-ready drafts | (inherited from V1; T040/T063/T074 wire it into the new triggers) | C, D, E |
| V2-6 Dynamic-evidence correction | T070-T079 | F, I |
| V2-7 Generation triggers (manual + automatic) | T040-T045, T060-T068 | C, D |
| V2-8 Knowledge-base CRUD | T080-T090 | G, I |

## `spec.md` §5 acceptance outcomes to acceptance.md sections

| # | Outcome | Acceptance area |
|---|---|---|
| 1 | Token view/copy scope | B |
| 2 | Manual search visibly matches query | E |
| 3 | Clinical child → complete parent, no automated send | E |
| 4 | Admin Q&A → concise LLM response | E |
| 5 | Checkboxes select multiple messages, traceable | C |
| 6 | Unauthorized users blocked from token/selection/evidence/metadata | I |
| 7 | RAG/provider failure and insufficient evidence leave manual available | K (V1 regression) |
| 8 | Token rate-limit/lockout, ambiguous-character exclusion | B, I |
| 9 | No automatic draft while typing; 8s debounce; typing indicator | D |
| 10 | Unconfigured/failed dynamic pattern falls back safely, detail operator-only | F, I |
| 11 | Knowledge CRUD (create/read/update/deactivate), audited | G |

## Non-functional coverage

| Requirement | Primary tasks/tests | Acceptance area |
|---|---|---|
| Token entropy/brute-force mitigation | T022-T026 | B, I |
| No new infrastructure (no scheduler/WebSocket) | T062-T063, plan.md §7.2/§18 | J |
| Traceability of selections (no chain-of-thought) | T032, T036 | C, K |
| Dynamic-pattern security (allowlist only) | T071, T077-T078 | F, I |
| Audit coverage for new event types | T110-T113 | I, J |
| Accessibility of new controls | T103 | H |
| Idempotent re-embed on CRUD change | T084, T090 | G |

## Executable evidence (to be populated as tests land)

| Coverage | Evidence |
|---|---|
| Token rate limiting | *(new test module, per T025)* |
| Message-context selection/default/clear-all | *(new test module, per T036)* |
| "Gerar rascunho" request-shape change, no `/regenerate` route | *(new test module, per T044-T045)* |
| "Buscar evidências" single-selection + independence | *(new test module, per T054, T056-T057)* |
| Typing heartbeat + lazy 8s trigger | *(new test module, per T066-T068)* |
| Dynamic-pattern resolution + all fallback modes | *(new test module, per T076-T079)* |
| Knowledge CRUD + re-embed + soft delete + audit | *(new test module, per T089-T090)* |
| E2E: typing-debounce batching | *(per tasks.md T124)* |
| E2E: "Buscar evidências"/"Gerar rascunho" independence | *(per tasks.md T125)* |
| E2E: dynamic-pattern happy path + fallback | *(per tasks.md T126)* |
| E2E: knowledge CRUD round trip | *(per tasks.md T127)* |
| E2E: token lockout | *(per tasks.md T128)* |

This table's right-hand column should be filled in with actual file paths as
Phase 11 (`tasks.md`) produces them — do not claim executable evidence exists
before the corresponding test file is committed.
