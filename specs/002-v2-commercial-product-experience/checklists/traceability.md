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
| Token format/rate limiting | `app/tests/test_anonymous_token_rate_limit.py`; `app/tests/smoke_v2_token_rate_limit.py` |
| Message-context selection/default/clear-all | `app/tests/smoke_n2.py` (V2-4 section) |
| "Gerar rascunho" request-shape change, no `/regenerate` route | `app/tests/smoke_n2.py` (V2-4 section) |
| "Buscar evidências" single-selection + independence | `app/tests/smoke_n2.py` (V2-3/V2-6 sections) |
| Typing heartbeat + lazy 8s trigger | `app/tests/smoke_v2_automatic_trigger.py` |
| Dynamic-pattern resolution + all fallback modes | `app/tests/smoke_v2_dynamic_pattern.py`; `app/tests/smoke_n2.py` (V2-6 section) |
| Knowledge CRUD + re-embed + soft delete + audit + write-time binding validation | `app/tests/smoke_v2_knowledge_crud.py` |
| N1 search flag / manual-fallback regression | `app/tests/smoke_resilience.py` |
| Real-provider draft generation | `app/tests/smoke_real_provider.py` |
| E2E: V1 acceptance flows re-verified against the V2-1 redesign | `frontend/e2e/v1.spec.ts` |
| E2E: typing-debounce batching | `frontend/e2e/v2.spec.ts` (T124) |
| E2E: "Buscar evidências"/"Gerar rascunho" independence | `frontend/e2e/v2.spec.ts` (T125) |
| E2E: dynamic-pattern happy path + fallback | `frontend/e2e/v2.spec.ts` (T126) |
| E2E: knowledge CRUD round trip | `frontend/e2e/v2.spec.ts` (T127) |
| E2E: token lockout | `frontend/e2e/v2.spec.ts` (T128) |
