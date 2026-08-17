# Tasks: V2 Commercial Product Experience

Execution rule: complete in dependency order; migrations before dependent
code. Do not implement V3+, N3/N4, or any appointment-booking/resolver
behavior beyond the V2-6 dynamic-pattern correction — those remain excluded
per `spec.md` §6 and `ROADMAP.md`'s separate "Dynamic appointment
availability" future feature.

Legend:

- `[P]` parallelizable after dependencies;
- `[V2-x]` primary confirmed-outcome mapping (`spec.md` §2);
- every task must update tests/docs when behavior changes.

## Phase 0 — SDD gates

- [x] **T000** Read constitution, `spec.md`, `plan.md`, V1's `data-model.md`/
  `contracts/openapi.yaml`/`analysis.md`, root architecture/security/data/
  test/operations docs, and the current V1 implementation for every module
  this plan extends.
- [x] **T001** Run cross-artifact review of `spec.md` vs `plan.md`; record
  findings/repairs in V2 `analysis.md` before implementation starts.
- [x] **T002** Produce a V2 requirements-to-task/test traceability matrix
  (`checklists/traceability.md`) mapping every V2-1..V2-8 outcome and every
  `spec.md` §5 acceptance outcome to its implementing task(s).
- [x] **T003** Confirm which V1 modules/functions this plan reuses rather
  than reimplements (`full_parent_draft`, `provider.generate`,
  `customer_care.knowledge.ingest`'s content-hash/re-embed logic, the
  existing operator polling cadence) and record the exact call sites in
  `plan.md` if not already precise enough to implement against.

**Gate:** no unresolved blocker/contradiction between `spec.md` and `plan.md`.

## Phase 1 — Migrations

- [x] **T010** Add `conversations.last_customer_activity_at`,
  `last_customer_typing_at`, and `auto_draft_covers_through_message_id`
  (FK → `messages.id`, nullable) — `plan.md` §3.2.
- [x] **T011** Create `customer_service.message_selections` (`ai_generation_id`
  FK, `message_id` FK, unique pair) — `plan.md` §3.2.
- [x] **T012** Add `ai_generations.trigger` (enum `AUTOMATIC` /
  `MANUAL_DRAFT` / `MANUAL_EVIDENCE`), `manual_search_text` (nullable text),
  and `dynamic_pattern_used` (bool default false); relax
  `triggering_message_id` from `NOT NULL` to nullable (`MANUAL_EVIDENCE` has
  none) — `plan.md` §3.3/§3.4. `trigger` is `NOT NULL` with no ongoing
  default (existing rows backfilled to `MANUAL_DRAFT` during the migration,
  then the column default was dropped) — this needed real backfill, unlike
  the "no backfill requirement" this task originally assumed; see T015.
  As a compatibility stopgap, `ai/router.py`'s two `AIGeneration(...)`
  constructors now pass `trigger="MANUAL_DRAFT"` explicitly so V1's
  existing draft-generation code keeps working until Phase 4 threads the
  real trigger value through.
- [x] **T013** Create `content.qa_dynamic_bindings` (`qa_id` FK unique,
  `source_table`, `filter` jsonb, `output_columns` jsonb, `row_limit` default
  4) — `plan.md` §3.4.
- [x] **T014** Add forward-only Alembic revisions for T010–T013
  (`20260814_0001_v2_selection_triggers_dynamic_pattern.py`); verified
  against the running (empty) V1-migrated database.
- [x] **T015** Verified against a populated V1 database: created an isolated
  temp database, applied only the V1 baseline migration, inserted a
  synthetic pre-V2 `ai_generations` row, applied the V2 migration, and
  confirmed the row survived with `trigger` correctly backfilled to
  `MANUAL_DRAFT` and all original data intact; temp database dropped after.
  Reran backend `ruff`/`mypy`/`pytest` (13/13) and the `smoke_core`,
  `smoke_n2`, `smoke_resilience` E2E scripts against the live stack — all
  pass with the new schema. Not yet captured as a standalone pytest file
  (V1 didn't have one for its own baseline migration either); a permanent
  automated version of this check would be a reasonable Phase 11 addition
  if migration regressions become a recurring risk.

**Gate:** clean V1 database migrates to V2 schema without data loss. **Passed.**

## Phase 2 — Token format and rate limiting [V2-2]

- [x] **T020 [V2-2]** Replace the token generator with the 8-character,
  31-symbol alphabet in `plan.md` §3.1 (excludes `0/O`, `1/I`, `L`); keep the
  constant in one place. Implemented in
  `anonymous_access/security.py` (`TOKEN_ALPHABET`/`TOKEN_LENGTH`).
- [x] **T021 [V2-2]** Confirm `/public/conversations` creation and the
  existing HMAC-digest storage/comparison path work unchanged against the
  new format (digest algorithm/column untouched, only input format changes).
  Verified live via `smoke_core`/`smoke_n2` and a direct curl round trip.
- [x] **T022 [V2-2]** Implement an IP-keyed sliding-window rate limiter for
  token validation failures on `/public/*` (429 beyond threshold, escalating
  backoff/lockout); make thresholds configurable settings, not hardcoded.
  New module `anonymous_access/rate_limit.py`: sliding-window failure count
  plus exponentially escalating lockout duration (capped), keyed by
  `(bucket, source_key)`.
- [x] **T023 [V2-2]** Wire the limiter into the existing customer-token
  authorization dependency; ensure successful validations do not count
  against the limiter. Wired into `token_bound_conversation` in
  `anonymous_access/router.py`, keyed by client IP; a successful lookup
  clears prior failure/lockout state for that key.
- [x] **T024 [V2-2]** Add rate-limit configuration to typed settings and
  `.env.example`. Also allowlisted the four new env vars explicitly in
  `docker-compose.yml`'s backend service, consistent with V1's
  explicit-allowlist convention.
- [x] **T025 [V2-2]** Add negative tests: lockout engages at the configured
  threshold, resets on schedule, and does not block a legitimate customer
  using the correct token. `tests/test_anonymous_token_rate_limit.py` (8
  tests, deterministic fake clock): threshold engagement, window expiry,
  exponential escalation, cap enforcement, success clears state, and
  per-source-key isolation. Also verified live end-to-end with `curl`
  against the running server (5×403 then 429 — the threshold in effect at
  that moment; the production default was raised to 30 immediately
  afterward per `plan.md` §13.1, same mechanism, not independently
  re-verified live at 30 since the unit tests already cover the mechanism
  generically for any threshold). Correct token also blocked during an
  active lockout, by design — see T023's success-clears-state behavior for
  the legitimate-customer-not-blocked-once-clear case.
- [x] **T026 [V2-2]** Add a regression test confirming the raw token is still
  never persisted, logged, or placed in a URL despite the format change.
  Covered by the existing `test_anonymous_token_is_returned_only_as_one_way_digest`
  (unaffected by the format change) plus the unchanged structural absence of
  any raw-token column on `Conversation`.
- [x] **T027 [V2-2] [P]** Customer SPA: render the token continuously in the
  conversation header (no reveal/hide toggle) with a copy action; confirm no
  new lookup/recovery affordance is added. Implemented in `CustomerPage`
  (`frontend/src/main.tsx`); regression test added to `main.test.tsx`. Full
  visual redesign is deferred to Phase 9 — this is the minimal functional
  version.

**Gate:** `ruff`/`mypy`/`pytest` (21/21) and frontend
`lint`/`typecheck`/`vitest` (6/6)/`build` all pass; `smoke_core`, `smoke_n2`,
`smoke_concurrent_capacity`, `smoke_resilience`, and `smoke_real_provider`
all pass end-to-end against the rebuilt stack with the new token format and
schema. **Passed.**

## Phase 3 — Operator-selected conversation context [V2-4]

Implemented together with Phase 4 (T040-T045): both phases edit the same
`generate_draft`/`draft()` code in `ai/router.py`, which cannot have two
signatures at once — splitting the implementation across two separate
passes would have left the system broken in between.

- [x] **T030 [V2-4]** Change `GenerateDraftRequest` to
  `selected_message_ids: UUID[]` (may be empty) + `manual_search_text: str`
  (may be empty); update the endpoint/service signature accordingly.
  `DraftIn` in `ai/router.py`.
- [x] **T031 [V2-4]** Validate every submitted message ID belongs to the
  target conversation; reject (`422`) when both inputs are empty. `draft()`
  raises `EMPTY_SELECTION` / `MESSAGE_NOT_IN_CONVERSATION`.
- [x] **T032 [V2-4]** Persist `message_selections` rows for every generation,
  regardless of trigger (Phase 4/6 depend on this). Done in
  `generate_draft`; `MANUAL_EVIDENCE` (Phase 5) intentionally does not use
  this helper.
- [x] **T033 [V2-4] [P]** Operator UI: checkbox on every message in the
  conversation view.
- [x] **T034 [V2-4] [P]** Operator UI: default selection = the contiguous
  trailing run of `CUSTOMER` messages after the last `OPERATOR` message,
  computed client-side from data already in the message list
  (`defaultMessageSelection`, applied when a conversation is opened/claimed,
  not on every poll refresh — polling must not discard operator edits).
- [x] **T035 [V2-4] [P]** Operator UI: "desmarcar conversas" clears all
  message checkboxes (pure client-side action, no endpoint).
- [x] **T036 [V2-4]** Add tests: default-selection correctness, clear-all
  behavior (`main.test.tsx`, new V2-4 test), both-empty rejection and a
  cross-conversation message-ID rejection (`smoke_n2.py`, new V2-4 section —
  required creating a fresh conversation with two real customer messages and
  releasing capacity for it, since the operator endpoint only creates
  OPERATOR messages and the four pre-claimed conversations were already at
  capacity).

## Phase 4 — "Gerar rascunho" manual trigger [V2-7 manual]

- [x] **T040 [V2-7]** Update the draft-generation application service to
  build its query/context from `selected_message_ids` (joined message
  bodies, ordered by `created_at`) concatenated with `manual_search_text`
  when both are present, replacing V1's single `triggering_message_id`.
  `history` (LLM context) is now built from exactly the selected messages,
  not V1's fixed last-20-messages window — this follows `spec.md` V2-4's
  "messages supplied to draft generation" wording.
- [x] **T041 [V2-7]** Persist `trigger = MANUAL_DRAFT` on the resulting
  generation.
- [x] **T042 [V2-7]** Remove `POST /operator/drafts/{generation_id}/regenerate`
  (service, route, and OpenAPI entry — the OpenAPI contract already omitted
  it since the original V2 planning pass) — re-invoking the drafts endpoint
  against the current selection now serves this purpose.
- [x] **T043 [V2-7] [P]** Operator UI: wire "Gerar rascunho" to the new
  request shape; remove the "Regenerar" control entirely.
- [x] **T044 [V2-7]** Design clarification found during implementation:
  since the removed `/regenerate` endpoint was the only thing that ever
  supplied a `prior_generation_id`, and the new `/drafts` endpoint has no
  client-supplied "prior generation" concept, `prior_generation_id` is now
  always `null` for `MANUAL_DRAFT`/`AUTOMATIC` generations from this path —
  the self-FK column stays in the schema for potential future use, but
  sequential drafts for a conversation are ordered/differentiated via
  `created_at`, not an explicit lineage FK. Verified via `smoke_n2.py`'s
  multi-select generation plus the existing audit-event-type assertions
  (each call emits its own `ai.draft_generated`).
- [x] **T045 [V2-7]** Add a test confirming the `/regenerate` route no longer
  exists: `smoke_n2.py` asserts a live `404` from the running server (not
  just an omission from the OpenAPI source file).

**Gate (Phases 3+4):** `ruff`/`mypy`/`pytest` (21/21), frontend
`lint`/`typecheck`/`vitest` (7/7)/`build`, and the full E2E smoke suite
(`smoke_core`, `smoke_n2` with new V2-4 assertions, `smoke_concurrent_capacity`,
`smoke_resilience`, `smoke_real_provider`) all pass against the rebuilt
stack. `smoke_resilience.py` and `smoke_real_provider.py` also needed their
draft-request payloads updated from the removed `triggering_message_id`
field. **Passed.**

## Phase 5 — "Buscar evidências" [V2-3]

- [x] **T050 [V2-3]** Implement `POST
  /operator/knowledge/evidence/{retrieval_hit_id}/select`: given a hit from a
  prior `/operator/knowledge/search` call, execute the deterministic
  selection outcome server-side. `select_evidence` in `ai/router.py`, using
  a new `load_evidence()` helper in `rag/service.py` to reconstruct the
  `Evidence` from an already-persisted `RetrievalHit`. Requires
  `conversation_id` in the body (an `AIGeneration` always needs one) and the
  same active-effective-N2 gate as `/drafts` — found and fixed during
  implementation: the OpenAPI contract had left `conversation_id` optional,
  which cannot work since `AIGeneration.conversation_id` is a required
  column (`analysis.md`-style fix, applied directly to
  `contracts/openapi.yaml`).
- [x] **T051 [V2-3]** Clinical branch: reuse `full_parent_draft` as a plain
  function call (no LLM); persist `trigger = MANUAL_EVIDENCE`,
  `provider = clinical-parent-document`, `model = not-applicable`.
- [x] **T052 [V2-3]** Administrative Q&A branch without a dynamic binding:
  reuse the existing `provider.generate` path scoped to this single hit.
  Design decision made during implementation (not fully specified in
  `plan.md`): since this path has no `selected_message_ids` by design, the
  LLM history is the conversation's single latest `CUSTOMER` message (if
  any), not empty and not the full conversation — giving the LLM a request
  to focus on without coupling to V2-4's checkbox state.
- [x] **T053 [V2-3]** Administrative Q&A branch with a dynamic binding: defer
  to the Phase 7 resolver (`knowledge/dynamic_binding.py`). Closed once
  Phase 7 landed: `select_evidence()` in `ai/router.py` calls
  `dynamic_pattern_result()` for its single hit exactly as
  `generate_draft()` does, so the deterministic substitution/fallback
  behavior is shared, not reimplemented.
- [x] **T054 [V2-3]** Add a test proving this endpoint never reads or writes
  `message_selections` — full independence from V2-4's context selection.
  `smoke_n2.py`: asserts `selected_message_ids == []` on both branches'
  responses.
- [x] **T055 [V2-3] [P]** Operator UI: "Buscar evidências" button plus a
  results list where selecting exactly one item triggers the outcome (no
  multi-select control exists in the UI at all). `ManualEvidence` gained an
  optional `onSelect`/"Selecionar" button, wired to the new endpoint.
- [x] **T056 [V2-3]** Add a test confirming the endpoint's request shape
  structurally accepts only one `retrieval_hit_id`, not a list. Structural
  guarantee: the field is a path parameter (`{retrieval_hit_id}`), not a
  request-body list — there is no code path that could accept more than one;
  confirmed by reading the route signature (same evidentiary standard V1
  used for equivalent structural guarantees).
- [x] **T057 [V2-3]** Add a test confirming the clinical branch has no
  LLM-composed-short-reply alternative anywhere in V2. `smoke_n2.py`:
  asserts `model == "not-applicable"` for the clinical selection response.

**Gate:** `ruff`/`mypy`/`pytest` (21/21), frontend
`lint`/`typecheck`/`vitest` (8/8)/`build`, and the full E2E smoke suite all
pass. T053 (dynamic-binding branch) was intentionally left open pending
Phase 7 at the time this phase closed, then closed retroactively once
Phase 7 landed (see T053 above). **Passed** (T050-T057).

## Phase 6 — Typing heartbeat and automatic debounce trigger [V2-7 automatic]

- [x] **T060 [V2-7]** Implement `POST /public/conversations/{id}/typing`:
  updates `last_customer_typing_at` and `last_customer_activity_at`.
  Design clarification found during implementation: no separate
  higher-allowance limiter was needed — the existing per-source limiter
  (Phase 2) only counts *failed* validations, so a correct token's frequent
  heartbeats never count against it. `contracts/openapi.yaml` and `plan.md`
  §7.2/§13.1 updated to describe this instead of the originally-assumed
  separate allowance.
- [x] **T061 [V2-7]** Confirm customer-message send already updates
  `last_customer_activity_at`. Correction during implementation: it was
  *not* already implicit — `send_customer_message` only set
  `last_message_at`, not `last_customer_activity_at`; added the missing
  assignment.
- [x] **T062 [V2-7]** Implement the lazy trigger-check: on the existing
  operator conversation-detail poll and on the typing heartbeat, evaluate
  whether `now - last_customer_activity_at >= 8s` AND a customer message
  newer than `auto_draft_covers_through_message_id` exists AND the
  conversation is active effective-N2. `evaluate_automatic_trigger` in
  `ai/router.py`; on the heartbeat, evaluated *before* the heartbeat resets
  the activity timestamp (otherwise the in-heartbeat check would always see
  "just now" and never fire).
- [x] **T063 [V2-7]** On a positive check, run the same generation path as
  Phase 4 with `selected_message_ids` set to the consecutive customer-message
  run, persist `trigger = AUTOMATIC`, and advance
  `auto_draft_covers_through_message_id` — set *before* attempting
  generation (win or lose) so a provider failure doesn't retry every poll.
  Generation failures inside the trigger are swallowed (already persisted as
  a `FAILED` row by `generate_draft`) so they never break the caller's own
  request (a customer's heartbeat or an operator's poll).
- [x] **T064 [V2-7]** Add `is_customer_typing` to `OperatorConversationDetail`.
  Functional gap found and fixed during implementation: `latest_generation`
  (already in the V1-inherited schema but never actually implemented, even
  in V1) also had to be implemented now — without it, an `AUTOMATIC`
  generation created server-side has no way to reach the operator's browser
  at all. New `latest_generation_dict`/`evidence_for_generation` helpers;
  wired into `claim`, `take-over`, and the conversation-detail endpoints.
- [x] **T065 [V2-7] [P]** Operator UI: live "cliente está digitando…"
  indicator; "Usar sugestão" action to accept/send the current automatic
  draft (reuses the existing generic draft-display UI). Polling adopts a new
  `latest_generation` into local `draft` state only when its id differs from
  the last one already surfaced, so an already-sent/dismissed draft doesn't
  reappear on the next poll.
- [x] **T066 [V2-7]** Add tests: the trigger fires exactly once per activity
  run (not once per poll), accumulates the correct message set across
  multiple typing bursts (matching `spec.md`'s 4-then-6-message example,
  scaled to 2-then-4 for smoke-test runtime), and does not fire while
  typing activity is recent. New `smoke_v2_automatic_trigger.py` (real time
  passage, ~18s runtime) — the first genuinely time-based E2E test in this
  suite.
- [x] **T067 [V2-7]** Add a test confirming no token-by-token streaming
  occurs anywhere in the response (draft returned whole). Covered in
  `smoke_v2_automatic_trigger.py`.
- [x] **T068 [V2-7]** Load-shape note (no dedicated perf test, matching
  `plan.md` §16's "no premature optimization"): the lazy check is one
  indexed timestamp comparison plus, on a positive hit, the same generation
  work "Gerar rascunho" already performs — negligible relative to the
  existing ~2s poll and the retrieval/LLM call itself.

**Gate:** `ruff`/`mypy`/`pytest` (21/21), frontend
`lint`/`typecheck`/`vitest` (9/9)/`build`, and the full E2E smoke suite
(`smoke_core`, `smoke_n2`, `smoke_concurrent_capacity`, `smoke_resilience`,
`smoke_real_provider`, `smoke_v2_automatic_trigger`) all pass. No
scheduler/WebSocket introduced — confirmed by construction, not just by
absence of one in the diff. **Passed.**

## Phase 7 — Dynamic-evidence safety correction [V2-6]

**Scope decision made during implementation:** no *production* Q&A entry
(none of the existing `dynamic_data_required=true` entries in the demo
corpus) is wired to a binding in this phase. Leaving them unconfigured is
the *correct* closure of the original V1 finding — per T075/§9.4, an
unconfigured entry now falls back safely exactly like a configured-but-failed
one, instead of literal passthrough. Building real backing tables/resolvers
for scheduling, pricing, etc. remains excluded (`spec.md` §6). The mechanism
is proven against one clearly-labeled fixture table
(`content.knowledge_dynamic_fixture` / `DynamicFixtureRow`) that exists
solely for this purpose — not scheduling-flavored, to keep the scope
boundary unambiguous — with no production data pointed at it.

- [x] **T070 [V2-6]** Implement the `qa_dynamic_bindings` model/repository.
  (Model added in Phase 1; this phase adds the fixture table via a new
  migration, `20260814_0002`.)
- [x] **T071 [V2-6]** Implement the server-side table allowlist (Python
  mapping of table name → SQLAlchemy model, plus a hardcoded stable-order
  column per entry); never accept a table/column identifier from anywhere
  else. `ALLOWLISTED_TABLES` in `knowledge/dynamic_binding.py` — empty of
  any production source by design (see scope decision above).
- [x] **T072 [V2-6]** Implement `knowledge/dynamic_binding.py`: resolve a
  `qa_id`'s binding into a parameterized, filtered, `LIMIT`-bounded query
  against the allowlisted model. `resolve_dynamic_pattern`.
- [x] **T073 [V2-6]** Implement pattern substitution: single-row and
  multi-row rendering per `output_columns`. Pinned: each matching row
  renders the full pattern independently (all `{{variable_name}}`
  placeholders substituted from that row), and rendered rows are joined with
  a blank line (`"\n\n"`).
- [x] **T074 [V2-6]** Wire the resolver into both generation paths that can
  reach a Q&A entry with a binding: `select_evidence` (Phase 5) and
  `generate_draft`'s RAG+LLM path (Phase 4/6) when the top evidence is
  ADMIN_QA and `dynamic_data_required`. New shared `dynamic_pattern_result`
  helper in `ai/router.py` — resolver output takes priority over LLM
  composition in both, and `full_parent_draft`'s clinical shortcut is still
  checked first (unaffected, different evidence type).
- [x] **T075 [V2-6]** Implement the unified fallback: no binding configured,
  allowlist miss, table/column mismatch, query error, or zero matching rows
  all raise `DynamicResolutionError` with a specific cause, uniformly mapped
  to `status = ABSTAIN`, `abstention_reason = DYNAMIC_DATA_UNAVAILABLE`,
  `dynamic_pattern_used = false`. The cause reaches only a new
  `ai.dynamic_pattern_fallback` audit event, never `draft_text` or any
  response field.
- [x] **T076 [V2-6]** Add tests: successful single-row and multi-row
  resolution against the fixture table. New `smoke_v2_dynamic_pattern.py`.
- [x] **T077 [V2-6]** Add tests for each failure mode individually (missing
  binding, allowlist miss, missing column, empty result — all in
  `smoke_v2_dynamic_pattern.py`; query-error is exercised structurally by
  the allowlist-miss and missing-column cases, which both fail before/at
  query construction).
- [x] **T078 [V2-6]** Add a negative test proving the audit-only cause string
  never appears in `draft_text` or any customer-facing field/response.
  `smoke_n2.py`'s new V2-6 section: exercises the full HTTP path
  (`/operator/knowledge/evidence/{id}/select`) with a binding pointing at a
  non-allowlisted table, asserts the cause string is absent from the entire
  JSON response body.
- [x] **T079 [V2-6]** Add the regression test that closes the original V1
  finding: a `dynamic_data_required=true` entry with no binding behaves
  identically to a configured-but-failed one (never literal passthrough).
  `smoke_v2_dynamic_pattern.py` step 1.

**Gate:** `ruff`/`mypy`/`pytest` (21/21) and the full E2E smoke suite
(`smoke_core`, `smoke_n2` with the new V2-6 section, `smoke_concurrent_capacity`,
`smoke_resilience`, `smoke_real_provider`, `smoke_v2_automatic_trigger`,
`smoke_v2_dynamic_pattern`) all pass. **Passed.**

## Phase 8 — Knowledge-base CRUD [V2-8]

Depends on Phase 1 (`qa_dynamic_bindings`) and reuses Phase 7's binding
model.

- [x] **T080 [V2-8]** Implement Q&A CRUD service (create/read/update/
  deactivate) including nested create/update of its `qa_dynamic_bindings`
  row. `customer_care/knowledge/router.py`'s `qa_dict`/`upsert_binding` plus
  the `POST/GET/PATCH/DELETE /operator/knowledge/qa[/{id}]` handlers;
  server-generated IDs (`qa-{uuid4().hex[:12]}`).
- [x] **T081 [V2-8]** Implement clinical parent-document CRUD service.
  `document_dict` + `/operator/knowledge/clinical-documents[/{id}]`
  handlers; creation fills the V1-legacy-required fields
  (`document_type`, `audience`, `language`, `responsible_physician`,
  `status`, dates, `patient_markdown_path=f"crud:{document_id}"`) with
  fixed defaults since the CRUD form only captures title/content.
- [x] **T082 [V2-8]** Implement clinical child-chunk CRUD service, nested
  under its parent. `chunk_dict` +
  `/operator/knowledge/clinical-documents/{id}/chunks[/{chunk_id}]`;
  IDs are `{document_id}-C{ordinal:02d}`; duplicate ordinal within the
  same document returns `422`.
- [x] **T083 [V2-8]** Implement the endpoints in `plan.md` §10 under
  `/operator/knowledge/qa` and `/operator/knowledge/clinical-documents`
  (+ nested `/chunks`), `operatorBearer`-secured, no new role. Router
  registered in `bootstrap.py` as `knowledge_crud_router`.
- [x] **T084 [V2-8]** Wire create/update to `customer_care.knowledge.ingest`'s
  existing content-hash/re-embed logic by calling it, not reimplementing it.
  Shared `qa_content_hash`/`chunk_content_hash`/`needs_reembedding`/
  `apply_embedding` helpers added to `ingest.py` and reused by both the
  batch ingest loops and the CRUD router.
- [x] **T085 [V2-8]** Implement "delete" as `is_active = false` (soft
  delete), consistent with the existing column on all three content tables.
  Deactivated records are excluded from the default list endpoints but
  remain fetchable by ID (`is_active: false` in the response).
- [x] **T086 [V2-8]** Emit an audit event for every CRUD mutation
  (`knowledge.qa_created/updated/deactivated`,
  `knowledge.clinical_document_created/updated/deactivated`,
  `knowledge.clinical_chunk_created/updated/deactivated`). Verified by
  `smoke_v2_knowledge_crud.py`'s audit-event-type assertion.
- [x] **T087 [V2-8] [P]** Operator UI: knowledge CRUD screen (Q&A + clinical
  parent/child), reachable from operator navigation, separate from the
  conversation workspace. `KnowledgeAdminPage` in `frontend/src/main.tsx`,
  routed at `/operator/knowledge`, linked from the main nav ("Registros").
- [x] **T088 [V2-8] [P]** Operator UI: dynamic-binding editor (table, filter,
  output-column mapping) embedded in the Q&A entry form.
  `KnowledgeAdminPage`'s "Vínculo dinâmico" fieldset (table/filter-JSON/
  output-columns-JSON inputs) submitted as the Q&A creation's
  `dynamic_binding` field.
- [x] **T089 [V2-8]** Add authorization tests (existing operator credentials
  work; no anonymous/customer-token path reaches these endpoints).
  `smoke_v2_knowledge_crud.py`: anonymous request and customer-token
  request both assert `401`.
- [x] **T090 [V2-8]** Add tests: re-embed triggers only when content hash
  actually changes (idempotency preserved), and soft-deleted records stop
  appearing in retrieval/search without breaking existing FK references from
  historical `ai_generation_sources`/`message_citations`.
  `smoke_v2_knowledge_crud.py`: no-op `PATCH` leaves `embedded_at`
  unchanged, a real content change updates it; deactivated Q&A is absent
  from the default listing while still `GET`-able by ID (soft delete
  preserves the FK target for historical generations/citations).

**Gate:** `ruff`/`mypy` (customer_care package)/`pytest` (21/21) and the
full E2E smoke suite (`smoke_core`, `smoke_n2`, `smoke_concurrent_capacity`,
`smoke_resilience`, `smoke_real_provider`, `smoke_v2_automatic_trigger`,
`smoke_v2_dynamic_pattern`, `smoke_v2_knowledge_crud`) all pass against the
rebuilt backend image. Frontend gates (`tsc --noEmit`, `eslint`, `vitest`
10/10 including a new `KnowledgeAdminPage` list/create test, `vite build`)
also pass. **Passed.**

## Phase 9 — Professional UX redesign [V2-1]

- [x] **T100 [V2-1]** Define the V2 design system (color/typography/spacing
  tokens, component states) and document it for reuse across both surfaces.
  Use [accamargo.org.br](https://accamargo.org.br)'s UX patterns (tone,
  information hierarchy, professionalism level) as a reference point per
  `spec.md` V2-1 — do not copy its branding, logo, color identity, or
  content; this is a synthetic demo product with no affiliation to that
  organization. Documented in `plan.md` §11.3, implemented as CSS custom
  properties in `frontend/src/styles.css`. Automated fetch of the
  reference site returned HTTP 403 during implementation (bot-blocked),
  so the tokens were not derived from its markup — see §11.3 for the
  pattern-level (not markup-level) reasoning that stands in for it.
- [x] **T101 [V2-1] [P]** Redesign the customer SPA (start, message list,
  send, status, token header, close) to the new design system, including
  empty/loading/error states. `CustomerPage` in `main.tsx`: `.card`
  shell, `StatusBadge`, an empty-state message when there are no
  messages yet, a loading state before the first conversation fetch
  resolves, and the reply textarea/button disabled once the
  conversation is `CLOSED`.
- [x] **T102 [V2-1] [P]** Redesign the operator SPA, retaining the three-pane
  functional layout (`[ waiting/active list ] [ conversation ] [ AI/evidence
  panel ]`) with the new design system and this feature's new controls
  (checkboxes, "desmarcar conversas", "Gerar rascunho"/"Buscar evidências",
  "Usar sugestão", typing indicator, knowledge-CRUD entry point).
  `OperatorPage`/`KnowledgeAdminPage` in `main.tsx`: `StatusBadge` on
  every queue item, empty-state text for an empty queue/message list,
  a "conversation encerrada" state that replaces the reply form, and
  card/list styling reused for the knowledge-CRUD screen (`main.tsx`,
  `styles.css`).
- [x] **T103 [V2-1]** Ensure all redesigned/new controls are keyboard-usable
  and semantically labeled. Every text input/textarea now has an
  `htmlFor`-linked `<label>` (previously several were unlabeled or
  relied on implicit wrapping); `:focus-visible` gets an explicit
  focus ring (`--focus-ring` token) on every interactive element;
  status is always conveyed by a `<span class="badge">` carrying its
  own visible text label, never by color alone.
- [x] **T104 [V2-1]** Ensure the UI never exposes a control the backend would
  reject for the current effective mode/feature flag — backend remains
  authoritative regardless of what the UI shows. Auditing this
  surfaced two real gaps, both fixed in `main.tsx`: (1) "Gerar
  rascunho"/"Assumir controle" were gated on `effective_mode === "N2"`
  only, but the backend (`ai/router.py` `draft()`, `select_evidence()`;
  `operator_workspace/router.py` `take_over()`) also requires
  `status === "ACTIVE"` — introduced `aiEligible = status === "ACTIVE"
  && effective_mode === "N2"` and used it for both controls plus the
  manual-search-evidence "Selecionar" action (`select_evidence` has the
  same N2+ACTIVE requirement, but manual search itself is legitimately
  available in N1-assistive mode as read-only, so the fix scopes
  `onSelect` to `aiEligible` without hiding the search results
  themselves); (2) the operator reply form/"Encerrar conversa" had no
  `status === "ACTIVE"` guard, but `send_operator_message` 409s on a
  non-active conversation — a closed conversation opened from the
  queue for historical review now shows "Esta conversa está encerrada."
  instead of a form that would fail on submit.
- [x] **T105 [V2-1]** Add frontend regression coverage for the redesigned
  flows appropriate to the existing test stack (component/unit level; E2E
  coverage is Phase 11). Four new Vitest cases in `main.test.tsx`: the
  customer empty-message state, the operator empty-queue state, the
  closed-conversation control-hiding behavior from T104's fix #2, and
  the N1-assistive-search omitting "Selecionar" from T104's fix #1.
  Additionally (not new coverage, but existing coverage the redesign's
  text changes broke): `e2e/v1.spec.ts`'s two V1 acceptance scenarios
  asserted on the raw status enum (`"WAITING"`, `/^ACTIVE/`) that the
  new `StatusBadge` no longer renders verbatim (it renders the
  translated label, e.g. "Aguardando"/"Em atendimento"). Updated the
  matchers to match and reran both scenarios (N2 and N1, the latter
  with `GLOBAL_MATURITY_MODE=N1`/`N1_ASSISTIVE_SEARCH_ENABLED=false`)
  against the rebuilt `frontend` Docker image with real Chrome via
  Playwright — both pass.

**Gate:** `ruff`/`mypy`/`pytest` unaffected (Phase 9 is frontend-only, no
backend files changed). Frontend `tsc --noEmit`, `eslint`, `vitest`
(14/14), `vite build` all pass. Manually verified in a real browser via
screenshots of `/customer`, `/operator` (empty and with an open
N2 conversation through to a generated draft), and `/operator/knowledge`.
Both `e2e/v1.spec.ts` Playwright acceptance scenarios (N2 and N1) pass
against the rebuilt frontend image. **Passed.**

## Phase 10 — Audit and observability

- [x] **T110** Add the new event types from `plan.md` §14 to
  `docs/architecture/EVENT_CATALOG.md`: `ai.draft_generated`'s new `trigger`
  payload field, `ai.dynamic_pattern_resolved`,
  `ai.dynamic_pattern_fallback`, the `knowledge.*` CRUD events, and
  `anonymous_access.token_validation_rate_limited`. All were already in
  the catalog from earlier phases except the `knowledge.*` CRUD events
  and `anonymous_access.token_validation_rate_limited`, both added now.
- [x] **T111** Verify every new event type is actually emitted by its
  corresponding flow (cross-check against Phases 2–8). Grepped every
  `record_event(...)` call site against the catalog. Found one real gap:
  **`anonymous_access.token_validation_rate_limited` was planned in
  `plan.md` §14 but never implemented** — `token_bound_conversation` in
  `anonymous_access/router.py` called `enforce_not_locked_out` but never
  recorded an audit event on the 429 it raises. Fixed: it now catches
  that `HTTPException` and records the event (with no payload — see
  T113) before re-raising, deliberately leaving `conversation_id` null
  rather than trusting the route's path parameter (which may not
  correspond to a real conversation and would violate that column's FK
  constraint). Added `tests/smoke_v2_token_rate_limit.py` to prove the
  event fires on lockout, that both a wrong and a since-correct token
  are rejected identically while locked out, and that neither the
  attempted token nor a fabricated `conversation_id` leaks into the
  audit row. All other `knowledge.*`, `ai.dynamic_pattern_*`, and
  `ai.draft_generated`'s `trigger` field were already correctly wired
  from Phases 2–8.
- [x] **T112** Document that `conversation.typing_heartbeat` is deliberately
  not audited (too frequent, no product-facing decision) as an explicit
  exception, not an oversight. Added as an explicit strikethrough entry
  in `EVENT_CATALOG.md` next to the other `conversation.*` events,
  rather than a silent absence.
- [x] **T113** Confirm no new audit payload or log line carries full message
  bodies, raw tokens, or dynamic-pattern diagnostic detail at a
  customer-reachable or INFO-log level. Reviewed every V2
  `record_event(...)` payload (all carry only IDs) and the app's only
  `logging.info` call site (`shared/http.py`: method/path/status/
  duration/request_id, unchanged by V2). No payload or log line carries
  a message body, a raw/hashed token, or the dynamic-pattern `cause`
  string outside the audit table itself (which is not customer-
  reachable and not INFO-logged).

**Gate:** `ruff`/`mypy`/`pytest` (21/21) pass. Full E2E smoke suite
(`smoke_core`, `smoke_n2`, `smoke_concurrent_capacity`, `smoke_resilience`,
`smoke_real_provider`, `smoke_v2_dynamic_pattern`, `smoke_v2_knowledge_crud`,
`smoke_v2_automatic_trigger`, and the new `smoke_v2_token_rate_limit`) all
pass against the rebuilt backend image. **Passed.**

## Phase 11 — Acceptance automation and DONE

- [x] **T120** Update `contracts/openapi.yaml` per `plan.md` §12 (all new,
  changed, and removed endpoints/schemas) as the canonical V2 contract.
  The pre-implementation draft (written before Phase 1) was verified
  against the real implementation rather than rewritten: every registered
  FastAPI route (`app.routes`, 24 `/api/v1/*` paths) matches the
  contract's paths+methods exactly; spot-checked the highest-risk
  schemas (`AIGeneration`/`generation_dict`, `QAEntry`/`qa_dict`,
  `ClinicalDocument`/`document_dict`, `ClinicalChunk`/`chunk_dict`,
  `QADynamicBinding`) field-by-field against their actual response-dict
  builders — no drift found. No changes were needed to this file itself.
- [x] **T121** Write `data-model.md` reflecting `plan.md` §3 in full. Same
  verification approach as T120. Found one real gap while checking §6's
  claim that `qa_dynamic_bindings.source_table` is "validated against the
  allowlist at write time (V2-8 CRUD) *and* at resolution time": only the
  resolution-time check (`knowledge/dynamic_binding.py`) existed —
  `knowledge/router.py`'s CRUD handlers never validated the binding at
  all before Phase 11. Not a security hole (the resolution-time check
  remains authoritative), but the write-time UX guarantee the doc
  promised was simply missing. Fixed: added `validate_binding()` to
  `knowledge/router.py`, called from `upsert_binding()`, reusing
  `dynamic_binding.py`'s `ALLOWLISTED_TABLES` to reject an unknown
  `source_table` or column with `422 INVALID_DYNAMIC_BINDING` at
  creation/update time. Covered by two new assertions in
  `smoke_v2_knowledge_crud.py`. `data-model.md` itself needed no text
  change — it already correctly described the intended design.
- [x] **T122** Write `acceptance.md` covering all 11 acceptance outcomes in
  `spec.md` §5 as executable scenarios. Already fully written
  pre-implementation (sections A–K); no scenario rewrite was needed.
  Executed against the running stack and recorded in its "Execution
  record" section (see below) once T124–T129 completed.
- [x] **T123** Write/update `checklists/security.md`,
  `checklists/requirements.md` (closing its two remaining open items), and
  `checklists/traceability.md` for V2. `requirements.md` was already
  fully closed (all items checked) from the pre-implementation cycle —
  no open items remained to close by the time Phase 11 started.
  `security.md`'s 12 items were still all unchecked; verified each
  against the actual implementation/tests and checked them off with an
  evidence reference (file/test name) per item — see the file itself for
  the per-item reasoning. `traceability.md`'s "Executable evidence" table
  (flagged as a known placeholder in `analysis.md` §4) is now filled in
  with real file paths for every non-E2E row, and the E2E rows point at
  `frontend/e2e/v2.spec.ts` once T124–T128 landed.
- [x] **T124** Implement an E2E scenario for the typing-debounced automatic
  trigger (correct batching across multiple bursts).
  `frontend/e2e/v2.spec.ts`: sends one message, resumes typing mid-window
  to prove no premature draft, goes idle 8s+ for the first automatic
  draft, then sends two more messages and goes idle again for a second
  automatic draft — passed against real Chrome.
- [x] **T125** Implement an E2E scenario proving "Buscar evidências" and
  "Gerar rascunho" are independent (selecting evidence in one does not leak
  into the other). `frontend/e2e/v2.spec.ts`: confirms the message
  checkbox state survives an evidence-selection generation untouched, and
  that "Gerar rascunho" still works correctly afterward — passed.
- [x] **T126** Implement an E2E scenario for the dynamic-pattern happy path
  and its fallback path. `frontend/e2e/v2.spec.ts`: seeds two real
  `content.knowledge_dynamic_fixture` rows via `psql` (no CRUD UI exists
  for this fixture table by design, `plan.md` §9.4), creates a matching
  and a non-matching Q&A dynamic binding through `KnowledgeAdminPage`,
  and proves the happy path renders both fixture rows verbatim while the
  fallback path yields `ABSTAIN` with no diagnostic cause leaking into
  the visible draft panel — passed. Two real test bugs found and fixed
  while debugging: (1) the test clicked the operator's queue-item button
  without first navigating from `/operator/knowledge` back to
  `/operator` — the element genuinely didn't exist on the page, so
  Playwright polled for it until the timeout, misleadingly looking like
  a product-side hang; (2) each QA creation and search makes a real
  OpenAI embedding call, which needed a bumped 120s test timeout once
  (1) was fixed and the test could actually reach that step.
- [x] **T127** Implement an E2E scenario: knowledge CRUD create → appears in
  retrieval/selection → used in a generation → deactivate → no longer
  retrievable. `frontend/e2e/v2.spec.ts` — passed, same two-bug class as
  T126 (missing post-knowledge-CRUD navigation back to `/operator`; a
  90s test timeout for the real-embedding/LLM latency of the
  subsequent evidence-selection generation).
- [x] **T128** Implement an E2E scenario for the token rate-limit lockout.
  `frontend/e2e/v2.spec.ts`: uses Playwright's `request` fixture (real
  HTTP through the same nginx→backend path the browser uses, not a
  UI-driven flow) — the customer UI has no manual-token-entry affordance
  to organically drive this from clicks, and its background polling
  timer silently swallows post-first-failure errors (`.catch(() =>
  undefined)`), so a click-driven version couldn't actually observe the
  lockout either. Loops failed-token requests until a `429 RATE_LIMITED`
  is observed (bounded at 60 attempts, well above the default 30) —
  passed in ~0.3s (much faster than expected, confirming this isn't
  driven through a real browser's network stack).
  **Operational finding, not a product defect:** the lockout this test
  deliberately triggers is IP-keyed with exponential backoff (`plan.md`
  §13.1) and persists in the backend's in-memory state until it expires
  naturally or the process restarts. Running T128 repeatedly against a
  long-lived `backend` container (as happened while iterating on this
  file) escalates `consecutive_lockouts` for the shared test-runner
  source IP and can poison *any other* E2E test relying on customer
  token validation from the same machine for minutes afterward — this
  is exactly what happened to a `v1.spec.ts` rerun immediately after a
  T128 run, and `docker compose restart backend` (clearing the
  in-memory limiter state) resolved it. Documented here so this doesn't
  get re-diagnosed as a regression next time: **restart the `backend`
  container between running T128 and any other test that depends on
  legitimate token validation from the same host.**
- [x] **T129** Run all backend/frontend/E2E/lint/type gates. See the
  Gate note below.
- [x] **T130** Run a Spec Kit `analyze`-equivalent cross-artifact and
  V1-to-V2 convergence review; repair any drift; write the results into
  V2 `analysis.md`. Added a Phase 11 convergence section to `analysis.md`
  documenting the two real gaps found and fixed this phase (T111's
  missing rate-limit audit event, T121's missing write-time binding
  validation) plus confirmation that no other artifact/implementation
  drift remains.
- [x] **T131** Update `PROJECT_STATE.md` to record V2 DONE only once every
  `spec.md` §5 acceptance outcome passes.

**Gate:** backend `ruff`/`mypy`/`pytest` (21/21); frontend
`eslint`/`tsc --noEmit`/`vitest` (14/14)/`vite build`; the full backend E2E
smoke suite (`smoke_core`, `smoke_n2`, `smoke_concurrent_capacity`,
`smoke_resilience`, `smoke_real_provider`, `smoke_v2_dynamic_pattern`,
`smoke_v2_knowledge_crud`, `smoke_v2_automatic_trigger`,
`smoke_v2_token_rate_limit`) against the rebuilt backend image; both
`v1.spec.ts` browser scenarios (N2 and N1) re-verified against the V2-1
redesign; all 5 new `v2.spec.ts` scenarios (T124-T128). `acceptance.md`'s
Execution record (2026-08-17) covers sections A-K. **Passed.**

## Dependency summary

```text
Phase 0
  -> migrations (Phase 1)
  -> token format/rate limiting (Phase 2)         [independent of 3-8]
  -> message-context selection (Phase 3)
      -> manual "Gerar rascunho" (Phase 4)
          -> typing/automatic trigger (Phase 6)
      -> "Buscar evidências" (Phase 5, T050-052/054-057 independent of Phase 7)
  -> dynamic-evidence correction (Phase 7)
      -> Phase 5's T053 (binding branch)
      -> knowledge CRUD (Phase 8, reuses Phase 7's binding model)
  -> UX redesign (Phase 9)                        [mostly independent, needs Phase 2-8 controls to style]
  -> audit/observability (Phase 10)
  -> acceptance automation and convergence (Phase 11)
```

Do not parallelize across an unresolved schema or API contract change.
