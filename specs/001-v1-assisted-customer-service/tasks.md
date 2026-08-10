# Tasks: V1 Assisted Customer Service

Execution rule: complete in dependency order. Do not implement V2+.

Legend:

- `[P]` parallelizable after dependencies;
- `[USx]` primary user-story mapping;
- every task must update tests/docs when behavior changes.

## Phase 0 — SDD gates

- [ ] **T000** Read constitution, active spec/plan/data model/OpenAPI/acceptance and root security/architecture docs.
- [ ] **T001** Run Spec Kit `analyze` or equivalent cross-artifact review; document/fix contradictions before code.
- [ ] **T002** Produce requirements-to-task/test traceability matrix; ensure every P1 FR/NFR has coverage.
- [ ] **T003** Confirm implementation repository contains/identifies existing PostgreSQL/knowledge source assets; map actual source schema into canonical ingestion DTO without changing V1 behavior.

**Gate:** no unresolved blocker/contradiction.

## Phase 1 — Project skeleton and local runtime

- [ ] **T010** Create backend Python/FastAPI/Poetry project structure per plan.
- [ ] **T011** Create frontend React/TypeScript/Vite project with `/customer` and `/operator` routes.
- [ ] **T012** Create Docker Compose with PostgreSQL 17 + pgvector, backend, frontend.
- [ ] **T013** Create `.env.example` with required variable names and safe defaults where possible.
- [ ] **T014** Implement typed central runtime settings for N1/N2, N1 assistive search, max active conversations, DB, auth, AI models.
- [ ] **T015** Add backend health/readiness endpoints and database connectivity check.
- [ ] **T016** Add backend lint/format/type/test commands.
- [ ] **T017** Add frontend lint/type/test commands.
- [ ] **T018** Add correlation/request ID middleware and structured logging baseline without message bodies.

**Gate:** compose starts DB/backend/frontend; health passes.

## Phase 2 — Persistence and migrations

- [ ] **T020** Implement SQLAlchemy base/session/transaction utilities.
- [ ] **T021** Implement models/enums for operator users, conversations, assignments, messages.
- [ ] **T022** Implement knowledge documents/chunks including pgvector representation and hierarchy constraints.
- [ ] **T023** Implement retrieval runs/hits.
- [ ] **T024** Implement AI generations + generation-source lineage.
- [ ] **T025** Implement message citations.
- [ ] **T026** Implement audit events.
- [ ] **T027** Create initial Alembic migration(s) including pgvector extension/index strategy.
- [ ] **T028** Add migration tests from empty DB.

**Gate:** clean DB migrates; schema matches active data model.

## Phase 3 — Audit and shared security primitives

- [ ] **T030** Implement append-only audit repository/service with typed event names.
- [ ] **T031** Add audit event integration tests; verify no update/delete application API.
- [ ] **T032** Implement anonymous token generation + digest verification primitive.
- [ ] **T033** Implement operator password hashing/verification primitive.
- [ ] **T034** Implement operator auth token/session mechanism and dependency/middleware.
- [ ] **T035** Add negative tests for raw token/password persistence/logging.

## Phase 4 — Anonymous customer conversation [US1]

- [ ] **T040 [US1]** Implement create-conversation application service: WAITING, initial/effective mode snapshot, token digest, audit.
- [ ] **T041 [US1]** Implement public create/read/close endpoints per OpenAPI.
- [ ] **T042 [US1]** Implement customer-token authorization scoped to exact conversation.
- [ ] **T043 [US1]** Implement customer-message persistence endpoint; persist before any AI assistance; emit audit event.
- [ ] **T044 [US1]** Implement customer-safe DTO that excludes AI/retrieval/internal metadata.
- [ ] **T045 [US1] [P]** Implement customer SPA session service using per-tab `sessionStorage`.
- [ ] **T046 [US1] [P]** Implement customer chat UI: start, message list, send, status, close.
- [ ] **T047 [US1]** Add cross-conversation IDOR negative tests.
- [ ] **T048 [US1]** Add browser test proving six tabs create six distinct independent conversation tokens/IDs.

## Phase 5 — Operator authentication [US2]

- [ ] **T050 [US2]** Implement operator repository/service.
- [ ] **T051 [US2]** Implement reproducible synthetic operator seed command.
- [ ] **T052 [US2]** Implement login + `/operator/me` endpoints.
- [ ] **T053 [US2] [P]** Implement operator login UI/session storage strategy.
- [ ] **T054 [US2]** Add auth success/failure and customer-token-to-operator-route negative tests.

## Phase 6 — Queue, assignment, capacity [US3]

- [ ] **T060 [US3]** Implement waiting/active conversation query service.
- [ ] **T061 [US3]** Implement transactional claim service with max-active capacity.
- [ ] **T062 [US3]** Implement release service and assignment-history semantics.
- [ ] **T063 [US3]** Implement operator list/claim/release/close endpoints.
- [ ] **T064 [US3] [P]** Implement operator left-pane waiting/active list and claim controls.
- [ ] **T065 [US3]** Add integration test: six waiting -> four claims -> fifth rejected -> two waiting.
- [ ] **T066 [US3]** Add concurrent claim/capacity race test proving operator cannot exceed configured max.

**Gate:** six-client/max-four behavior passes without AI/RAG.

## Phase 7 — N1 manual messaging [US4]

- [ ] **T070 [US4]** Implement operator conversation detail/read authorization.
- [ ] **T071 [US4]** Implement explicit operator final-message send application service without AI dependency.
- [ ] **T072 [US4]** Implement operator send endpoint per OpenAPI.
- [ ] **T073 [US4] [P]** Implement selected conversation center pane + manual compose/send.
- [ ] **T074 [US4]** Add tests proving manual send works in N1 and when AI provider is unavailable.

## Phase 8 — Knowledge ingestion [US10, US11]

- [ ] **T080 [US10]** Define canonical administrative Q&A ingestion DTO + source adapter(s).
- [ ] **T081 [US11]** Define canonical clinical parent/child ingestion DTO + source adapter(s).
- [ ] **T082** Implement ingestion validation for IDs, blank content, hierarchy, exposure metadata.
- [ ] **T083** Implement content hashing/idempotent upsert semantics.
- [ ] **T084** Implement embedding provider port + configured OpenAI embedding adapter.
- [ ] **T085** Implement embedding persistence for QNA/CHILD searchable records.
- [ ] **T086** Implement offline CLI/application ingestion entry point for both source families.
- [ ] **T087** Emit ingestion started/completed/failed audit events with counts.
- [ ] **T088** Add ingestion idempotency tests.
- [ ] **T089** Add changed-content re-embedding test.
- [ ] **T090 [US11]** Add invalid missing-parent test.
- [ ] **T091** Add demo knowledge fixtures or documented adapter to existing repository source data sufficient for acceptance.

**Gate:** DB contains searchable vectors for both knowledge families.

## Phase 9 — Retrieval and N1 assistive search [US5, US10, US11]

- [ ] **T100** Implement query embedding application service.
- [ ] **T101 [US10]** Implement administrative flat vector retrieval.
- [ ] **T102 [US11]** Implement clinical child vector retrieval + parent expansion/dedupe.
- [ ] **T103** Implement combined evidence projection with type/rank/score/source exposure.
- [ ] **T104** Persist retrieval run/hits and emit search events.
- [ ] **T105 [US5]** Implement manual knowledge search service enforcing N1 assistive flag.
- [ ] **T106 [US5]** Implement `/operator/knowledge/search` endpoint.
- [ ] **T107 [US5] [P]** Implement operator evidence panel/manual search UI.
- [ ] **T108 [US10]** Test admin Q&A search with no parent assumption.
- [ ] **T109 [US11]** Test clinical child hit expands correct parent and persists lineage.
- [ ] **T110 [US5]** Test disabled N1 assistive search is forbidden/unavailable.

## Phase 10 — N2 AI copilot [US6, US8, US12]

- [ ] **T120** Implement generation provider port and configured OpenAI generation adapter with structured output validation.
- [ ] **T121** Implement prompt version registry/loading from `prompts/` or code-managed equivalent with stable version identifier.
- [ ] **T122 [US6]** Implement conversation-context builder with bounded active conversation history.
- [ ] **T123 [US6]** Implement N2 draft application service: effective-mode check -> retrieval -> generation -> persistence -> audit.
- [ ] **T124 [US12]** Implement structured abstention mapping/reason codes.
- [ ] **T125 [US6]** Implement generate-draft endpoint.
- [ ] **T126 [US8]** Implement regeneration service preserving prior generation and retrieval/provenance rules.
- [ ] **T127 [US8]** Implement regenerate endpoint.
- [ ] **T128 [US6] [P]** Implement operator AI panel: generate/view draft/evidence.
- [ ] **T129 [US8] [P]** Implement regenerate UI action.
- [ ] **T130 [US12]** Implement abstention presentation to operator.
- [ ] **T131** Add deterministic fake AI provider for tests.
- [ ] **T132 [US6]** Add test: customer message persistence does not depend on AI generation.
- [ ] **T133 [US6]** Add test: customer cannot fetch generation/internal evidence.
- [ ] **T134 [US12]** Add unsupported-query abstention test.
- [ ] **T135** Add AI provider failure test preserving manual flow.

## Phase 11 — Explicit human send from draft [US7]

- [ ] **T140 [US7]** Extend operator send service to accept optional `source_generation_id` and compare final text to draft.
- [ ] **T141 [US7]** Emit `ai.draft_accepted` when exact accepted content is sent and `ai.draft_edited` when modified.
- [ ] **T142 [US7] [P]** Implement `Use suggestion`/edit/final send UX.
- [ ] **T143 [US7]** Add negative service/API test proving an AIGeneration cannot directly create/publish customer-visible output without operator send.
- [ ] **T144 [US7]** Add provenance test linking final message to generation without changing draft record.

## Phase 12 — Citation exposure [US13]

- [ ] **T150 [US13]** Implement server-side customer citation policy service.
- [ ] **T151 [US13]** Implement citation attachment validation during operator send.
- [ ] **T152 [US13]** Implement safe customer citation snapshot/projection.
- [ ] **T153 [US13] [P]** Render approved citations in customer UI and internal evidence in operator UI.
- [ ] **T154 [US13]** Add positive clinical citation test.
- [ ] **T155 [US13]** Add negative administrative citation leakage test.
- [ ] **T156 [US13]** Add test preventing internal IDs/scores/storage metadata in public DTO.

## Phase 13 — Take over N2 -> N1 [US9]

- [ ] **T160 [US9]** Implement take-over domain/application service, one-way until close.
- [ ] **T161 [US9]** Implement take-over endpoint and audit event.
- [ ] **T162 [US9] [P]** Implement prominent effective-mode badge + `Take over` action in operator UI.
- [ ] **T163 [US9]** Disable/reject N2 draft generation after take-over.
- [ ] **T164 [US9]** Verify manual send and optional N1 search still work after take-over.
- [ ] **T165 [US9]** Add end-to-end take-over test.

## Phase 14 — Observability and hardening [US14]

- [ ] **T170 [US14]** Verify all required audit event types emitted for implemented flows.
- [ ] **T171** Add retrieval/generation duration + usage metadata capture.
- [ ] **T172** Add error handling with stable error codes for auth, capacity, mode conflict, provider failure.
- [ ] **T173** Add output rendering/sanitization security checks.
- [ ] **T174** Add database restart/persistence smoke test.
- [ ] **T175** Confirm full-message content is absent from normal INFO logs.
- [ ] **T176** Document manual demo reset/reseed/reingest procedure.

## Phase 15 — Full frontend functional completion

- [ ] **T180 [P]** Ensure customer UI cleanly represents WAITING/ACTIVE/CLOSED without future ETA feature.
- [ ] **T181 [P]** Ensure operator layout supports list + selected conversation + AI/evidence panel at functional desktop widths.
- [ ] **T182 [P]** Ensure core actions are keyboard-usable/semantically labeled.
- [ ] **T183** Ensure UI never exposes controls prohibited by effective mode/feature flag, while backend remains authoritative.

## Phase 16 — Acceptance automation and DONE

- [ ] **T190** Implement E2E automation for operator login + customer conversation happy path.
- [ ] **T191** Implement E2E multi-tab six-client/four-active/two-waiting scenario.
- [ ] **T192** Implement E2E N2 draft hidden -> operator edit/accept -> explicit send -> customer receives.
- [ ] **T193** Implement E2E N1/manual search feature-flag scenario.
- [ ] **T194** Implement E2E take-over scenario.
- [ ] **T195** Implement dual-RAG/citation acceptance tests with deterministic fixtures.
- [ ] **T196** Implement abstention + provider-failure fallback acceptance tests.
- [ ] **T197** Run all backend/frontend/E2E/lint/type gates.
- [ ] **T198** Execute/document `acceptance.md` against local Docker Compose.
- [ ] **T199** Run Spec Kit `converge` or equivalent spec-to-code review; repair drift.
- [ ] **T200** Update `PROJECT_STATE.md` to V1 DONE only if every DONE item passes; do not start V2.

## Dependency summary

```text
Phase 0
  -> runtime/skeleton
  -> persistence/security
  -> customer/operator/queue/manual N1
  -> ingestion
  -> retrieval
  -> N2 generation
  -> human send/citations/take-over
  -> hardening/frontend/E2E
  -> converge
```

Do not parallelize across an unresolved schema or API contract change.
