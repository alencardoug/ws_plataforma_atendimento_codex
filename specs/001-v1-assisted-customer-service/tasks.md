# Tasks: V1 Assisted Customer Service

Execution rule: complete in dependency order. Do not implement V2+.

Legend:

- `[P]` parallelizable after dependencies;
- `[USx]` primary user-story mapping;
- every task must update tests/docs when behavior changes.

## Phase 0 — SDD gates

- [x] **T000** Read constitution, all active feature artifacts, OpenAPI/acceptance, root architecture/security/test/data docs, ADRs, existing code, SQL, generators, and corpus structure.
- [x] **T001** Run equivalent cross-artifact/repository analysis; findings and repairs are recorded in `analysis.md` §8.
- [x] **T002** Produce requirements-to-task/test traceability matrix; FR and NFR coverage is recorded in `checklists/traceability.md`.
- [x] **T003** Confirm implementation repository contains/identifies existing PostgreSQL/knowledge source assets; map actual source schema into canonical ingestion DTO without changing V1 behavior. Verified source-of-truth mapping: `content.documents` parents (57), `content.chunks` children (570), and flat `content.qa_entries` (86); details in `plan.md` §9 and `analysis.md` §8.

**Gate:** no unresolved blocker/contradiction.

## Phase 1 — Project skeleton and local runtime

- [x] **T010** Refactor the existing `app/` FastAPI/pip project into the logical module structure in the plan; preserve legacy source history but remove legacy scheduling/payment/CPF routes from the V1 runtime.
- [x] **T011** Create frontend React/TypeScript/Vite project with `/customer` and `/operator` routes.
- [x] **T012** Evolve Docker Compose to PostgreSQL 17 + pgvector, modular `app/` backend, and frontend; document the required volume migration/recreation path without silently reusing a PostgreSQL 16 data directory.
- [x] **T013** Create `.env.example` with required variable names and safe defaults where possible.
- [x] **T014** Implement typed central runtime settings for N1/N2, N1 assistive search, max active conversations, DB, auth, AI models.
- [x] **T015** Add backend health/readiness endpoints and database connectivity check.
- [x] **T016** Add backend lint/format/type/test commands.
- [x] **T017** Add frontend lint/type/test commands.
- [x] **T018** Add correlation/request ID middleware and structured logging baseline without message bodies.

**Gate:** compose starts DB/backend/frontend; health passes.

## Phase 2 — Persistence and migrations

- [x] **T020** Implement SQLAlchemy base/session/transaction utilities plus legacy-schema preflight needed for safe Alembic adoption.
- [x] **T021** Implement models/enums for operator users, conversations, assignments, messages.
- [x] **T022** Map/evolve canonical knowledge models onto existing `content.documents` parents, `content.chunks` children, and flat `content.qa_entries`; do not create a duplicate `knowledge_*` corpus.
- [x] **T023** Implement retrieval runs/hits.
- [x] **T024** Implement AI generations + generation-source lineage.
- [x] **T025** Implement message citations.
- [x] **T026** Implement audit events.
- [x] **T027** Create forward-only Alembic baseline/adoption revisions, V1 service schema, and content-table alterations including pgvector metadata/index strategy; never edit legacy `db/init/*.sql` as migration history.
- [x] **T028** Add migration tests from empty DB and from a schema matching the legacy bootstrap preflight.

**Gate:** clean DB migrates; schema matches active data model.

## Phase 3 — Audit and shared security primitives

- [x] **T030** Implement append-only audit repository/service with typed event names.
- [x] **T031** Add audit event integration tests; verify no update/delete application API.
- [x] **T032** Implement anonymous token generation + digest verification primitive.
- [x] **T033** Implement operator password hashing/verification primitive.
- [x] **T034** Implement operator auth token/session mechanism and dependency/middleware.
- [x] **T035** Add negative tests for raw token/password persistence/logging.

## Phase 4 — Anonymous customer conversation [US1]

- [x] **T040 [US1]** Implement create-conversation application service: WAITING, initial/effective mode snapshot, token digest, audit.
- [x] **T041 [US1]** Implement public create/read/close endpoints per OpenAPI.
- [x] **T042 [US1]** Implement customer-token authorization scoped to exact conversation.
- [x] **T043 [US1]** Implement customer-message persistence endpoint; persist before any AI assistance; emit audit event.
- [x] **T044 [US1]** Implement customer-safe DTO that excludes AI/retrieval/internal metadata.
- [x] **T045 [US1] [P]** Implement customer SPA session service using per-tab `sessionStorage`.
- [x] **T046 [US1] [P]** Implement customer chat UI: start, message list, send, status, close.
- [x] **T047 [US1]** Add cross-conversation IDOR negative tests.
- [x] **T048 [US1]** Add browser test proving six tabs create six distinct independent conversation tokens/IDs.

## Phase 5 — Operator authentication [US2]

- [x] **T050 [US2]** Implement operator repository/service.
- [x] **T051 [US2]** Implement reproducible synthetic operator seed command.
- [x] **T052 [US2]** Implement login + `/operator/me` endpoints.
- [x] **T053 [US2] [P]** Implement operator login UI/session storage strategy.
- [x] **T054 [US2]** Add auth success/failure and customer-token-to-operator-route negative tests.

## Phase 6 — Queue, assignment, capacity [US3]

- [x] **T060 [US3]** Implement waiting/active conversation query service.
- [x] **T061 [US3]** Implement transactional claim service with max-active capacity.
- [x] **T062 [US3]** Implement release service and assignment-history semantics.
- [x] **T063 [US3]** Implement operator list/claim/release/close endpoints.
- [x] **T064 [US3] [P]** Implement operator left-pane waiting/active list and claim controls.
- [x] **T065 [US3]** Add integration test: six waiting -> four claims -> fifth rejected -> two waiting.
- [x] **T066 [US3]** Add concurrent claim/capacity race test proving operator cannot exceed configured max.

**Gate:** six-client/max-four behavior passes without AI/RAG.

## Phase 7 — N1 manual messaging [US4]

- [x] **T070 [US4]** Implement operator conversation detail/read authorization.
- [x] **T071 [US4]** Implement explicit operator final-message send application service without AI dependency.
- [x] **T072 [US4]** Implement operator send endpoint per OpenAPI.
- [x] **T073 [US4] [P]** Implement selected conversation center pane + manual compose/send.
- [x] **T074 [US4]** Add tests proving manual send works in N1 and when AI provider is unavailable.

## Phase 8 — Knowledge ingestion [US10, US11]

- [x] **T080 [US10]** Define canonical administrative Q&A ingestion DTO + adapter for `documents/qa/qa-catalog.jsonl`/`content.qa_entries`.
- [x] **T081 [US11]** Define clinical adapter for `documents/catalog.jsonl` + referenced Markdown parents + existing `content.chunks` children, preserving `parent_document_id` lineage without synthesized parent chunks.
- [x] **T082** Implement ingestion validation for IDs, blank content, hierarchy, exposure metadata.
- [x] **T083** Implement content hashing/idempotent upsert semantics.
- [x] **T084** Implement embedding provider port + configured OpenAI embedding adapter.
- [x] **T085** Implement embedding persistence for QNA/CHILD searchable records.
- [x] **T086** Implement offline CLI/application ingestion entry point for both source families.
- [x] **T087** Emit ingestion started/completed/failed audit events with counts.
- [x] **T088** Add ingestion idempotency tests.
- [x] **T089** Add changed-content re-embedding test.
- [x] **T090 [US11]** Add invalid missing-parent test.
- [x] **T091** Add deterministic fixtures around the existing 57-parent/570-child/86-Q&A corpus and document reconciliation checks among JSONL, Markdown, SQL baseline, and database.

**Gate:** DB contains searchable vectors for both knowledge families.

## Phase 9 — Retrieval and N1 assistive search [US5, US10, US11]

- [x] **T100** Implement query embedding application service.
- [x] **T101 [US10]** Implement administrative flat vector retrieval.
- [x] **T102 [US11]** Implement clinical child vector retrieval + parent expansion/dedupe.
- [x] **T103** Implement combined evidence projection with type/rank/score/source exposure.
- [x] **T104** Persist retrieval run/hits and emit search events.
- [x] **T105 [US5]** Implement manual knowledge search service enforcing N1 assistive flag.
- [x] **T106 [US5]** Implement `/operator/knowledge/search` endpoint.
- [x] **T107 [US5] [P]** Implement operator evidence panel/manual search UI.
- [x] **T108 [US10]** Test admin Q&A search with no parent assumption.
- [x] **T109 [US11]** Test clinical child hit expands correct parent and persists lineage.
- [x] **T110 [US5]** Test disabled N1 assistive search is forbidden/unavailable.

## Phase 10 — N2 AI copilot [US6, US8, US12]

- [x] **T120** Implement generation provider port and configured OpenAI generation adapter with structured output validation.
- [x] **T121** Implement prompt version registry/loading from `prompts/` or code-managed equivalent with stable version identifier.
- [x] **T122 [US6]** Implement conversation-context builder with bounded active conversation history.
- [x] **T123 [US6]** Implement N2 draft application service: effective-mode check -> retrieval -> generation -> persistence -> audit.
- [x] **T124 [US12]** Implement structured abstention mapping/reason codes.
- [x] **T125 [US6]** Implement generate-draft endpoint.
- [x] **T126 [US8]** Implement regeneration service preserving prior generation and retrieval/provenance rules.
- [x] **T127 [US8]** Implement regenerate endpoint.
- [x] **T128 [US6] [P]** Implement operator AI panel: generate/view draft/evidence.
- [x] **T129 [US8] [P]** Implement regenerate UI action.
- [x] **T130 [US12]** Implement abstention presentation to operator.
- [x] **T131** Add deterministic fake AI provider for tests.
- [x] **T132 [US6]** Add test: customer message persistence does not depend on AI generation.
- [x] **T133 [US6]** Add test: customer cannot fetch generation/internal evidence.
- [x] **T134 [US12]** Add unsupported-query abstention test.
- [x] **T135** Add AI provider failure test preserving manual flow.

## Phase 11 — Explicit human send from draft [US7]

- [x] **T140 [US7]** Extend operator send service to accept optional `source_generation_id` and compare final text to draft.
- [x] **T141 [US7]** Emit `ai.draft_accepted` when exact accepted content is sent and `ai.draft_edited` when modified.
- [x] **T142 [US7] [P]** Implement `Use suggestion`/edit/final send UX.
- [x] **T143 [US7]** Add negative service/API test proving an AIGeneration cannot directly create/publish customer-visible output without operator send.
- [x] **T144 [US7]** Add provenance test linking final message to generation without changing draft record.

## Phase 12 — Citation exposure [US13]

- [x] **T150 [US13]** Implement server-side customer citation policy service.
- [x] **T151 [US13]** Implement citation attachment validation during operator send.
- [x] **T152 [US13]** Implement safe customer citation snapshot/projection.
- [x] **T153 [US13] [P]** Render approved citations in customer UI and internal evidence in operator UI.
- [x] **T154 [US13]** Add positive clinical citation test.
- [x] **T155 [US13]** Add negative administrative citation leakage test.
- [x] **T156 [US13]** Add test preventing internal IDs/scores/storage metadata in public DTO.

## Phase 13 — Take over N2 -> N1 [US9]

- [x] **T160 [US9]** Implement take-over domain/application service, one-way until close.
- [x] **T161 [US9]** Implement take-over endpoint and audit event.
- [x] **T162 [US9] [P]** Implement prominent effective-mode badge + `Take over` action in operator UI.
- [x] **T163 [US9]** Disable/reject N2 draft generation after take-over.
- [x] **T164 [US9]** Verify manual send and optional N1 search still work after take-over.
- [x] **T165 [US9]** Add end-to-end take-over test.

## Phase 14 — Observability and hardening [US14]

- [x] **T170 [US14]** Verify all required audit event types emitted for implemented flows.
- [x] **T171** Add retrieval/generation duration + usage metadata capture.
- [x] **T172** Add error handling with stable error codes for auth, capacity, mode conflict, provider failure.
- [x] **T173** Add output rendering/sanitization security checks.
- [x] **T174** Add database restart/persistence smoke test.
- [x] **T175** Confirm full-message content is absent from normal INFO logs.
- [x] **T176** Document manual demo reset/reseed/reingest procedure.

## Phase 15 — Full frontend functional completion

- [x] **T180 [P]** Ensure customer UI cleanly represents WAITING/ACTIVE/CLOSED without future ETA feature.
- [x] **T181 [P]** Ensure operator layout supports list + selected conversation + AI/evidence panel at functional desktop widths.
- [x] **T182 [P]** Ensure core actions are keyboard-usable/semantically labeled.
- [x] **T183** Ensure UI never exposes controls prohibited by effective mode/feature flag, while backend remains authoritative.

## Phase 16 — Acceptance automation and DONE

- [x] **T190** Implement E2E automation for operator login + customer conversation happy path.
- [x] **T191** Implement E2E multi-tab six-client/four-active/two-waiting scenario.
- [x] **T192** Implement E2E N2 draft hidden -> operator edit/accept -> explicit send -> customer receives.
- [x] **T193** Implement E2E N1/manual search feature-flag scenario.
- [x] **T194** Implement E2E take-over scenario.
- [x] **T195** Implement dual-RAG/citation acceptance tests with deterministic fixtures.
- [x] **T196** Implement abstention + provider-failure fallback acceptance tests.
- [x] **T197** Run all backend/frontend/E2E/lint/type gates.
- [x] **T198** Execute/document `acceptance.md` against local Docker Compose.
- [x] **T199** Run Spec Kit `converge` or equivalent spec-to-code review; repair drift.
- [x] **T200** Update `PROJECT_STATE.md` to V1 DONE only if every DONE item passes; do not start V2.

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
