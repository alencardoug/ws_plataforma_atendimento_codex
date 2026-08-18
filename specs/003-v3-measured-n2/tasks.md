# Tasks: V3 Measured N2

Execution rule: complete in dependency order; migrations before dependent
code; the category registry (Phase 1/2) before anything that reads
`category_slug` (V3-3, V3-4, V3-8's category selector, V3-12). Do not
implement N3/N4 policy enforcement, the specialist-escalation workflow
(V5), dynamic appointment availability, or an automated evaluation-case
re-run mechanism — those remain excluded per `spec.md` §6/§7.

Legend:

- `[P]` parallelizable after dependencies;
- `[V3-x]` primary confirmed-outcome mapping (`spec.md` §2);
- every task must update tests/docs when behavior changes.

## Phase 0 — SDD gates

- [x] **T000** Read the constitution, `spec.md`, `plan.md`, V1/V2's
  `data-model.md`/`contracts/openapi.yaml`/`analysis.md`, root
  architecture/security/data/test/operations docs, and the current V1/V2
  implementation for every module this plan extends
  (`ai/router.py`, `operator_workspace/router.py`, `knowledge/router.py`,
  `knowledge/dynamic_binding.py`, `anonymous_access/router.py`,
  `infrastructure/models.py`, `frontend/src/main.tsx`). Done during
  `plan.md` authoring — the exact model/endpoint names cited throughout
  `plan.md` were confirmed against the real source, not guessed.
- [x] **T001** Run cross-artifact review of `spec.md` vs `plan.md`; record
  findings/repairs in V3 `analysis.md` before implementation starts. Done
  2026-08-18 (`analysis.md`, 2 findings repaired: a stale `§14`→`§19`
  cross-reference and a fabricated `T151`/`T160` task-ID reference fixed to
  the real V1 `T141`). The `plan.md` §3.1 category-registry correction is
  confirmed consistent across `data-model.md`, `tasks.md`, and
  `contracts/openapi.yaml`.
- [x] **T002** Produce a V3 requirements-to-task/test traceability matrix
  (`checklists/traceability.md`) mapping every V3-1..V3-12 outcome and
  every `spec.md` §5 acceptance outcome (1-13) to its implementing task(s).
  Done.
- [x] **T003** Confirm which V1/V2 code this plan reuses rather than
  reimplements — `send_operator_message`'s existing
  `ai.draft_accepted`/`ai.draft_edited` computation (plan.md §1, the
  reason V3-2 needs no backend endpoint), `evaluate_automatic_trigger`'s
  eligibility guard (reused by V3-9), `validate_binding`/
  `ALLOWLISTED_TABLES` (reused, not replaced, by V3-8) — confirmed against
  the real `operator_workspace/router.py`/`ai/router.py`/
  `knowledge/dynamic_binding.py` source; call sites recorded in `plan.md`.

**Gate:** no unresolved blocker/contradiction between `spec.md` and
`plan.md`. **Passed.**

## Phase 1 — Migrations

- [x] **T010** Create `content.categories` (`slug` text PK, `label` text,
  `is_active` bool default true, `created_at`) — `plan.md` §3.1.
- [x] **T011** Backfill `content.categories` from **both**
  `DISTINCT content.qa_entries.category` and
  `DISTINCT content.documents.cancer_type` (`UNION`, `ON CONFLICT DO
  NOTHING`) — `plan.md` §3.1. Verified against the actual local dev
  database (104 `qa_entries`, 62 `documents`): 27 distinct category
  values backfilled (administrative topics + `mama`/`colorretal` +
  accumulated E2E/smoke test-fixture categories), 0 `qa_entries.category`
  or `documents.cancer_type` values left unmatched by the registry.
- [x] **T012** Add FK constraints: `content.qa_entries.category` →
  `content.categories.slug`; `content.documents.cancer_type` →
  `content.categories.slug` (nullable on the `documents` side, matching
  the existing column) — `plan.md` §3.1. Confirmed via `\d` in psql: both
  constraints present and correctly referencing `content.categories`.
- [x] **T013** Add `ai_generations.instruction_text` (text, nullable),
  `ai_generations.category_slug` (text, nullable, FK →
  `content.categories.slug`), `marked_incorrect_at` (timestamptz,
  nullable), `marked_incorrect_by_operator_id` (FK → `operator_users.id`,
  nullable), `escalated_at` (timestamptz, nullable),
  `escalated_by_operator_id` (FK → `operator_users.id`, nullable) —
  `plan.md` §3.2. `customer_care/infrastructure/models.py`'s `AIGeneration`
  updated to match; `ruff`/`mypy` clean.
- [x] **T014** Create `content.evaluation_cases` (`id` UUID PK,
  `category_slug` FK nullable, `question` text, `expected_status` text,
  `expected_evidence_ids` jsonb nullable, `actual_status` text nullable,
  `actual_notes` text nullable, `last_reviewed_at` timestamptz nullable,
  `created_by_operator_id` FK, `created_at`/`updated_at`) — `plan.md` §3.3.
  No FK from any `customer_service` table into this table, and no FK from
  this table into `conversations`/`ai_generations` — confirmed via `\d`:
  the isolation from production metrics (acceptance outcome 5) holds
  structurally, not just by convention. New `EvaluationCase` model added.
- [x] **T015** Create `customer_service.conversation_satisfaction_responses`
  (`id` UUID PK, `conversation_id` FK UNIQUE, `score` smallint with
  `CHECK (score BETWEEN 1 AND 5)`, `resolved` bool, `category_slug` FK
  nullable, `submitted_at`) — `plan.md` §3.4. New
  `ConversationSatisfactionResponse` model added.
- [x] **T016** Single forward-only Alembic revision for T010-T015
  (`20260818_0001_v3_categories_taxonomy_evaluation_satisfaction.py`,
  `down_revision = "20260814_0002"`).
- [x] **T017** Verified against the actual local dev database (V1+V2
  schema with accumulated real conversation/test data, not a freshly
  provisioned isolated copy — a deliberate substitution for the
  originally-planned isolated-temp-database method, since a real
  already-populated database was available and gives at least as strong a
  signal): `alembic upgrade head` applied cleanly; row counts unchanged
  (104 `qa_entries`, 62 `documents`, 2 `ai_generations` all intact); 0
  orphaned `category`/`cancer_type` values. Reran backend `ruff`/`mypy`
  (clean) and `pytest` (21/21), plus `smoke_core.py`, `smoke_n2.py`,
  `smoke_v2_knowledge_crud.py`, `smoke_v2_dynamic_pattern.py` against the
  live stack — all pass unmodified against the new schema.

**Gate:** clean V2 database migrates to V3 schema without data loss.
**Passed.**

## Phase 2 — Category registry backend and `category_slug` derivation
[V3-8 (category), V3-1/V3-3/V3-4/V3-12 (cross-cutting dependency)]

- [x] **T020 [V3-8]** `GET /operator/knowledge/categories` (list
  `{slug, label}`, `is_active = true` only) — `plan.md` §11.
  `knowledge/router.py`'s `list_categories`.
- [x] **T021 [V3-8]** `POST /operator/knowledge/categories` (create;
  `/operator/knowledge/*` auth) — `plan.md` §11. `create_category`; 409
  `CATEGORY_EXISTS` on a duplicate slug.
- [x] **T022 [V3-1/V3-3/V3-4/V3-12]** Implement the `category_slug`
  derivation in `generate_draft` and `select_evidence`
  (`app/customer_care/ai/router.py`): on `status == "ANSWER"`, resolve the
  `use_order = 1` `AIGenerationSource` → `RetrievalHit`; if `matched_qa_id`
  is set, copy `QAEntry.category`; else if `expanded_parent_document_id` is
  set, copy `KnowledgeDocument.cancer_type`; else leave `NULL` — `plan.md`
  §3.1 (as corrected 2026-08-18 to cover the clinical-parent path).
  `derive_category_slug()`; verified live via HTTP against the local
  stack — a Q&A-grounded draft correctly returned `category_slug:
  "instituicao"`.
- [x] **T023 [P]** `KnowledgeAdminPage`
  (`frontend/src/main.tsx`): replace the free-text `category` `<input>`
  with a `<select>` fed by T020, plus an inline "criar nova categoria"
  affordance calling T021. Verified live via Playwright: the select lists
  all 27 seeded categories; creating a new one adds it live and
  auto-selects it, with no page reload.
- [x] **T024** Unit tests: T022's derivation for (a) a Q&A-grounded
  `ANSWER`, (b) a clinical-parent-grounded `ANSWER`
  (`full_parent_draft` path), (c) an `ABSTAIN`, (d) a plain-greeting
  `ANSWER` with no evidence — asserting `category_slug` is exactly right
  in each case, including `NULL` for (c)/(d).
  `tests/test_category_derivation.py` (4 tests, fake-session pattern
  matching `test_security_and_ingestion.py`'s `_FakeOperatorSession` — real
  relational behavior covered by the T022 live-HTTP check instead of a
  DB-backed unit test, consistent with this suite's existing DB-free
  convention).

**Gate:** backend `ruff`/`mypy` (39 files clean)/`pytest` (25/25); frontend
`eslint`/`tsc --noEmit`/`vitest` (14/14)/`vite build`. **Passed.**

## Phase 3 — Operator feedback taxonomy [V3-1]

- [x] **T030 [V3-1]** Implement `classify_generation(session, generation)
  -> set[str]` in `customer_care/ai/router.py` per `plan.md` §3.2/§19:
  approve/edit from `ai.draft_accepted`/`ai.draft_edited`; search from
  `trigger == "MANUAL_EVIDENCE"`; take-over from the conversation's
  `taken_over_at`; regenerate/regenerate-with-instruction from
  `prior_generation_id`/`instruction_text`; mark-incorrect/escalate from
  the new T013 columns.
- [x] **T031 [V3-1]**
  `POST /operator/conversations/{conversation_id}/generations/{generation_id}/mark-incorrect`
  in `operator_workspace/router.py` — assignment-gated
  (`require_assignment`), 404 if the generation doesn't exist, 422
  `INVALID_GENERATION` if it belongs to a different conversation,
  idempotent, `record_event(..., "generation.marked_incorrect", ...)` —
  `plan.md` §4. New shared `require_generation` helper.
- [x] **T032 [V3-1]**
  `POST /operator/conversations/{conversation_id}/generations/{generation_id}/escalate`
  — same shape, `record_event(..., "generation.escalated", ...)` —
  `plan.md` §4.
- [x] **T033 [P] [V3-1]** `OperatorPage`: render mark-incorrect/escalate
  buttons on every generation in the conversation's rendered history (not
  only the latest), calling T031/T032. Required extending
  `conversations/projections.py`'s `customer_projection` with an
  `include_generation_id` flag (default `False`, operator-only call sites
  pass `True`) so each `OPERATOR` message's `source_generation_id` reaches
  the frontend without ever reaching `/public/*` — an AI generation stays
  an internal artifact to the customer (Article III), only the operator
  surface can target one by id.
- [x] **T034** Unit tests for `classify_generation` — one fixture per tag,
  including a generation that is both `edit` and later `marked_incorrect`
  (independent, non-exclusive facts, per `plan.md` §19).
  `tests/test_taxonomy.py` (9 tests, same fake-session pattern as T024).
- [x] **T035** Verified live against the rebuilt local stack (real HTTP,
  not a DB-backed pytest integration test — same substitution rationale as
  T017/T022): mark-incorrect sets `marked_incorrect_at`; a second call
  updates the timestamp (idempotent); escalate sets `escalated_at`; a
  `generation_id` belonging to a different `conversation_id` returns `422`;
  a nonexistent `generation_id` returns `404`. Frontend buttons verified
  end-to-end via Playwright against the rebuilt containers — both buttons
  appear on the sent operator message, and each flips to a "✓" confirmed
  state after a successful call (screenshot captured).

**Gate:** backend `ruff`/`mypy` (38 files clean)/`pytest` (34/34); frontend
`eslint`/`tsc --noEmit`/`vitest` (14/14)/`vite build`. **Passed.**

## Phase 4 — Quick-approve action [V3-2]

- [x] **T040 [V3-2]** Add the `STALE_GENERATION` freshness check to
  `send_operator_message` (`operator_workspace/router.py`): if
  `payload.source_generation_id` is set and does not equal the
  conversation's current latest non-`FAILED` generation id, return `409
  STALE_GENERATION` — `plan.md` §5. Applies to every send-from-a-generation
  path (quick-approve and an edited reply-box send alike).
- [x] **T041 [P] [V3-2]** `OperatorPage`: "Aprovar" button, visible
  whenever `draft.status == "ANSWER"`, calling the existing
  `POST /operator/conversations/{id}/messages` with
  `{body: draft.draft_text, source_generation_id: draft.id,
  citation_retrieval_hit_ids: []}` via a new `quickApprove()` — no new
  backend endpoint, reuses `send`'s exact request shape.
- [x] **T042** No new negative test needed for "no code path without
  `CurrentOperator` + assignment-gating" — quick-approve reuses the
  existing `send_operator_message` endpoint verbatim, already covered by
  that endpoint's existing auth. Verified live instead (real HTTP, same
  substitution rationale as prior phases): a generation superseded by a
  newer one returns `409 STALE_GENERATION`; sending the true latest draft
  unmodified succeeds `201`. This surfaced a real, organic case during
  testing — a manual draft superseded 7s later by a genuine V2-7
  automatic-trigger draft — proving the guard fires correctly under real
  timing, not just a contrived one. Frontend "Aprovar" button verified
  end-to-end via Playwright (operator message count goes from 0 to 1).

**Gate:** backend `ruff`/`mypy` (38 files clean)/`pytest` (34/34,
unaffected — `smoke_core`+`smoke_n2` chained rerun confirms no regression
in the existing send path); frontend `eslint`/`tsc --noEmit`/`vitest`
(14/14)/`vite build`. **Passed.**

## Phase 5 — Regenerate-with-instruction [V3-6]

- [x] **T050 [V3-6]** `DraftIn` (`ai/router.py`) gains
  `instruction_text: str = ""`.
- [x] **T051 [V3-6]** `generate_draft(...)` gains `instruction_text: str =
  ""`, stores it on `AIGeneration.instruction_text` (T013), and — when
  non-empty — appends one `{"role": "operator_instruction", "content":
  instruction_text}` entry to `history` immediately before calling
  `provider.generate(...)` — `plan.md` §9. Never appended when empty (no
  behavior change for existing regenerate/manual-draft calls). Extracted
  as a small pure `build_llm_history()` helper for testability.
- [x] **T052 [V3-6]** `draft()` endpoint threads `payload.instruction_text`
  through to `generate_draft`. **Also fixed a real, pre-existing V2 gap
  discovered while doing this**: `draft()` never actually computed/passed
  `prior_generation_id`, so the "second Gerar rascunho call = regenerate"
  linkage V2's own `spec.md`/`acceptance.md` §C.7 claimed was already
  working was silently never wired (confirmed empirically — two manual
  drafts in a row both had `prior_generation_id: null`; V2's
  `acceptance.md` Execution record's §C evidence list omits this specific
  check, and `smoke_n2.py` never asserted it). Fixed by computing the
  conversation's current latest non-`FAILED` generation id in `draft()`
  and passing it through — scoped to this endpoint only (not
  `evaluate_automatic_trigger`'s `AUTOMATIC` path or `select_evidence`'s
  `MANUAL_EVIDENCE` path, which are distinct trigger types, not
  "regenerate"). This was a blocking prerequisite for V3-1's `regenerate`/
  `regenerate-with-instruction` tags to ever fire correctly.
- [x] **T053 [V3-6]** `record_event`'s existing `ai.draft_generated`/
  `ai.draft_abstained` payload (inside `generate_draft`) gains
  `"instruction_text"` — no new event type, per `plan.md` §19.
- [x] **T054 [V3-6]** `prompts/rag_answer.md`: new "Operator steering
  instruction" section documenting that an `operator_instruction`-role
  entry is operator steering, not customer speech, must be followed, and
  must never be echoed verbatim into `draft_text`.
- [x] **T055 [P] [V3-6]** `OperatorPage`: free-text "Instrução para
  regenerar (opcional)" box next to "Gerar rascunho", sent as
  `instruction_text` combined with (not replacing) current
  message-selection/manual-search-text state.
- [x] **T056** `test_ai_providers.py`: `build_llm_history` unit tests
  (empty instruction leaves history untouched by identity; non-empty
  appends exactly one `operator_instruction`-role entry) plus a
  fake-`OpenAI`-client test asserting the instruction reaches the request
  payload and never appears in `result.draft_text`. `trigger`/
  `prior_generation_id` unaffected — regenerate-with-instruction stays a
  `MANUAL_DRAFT` call, no new trigger enum value (confirmed by T052's live
  check below).

**Live verification** (real HTTP + real OpenAI, real browser — same
substitution rationale as prior phases): two consecutive manual drafts on
the same selection — draft2 (instruction "Responda em francês") has
`prior_generation_id === draft1.id` (T052's fix confirmed) and
`instruction_text` round-trips correctly; the model's response actually
switched to French, proving the instruction reaches and steers the LLM,
not just that a field is stored. Frontend input box verified end-to-end
via Playwright against the rebuilt containers (screenshot captured,
French-language draft rendered in the UI).

**Gate:** backend `ruff`/`mypy` (38 files clean; `mypy customer_care` is
the project's actual gate per `Makefile`, not `tests/`, which has one
unrelated pre-existing untyped-`SimpleNamespace`-assignment note)/`pytest`
(37/37). frontend `eslint`/`tsc --noEmit`/`vitest` (14/14)/`vite build`.
**Passed.**

## Phase 6 — Guided knowledge-CRUD inputs (rest) and transformar em Q&A
[V3-8, V3-1×V3-8]

- [x] **T060 [V3-8]** `GET /operator/knowledge/dynamic-tables` returns
  `list(ALLOWLISTED_TABLES.keys())` (`knowledge/dynamic_binding.py`) —
  `plan.md` §11.
- [x] **T061 [V3-8]**
  `GET /operator/knowledge/dynamic-tables/{table}/columns` — 404 if
  `table` not in `ALLOWLISTED_TABLES`; else
  `sqlalchemy.inspect(ALLOWLISTED_TABLES[table][0]).columns` (live,
  allowlist-scoped introspection, resolved 2026-08-18) — `plan.md` §11/§18.
- [x] **T062 [P] [V3-8]** `KnowledgeAdminPage`: `Tabela` becomes a
  `<select>` fed by T060; `Filtro`/`Colunas de saída` become
  key-value builders (column `<select>` + value/variable-name input + "add",
  removable badges) fed by T061, replacing hand-typed JSON.
  `validate_binding` (`knowledge/router.py`) unchanged — remains the
  authoritative server-side check.
- [x] **T063 [V3-1×V3-8]** Frontend-only "Transformar em Q&A" button on any
  generation whose sent text differs from its draft (an `edit`, matching
  `classify_generation`'s own criterion): opens `KnowledgeAdminPage`'s
  existing create-entry form pre-filled with `question` (the customer
  message the generation answered, with the same latest-customer-message
  fallback `select_evidence` already uses for `MANUAL_EVIDENCE`/no-
  `triggering_message_id` generations), `answer_markdown` (the sent
  `Message.body`), and `category` (the generation's `category_slug`, if
  set). No new endpoint — submits through the existing
  `POST /operator/knowledge/qa`, so the operator's explicit-confirm
  requirement (acceptance outcome 9a) is enforced by the existing create
  flow. Backend: new `qa_transform_prefill()` in
  `conversations/projections.py` computes the pre-fill server-side (single
  source of truth, same logic `classify_generation`/`select_evidence`
  already use) and attaches it to each `OPERATOR` message's
  `include_generation_id=True` projection as `qa_transform` (`null` unless
  edited). Frontend: `OperatorPage` hands the pre-fill to
  `KnowledgeAdminPage` via a one-time `sessionStorage` read/clear (React's
  sanctioned lazy-`useState`-initializer pattern, not an effect+setState or
  a ref-during-render — both were tried and rejected by this project's
  stricter React-Compiler-era eslint rules) and navigates there.
- [x] **T064** Tests: `test_qa_transform.py` (4 unit tests: no-transform on
  an unedited send, prefill from the triggering message, the
  no-`triggering_message_id` fallback, and a `null`-category case).
  T061's 404 for a non-allowlisted table (including an injection-shaped
  name) and T063's live pre-fill/creation verified live instead of via a
  DB-backed pytest integration test (same substitution rationale as prior
  phases).

**Live verification** (real HTTP + real browser, rebuilt containers):
`dynamic-tables`/`.../columns` endpoints correct, including a SQL-
injection-shaped table name still 404ing before any query runs; the
guided `Tabela`/`Filtro`/`Colunas de saída` UI (table select → live column
options → add filter/output-column → removable badges) verified end-to-end
via Playwright (screenshot captured). Full "transformar em Q&A" flow
verified with a real edited send: pre-filled question/answer/category
correct on `KnowledgeAdminPage`, and submitting created the new
`content.qa_entries` row (visible in the list) — never before that
explicit submit.

**Gate:** backend `ruff`/`mypy` (38 files clean)/`pytest` (41/41);
frontend `eslint`/`tsc --noEmit`/`vitest` (14/14)/`vite build`. **Passed.**

## Phase 7 — Evaluation datasets/suites [V3-5]

- [x] **T070 [V3-5]** New `customer_care.evaluation` package
  (`__init__.py`, `router.py`) — `plan.md` §2/§8. Registered in
  `bootstrap.py` alongside the other routers.
- [x] **T071 [V3-5]** `POST /operator/evaluation/cases` (create) and
  `GET /operator/evaluation/cases` (list, filterable by `category_slug`) —
  operator-authenticated, no conversation/assignment scoping (not
  conversation-scoped by design). `expected_status` validated as `ANSWER`/
  `ABSTAIN`, else `422`.
- [x] **T072 [V3-5]** `PATCH /operator/evaluation/cases/{id}` — sets
  `actual_status`/`actual_notes`/`last_reviewed_at`, for a reviewer's
  manual re-check; no automated re-run mechanism (spec.md §7).
- [x] **T073 [P]** `scripts/seed_evaluation_cases.py`: seeds a first batch
  from `teste_humano.md`'s existing manual findings — §4.2's "agenda always
  ABSTAINs" gap (3 concrete customer-style questions, `category_slug:
  "agenda"`) and §4.6's category-independent hard cases (ambiguous/mixed
  question, out-of-scope, prompt-extraction attempt, sensitive-clinical,
  bare greeting). Seeds via the real `POST` endpoint (not raw SQL), so it
  needs no hand-maintained operator UUID and exercises the same path an
  operator would use. Not a UI requirement, run manually.
- [x] **T074** Tests: `test_evaluation_isolation.py` — structural-isolation
  proof via direct SQLAlchemy mapper inspection (no DB connection needed):
  `EvaluationCase` has no FK into `conversations`/`ai_generations`, and
  neither of those has an FK into `evaluation_cases`, in either direction.
  This is a stronger guarantee than a runtime "never creates a
  Conversation/Message row" test — it proves the schema makes that
  mechanically impossible, not just untested.

**Live verification** (real HTTP, rebuilt container + the seed script):
seeded 8 cases; created a 9th live with `category_slug`/`expected_status`;
`?category_slug=agenda` filter returns exactly the matching rows; `PATCH`
correctly sets `actual_status`/`actual_notes`/`last_reviewed_at`; invalid
`expected_status` → `422`; no auth → `401`.

**Gate:** backend `ruff`/`mypy` (40 files clean)/`pytest` (43/43).
**Passed.**

## Phase 8 — Automatic-draft countdown indicator [V3-9]

- [x] **T080 [V3-9]** Add `automatic_draft_eligible: bool` and
  `automatic_draft_seconds_remaining: int | None` (present only when
  eligible) to `operator_conversation_detail`, `claim`, and `take_over`'s
  response dicts (`operator_workspace/router.py`), computed from the same
  clock `evaluate_automatic_trigger` (`ai/router.py`) already reads —
  `plan.md` §12. New read-only `automatic_draft_status()` mirrors
  `evaluate_automatic_trigger`'s own guard exactly (status/mode,
  activity-not-yet-covered, assigned operator) — minus the idle-elapsed
  check itself, since that's what the countdown represents, not a gate on
  showing it. Never mutates state (acceptance outcome 10).
- [x] **T081 [P] [V3-9]** `OperatorPage`: local `setInterval` countdown
  ticking between the existing 2-second polls, resynced from
  `automatic_draft_seconds_remaining` whenever the poll response's
  eligibility/remaining values change (adjusted during render — React's
  documented pattern for this, not an effect+setState, which this
  project's stricter eslint rules reject). Shows "Gerando rascunho
  automaticamente…" at 0 until `automatic_draft_eligible: false` (a new
  `latest_generation` landing) resyncs it away.
- [x] **T082** Tests: `test_automatic_draft_status.py` (8 unit tests, fake
  session + monkeypatched `assigned_operator_id`) — not-`ACTIVE`, not-`N2`,
  no activity yet, no customer message, already-covered activity, and
  no-assigned-operator all correctly ineligible; eligible-with-remaining
  and eligible-past-threshold-floors-at-zero (never negative). Countdown
  reset-on-new-activity and never-self-triggers are consequences of
  reading `evaluate_automatic_trigger`'s own state, already covered by its
  V2 tests — not re-tested here.

**Live verification** (real HTTP + real browser, rebuilt containers):
`automatic_draft_eligible`/`_seconds_remaining` false/null before any
customer message, `true`/`8` immediately after one, `true`/`5` three
seconds later. Frontend countdown verified end-to-end via Playwright:
"Rascunho automático em 6s…" → "…em 3s…" → "Gerando rascunho
automaticamente…" past the threshold (screenshot captured) — ticking,
resync, and the zero-floor "gerando" state all correct.

**Gate:** backend `ruff`/`mypy` (40 files clean)/`pytest` (51/51);
frontend `eslint`/`tsc --noEmit`/`vitest` (14/14)/`vite build`. **Passed.**

## Phase 9 — Frontend-only UX: clear/reset, scroll-to-top, confirm-close
[V3-7, V3-10, V3-11]

- [ ] **T090 [P] [V3-7]** `OperatorPage`: "Limpar" button resetting local
  draft-panel state and evidence-search-results state to empty,
  independent of message-selection state. No new endpoint, no new audit
  event (`plan.md` §10).
- [ ] **T091 [P] [V3-10]** Evidence-list `<article>`'s existing `onSelect`
  handler ("Selecionar") additionally calls
  `window.scrollTo({ top: 0, behavior: "smooth" })`, invoked only inside
  the click handler — never inside a `useEffect` keyed on poll-refreshed
  state (`plan.md` §13).
- [ ] **T092 [P] [V3-11]** `CustomerPage.close` and
  `OperatorPage.closeConversation`: add a `confirmingClose` local-state
  step with the resolved copy ("Deseja encerrar a conversa?" / "Encerrar
  conversa" / "Retornar e continuar conversa") before the existing
  `close()`/`closeConversation()` calls fire. No backend/API change
  (`plan.md` §14).
- [ ] **T093** Tests: T091 does not fire on an unrelated poll re-render
  (acceptance outcome 11); T092's "Retornar e continuar conversa" leaves
  conversation status/state completely unchanged, no request sent
  (acceptance outcome 12); T090 does not touch any durably stored
  generation/audit row (acceptance outcome 8).

**Gate:** frontend `eslint`/`tsc --noEmit`/`vitest`/`vite build` (this
phase is frontend-only; backend gates unaffected).

## Phase 10 — Post-conversation satisfaction survey [V3-12]

- [ ] **T100 [V3-12]**
  `POST /public/conversations/{conversation_id}/satisfaction` in
  `anonymous_access/router.py`, using the existing `token_bound_conversation`
  dependency — `plan.md` §15. 409 `NOT_CLOSED` if
  `conversation.status != "CLOSED"`; 409 `ALREADY_SUBMITTED` if a response
  row already exists.
- [ ] **T101 [V3-12]** Compute `category_slug` per `plan.md` §3.1/§3.4's
  denormalization (the conversation's most recent `ANSWER` generation with
  a non-null `category_slug`; `NULL` if none).
- [ ] **T102 [V3-12]**
  `record_event(session, "conversation.satisfaction_submitted", "CUSTOMER",
  conversation_id=..., payload={...})` — matching the existing pattern
  every other customer-facing write already follows.
- [ ] **T103 [P] [V3-12]** `CustomerPage`: after `close()` succeeds (post
  T092's confirmation), render the optional survey (1-5 buttons,
  green-to-red emoji; "Sua necessidade foi resolvida?" Sim 🙂 / Não 🙁)
  with a visible skip action that sends no request.
- [ ] **T104** Tests: `NOT_CLOSED`/`ALREADY_SUBMITTED` negative tests;
  positive test asserting `category_slug` denormalization matches the
  conversation's actual most-recent categorized generation; skipping the
  survey never blocks or delays the close that already completed
  (acceptance outcome 13).

**Gate:** backend `ruff`/`mypy`/`pytest`; frontend
`eslint`/`tsc --noEmit`/`vitest`/`vite build`.

## Phase 11 — Documented read-only metrics [V3-3, V3-4]

- [ ] **T110 [V3-3/V3-4]** `docs/metrics/v3_queries.sql`: abstention rate
  overall/by category (including the explicit "sem categoria" row);
  Human Correction Rate overall/by category (`plan.md` §6 formula);
  generation volume by `trigger`/`category_slug`; V3-12 average score and
  resolved-rate overall/by category — `plan.md` §7. Each query
  parameterizable by date range and optionally `category_slug`.
- [ ] **T111** Test asserting the SQL `CASE`/aggregate expressions in
  T110 agree with `classify_generation()`'s (T030) Python logic against
  the same fixture data — `plan.md` §19, guards against silent drift
  between the two representations.
- [ ] **T112** Confirm no write endpoint exists anywhere in this surface
  (acceptance outcome 4 — read-only enforced by construction, not by
  omission).

**Gate:** `psql`/pytest-driven query tests pass against a seeded fixture
database; no backend/frontend route added.

## Phase 12 — Audit/observability consolidation and V1/V2 regression
spot-check

- [ ] **T120** Confirm the full set of new `audit_events.event_type`
  values (`generation.marked_incorrect`, `generation.escalated`,
  `conversation.satisfaction_submitted`) are documented alongside the
  existing catalog; confirm no new event type was needed for quick-approve
  or regenerate-with-instruction (`plan.md` §19).
- [ ] **T121** Rerun the existing `smoke_core`, `smoke_n2`,
  `smoke_concurrent_capacity`, `smoke_resilience`, `smoke_real_provider`,
  `smoke_v2_dynamic_pattern`, `smoke_v2_knowledge_crud`,
  `smoke_v2_automatic_trigger`, `smoke_v2_token_rate_limit` scripts against
  the rebuilt backend image — V1/V2 acceptance outcomes this spec's §3
  lists as preserved still pass unmodified (acceptance outcome 7, spot
  check, not a full rerun of V1/V2's own suites beyond what these scripts
  already cover).
- [ ] **T122** Confirm `instruction_text`/`manual_search_text` never appear
  in any public/customer-facing response schema (`plan.md` §18).

**Gate:** all `smoke_*` scripts pass unmodified; no new customer-facing
data leak found.

## Phase 13 — Acceptance automation and DONE

- [ ] **T130** Write `acceptance.md` covering `spec.md` §5's 13 outcomes as
  executable scenarios (backend integration tests + frontend
  `vitest`/Playwright scenarios as appropriate per outcome).
- [ ] **T131** New E2E smoke script(s) — `smoke_v3_taxonomy_hcr.py`
  (V3-1/V3-2/V3-3), `smoke_v3_knowledge_guided.py` (V3-8),
  `smoke_v3_satisfaction.py` (V3-12) — mirroring the existing
  `smoke_v2_*` naming convention.
- [ ] **T132** Frontend `v3.spec.ts` covering V3-7/V3-9/V3-10/V3-11's
  client-only behaviors (Playwright), plus quick-approve/mark-incorrect/
  escalate/transformar-em-Q&A/regenerate-with-instruction UI flows.
- [ ] **T133** `checklists/{requirements,security,traceability}.md`
  finalized against the implemented state (not just the plan).
- [ ] **T134** `analysis.md` — cross-artifact convergence review across
  `spec.md`/`plan.md`/`data-model.md`/`contracts/openapi.yaml`/
  `acceptance.md`/`tasks.md`, before declaring V3 done. Update
  `PROJECT_STATE.md`, `ROADMAP.md`, `DECISIONS.md` to record V3 closure,
  matching how V2's closure was recorded.

**Gate:** backend `ruff`/`mypy`/`pytest`; frontend
`eslint`/`tsc --noEmit`/`vitest`/`vite build`; the full backend E2E smoke
suite (all `smoke_*` scripts including the new V3 ones) against the
rebuilt backend image; all new `v3.spec.ts` scenarios; `acceptance.md`'s
Execution record covers all 13 `spec.md` §5 outcomes.

## Dependency summary

```text
Phase 0
  -> migrations (Phase 1)
  -> category registry + category_slug derivation (Phase 2)
      -> operator feedback taxonomy (Phase 3)          [reads category_slug nowhere directly, but classify_generation feeds Phase 11]
          -> quick-approve (Phase 4)                    [independent of Phase 3's new endpoints, needs T030 only for classification]
          -> regenerate-with-instruction (Phase 5)
          -> guided knowledge-CRUD + transformar em Q&A (Phase 6)   [needs Phase 3's edit classification + Phase 2's category endpoints]
      -> evaluation datasets (Phase 7)                  [needs Phase 2's category registry]
  -> automatic-draft countdown (Phase 8)                [independent, needs only existing evaluate_automatic_trigger]
  -> frontend-only UX: clear/reset, scroll-to-top, confirm-close (Phase 9)   [independent]
  -> satisfaction survey (Phase 10)                     [needs Phase 9's T092 confirm-close and Phase 2's category_slug denormalization]
  -> documented read-only metrics (Phase 11)            [needs Phases 2, 3, 10 — HCR/abstention/volume/CSAT all depend on prior phases' data]
  -> audit/observability consolidation + regression spot-check (Phase 12)
  -> acceptance automation and convergence (Phase 13)
```

Do not parallelize across an unresolved schema or API contract change.
