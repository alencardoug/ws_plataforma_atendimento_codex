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

- [ ] **T000** Read constitution, `spec.md`, `plan.md`, V1's `data-model.md`/
  `contracts/openapi.yaml`/`analysis.md`, root architecture/security/data/
  test/operations docs, and the current V1 implementation for every module
  this plan extends.
- [ ] **T001** Run cross-artifact review of `spec.md` vs `plan.md`; record
  findings/repairs in V2 `analysis.md` before implementation starts.
- [ ] **T002** Produce a V2 requirements-to-task/test traceability matrix
  (`checklists/traceability.md`) mapping every V2-1..V2-8 outcome and every
  `spec.md` §5 acceptance outcome to its implementing task(s).
- [ ] **T003** Confirm which V1 modules/functions this plan reuses rather
  than reimplements (`full_parent_draft`, `provider.generate`,
  `customer_care.knowledge.ingest`'s content-hash/re-embed logic, the
  existing operator polling cadence) and record the exact call sites in
  `plan.md` if not already precise enough to implement against.

**Gate:** no unresolved blocker/contradiction between `spec.md` and `plan.md`.

## Phase 1 — Migrations

- [ ] **T010** Add `conversations.last_customer_activity_at`,
  `last_customer_typing_at`, and `auto_draft_covers_through_message_id`
  (FK → `messages.id`, nullable) — `plan.md` §3.2.
- [ ] **T011** Create `customer_service.message_selections` (`ai_generation_id`
  FK, `message_id` FK, unique pair) — `plan.md` §3.2.
- [ ] **T012** Add `ai_generations.trigger` (enum `AUTOMATIC` /
  `MANUAL_DRAFT` / `MANUAL_EVIDENCE`), `manual_search_text` (nullable text),
  and `dynamic_pattern_used` (bool default false); relax
  `triggering_message_id` from `NOT NULL` to nullable (`MANUAL_EVIDENCE` has
  none) — `plan.md` §3.3/§3.4.
- [ ] **T013** Create `content.qa_dynamic_bindings` (`qa_id` FK unique,
  `source_table`, `filter` jsonb, `output_columns` jsonb, `row_limit` default
  4) — `plan.md` §3.4.
- [ ] **T014** Add forward-only Alembic revisions for T010–T013; verify
  against both an empty V1-migrated database and the current V1 acceptance
  database.
- [ ] **T015** Add migration tests proving the new columns/tables apply
  cleanly and existing V1 rows are unaffected (no backfill requirement, all
  new columns nullable/defaulted).

**Gate:** clean V1 database migrates to V2 schema without data loss.

## Phase 2 — Token format and rate limiting [V2-2]

- [ ] **T020 [V2-2]** Replace the token generator with the 8-character,
  31-symbol alphabet in `plan.md` §3.1 (excludes `0/O`, `1/I`, `L`); keep the
  constant in one place.
- [ ] **T021 [V2-2]** Confirm `/public/conversations` creation and the
  existing HMAC-digest storage/comparison path work unchanged against the
  new format (digest algorithm/column untouched, only input format changes).
- [ ] **T022 [V2-2]** Implement an IP-keyed sliding-window rate limiter for
  token validation failures on `/public/*` (429 beyond threshold, escalating
  backoff/lockout); make thresholds configurable settings, not hardcoded.
- [ ] **T023 [V2-2]** Wire the limiter into the existing customer-token
  authorization dependency; ensure successful validations do not count
  against the limiter.
- [ ] **T024 [V2-2]** Add rate-limit configuration to typed settings and
  `.env.example`.
- [ ] **T025 [V2-2]** Add negative tests: lockout engages at the configured
  threshold, resets on schedule, and does not block a legitimate customer
  using the correct token.
- [ ] **T026 [V2-2]** Add a regression test confirming the raw token is still
  never persisted, logged, or placed in a URL despite the format change.
- [ ] **T027 [V2-2] [P]** Customer SPA: render the token continuously in the
  conversation header (no reveal/hide toggle) with a copy action; confirm no
  new lookup/recovery affordance is added.

## Phase 3 — Operator-selected conversation context [V2-4]

- [ ] **T030 [V2-4]** Change `GenerateDraftRequest` to
  `selected_message_ids: UUID[]` (may be empty) + `manual_search_text: str`
  (may be empty); update the endpoint/service signature accordingly.
- [ ] **T031 [V2-4]** Validate every submitted message ID belongs to the
  target conversation; reject (`422`) when both inputs are empty.
- [ ] **T032 [V2-4]** Persist `message_selections` rows for every generation,
  regardless of trigger (Phase 4/6 depend on this).
- [ ] **T033 [V2-4] [P]** Operator UI: checkbox on every message in the
  conversation view.
- [ ] **T034 [V2-4] [P]** Operator UI: default selection = the contiguous
  trailing run of `CUSTOMER` messages after the last `OPERATOR` message,
  computed client-side from data already in the message list.
- [ ] **T035 [V2-4] [P]** Operator UI: "desmarcar conversas" clears all
  message checkboxes (pure client-side action, no endpoint).
- [ ] **T036 [V2-4]** Add tests: default-selection correctness across
  multi-burst conversations, clear-all behavior, both-empty rejection, and a
  cross-conversation message-ID rejection (authorization negative test).

## Phase 4 — "Gerar rascunho" manual trigger [V2-7 manual]

- [ ] **T040 [V2-7]** Update the draft-generation application service to
  build its query/context from `selected_message_ids` (joined message
  bodies, ordered by `created_at`) concatenated with `manual_search_text`
  when both are present, replacing V1's single `triggering_message_id`.
- [ ] **T041 [V2-7]** Persist `trigger = MANUAL_DRAFT` on the resulting
  generation.
- [ ] **T042 [V2-7]** Remove `POST /operator/drafts/{generation_id}/regenerate`
  (service, route, and OpenAPI entry) — re-invoking the drafts endpoint
  against the current selection now serves this purpose.
- [ ] **T043 [V2-7] [P]** Operator UI: wire "Gerar rascunho" to the new
  request shape; remove the "Regenerar" control entirely.
- [ ] **T044 [V2-7]** Add a test: changing the message/evidence selection and
  re-invoking "Gerar rascunho" produces a fresh generation with correct
  `prior_generation_id` lineage and `trigger = MANUAL_DRAFT`.
- [ ] **T045 [V2-7]** Add a test confirming the `/regenerate` route no longer
  exists in the routing table or the OpenAPI contract.

## Phase 5 — "Buscar evidências" [V2-3]

Depends on Phase 3 (independence from `message_selections` must be provable)
and, for the dynamic-binding branch, on Phase 7 (may land as a follow-up
task once Phase 7 exists — see T053).

- [ ] **T050 [V2-3]** Implement `POST
  /operator/knowledge/evidence/{retrieval_hit_id}/select`: given a hit from a
  prior `/operator/knowledge/search` call, execute the deterministic
  selection outcome server-side.
- [ ] **T051 [V2-3]** Clinical branch: reuse `full_parent_draft` as a plain
  function call (no LLM); persist `trigger = MANUAL_EVIDENCE`,
  `provider = clinical-parent-document`.
- [ ] **T052 [V2-3]** Administrative Q&A branch without a dynamic binding:
  reuse the existing `provider.generate` path scoped to this single hit.
- [ ] **T053 [V2-3]** Administrative Q&A branch with a dynamic binding: defer
  to the Phase 7 resolver (`knowledge/dynamic_binding.py`); implement once
  Phase 7 lands.
- [ ] **T054 [V2-3]** Add a test proving this endpoint never reads or writes
  `message_selections` — full independence from V2-4's context selection.
- [ ] **T055 [V2-3] [P]** Operator UI: "Buscar evidências" button plus a
  results list where selecting exactly one item triggers the outcome (no
  multi-select control exists in the UI at all).
- [ ] **T056 [V2-3]** Add a test confirming the endpoint's request shape
  structurally accepts only one `retrieval_hit_id`, not a list.
- [ ] **T057 [V2-3]** Add a test confirming the clinical branch has no
  LLM-composed-short-reply alternative anywhere in V2.

## Phase 6 — Typing heartbeat and automatic debounce trigger [V2-7 automatic]

Depends on Phase 3 (`message_selections`) and Phase 4 (shared generation
path).

- [ ] **T060 [V2-7]** Implement `POST /public/conversations/{id}/typing`:
  updates `last_customer_typing_at` and `last_customer_activity_at`.
  Rate-limited like other public endpoints (Phase 2) but with a higher
  allowance for its expected frequency.
- [ ] **T061 [V2-7]** Confirm customer-message send already updates
  `last_customer_activity_at` (via insert timestamp; no extra write needed) —
  add a test if not already implicit.
- [ ] **T062 [V2-7]** Implement the lazy trigger-check: on the existing
  operator conversation-detail poll and on the typing heartbeat, evaluate
  whether `now - last_customer_activity_at >= 8s` AND a customer message
  newer than `auto_draft_covers_through_message_id` exists AND the
  conversation is active effective-N2.
- [ ] **T063 [V2-7]** On a positive check, run the same generation path as
  Phase 4 with `selected_message_ids` set to the consecutive customer-message
  run (Phase 3's default-selection logic, reused server-side here), persist
  `trigger = AUTOMATIC`, and advance `auto_draft_covers_through_message_id`.
- [ ] **T064 [V2-7]** Add `is_customer_typing` (derived: `now -
  last_customer_typing_at <` a short grace window) to
  `OperatorConversationDetail`.
- [ ] **T065 [V2-7] [P]** Operator UI: live "cliente está digitando…"
  indicator; "Usar sugestão" action to accept/send the current automatic
  draft.
- [ ] **T066 [V2-7]** Add tests: the trigger fires exactly once per activity
  run (not once per poll), accumulates the correct message set across
  multiple typing bursts (matching `spec.md`'s 4-then-6-message example),
  and does not fire while typing activity is recent.
- [ ] **T067 [V2-7]** Add a test confirming no token-by-token streaming
  occurs anywhere in the response (draft returned whole).
- [ ] **T068 [V2-7]** Add a load-shape test/note confirming the lazy check
  adds negligible cost to the existing poll (per `plan.md` §16).

## Phase 7 — Dynamic-evidence safety correction [V2-6]

Depends on Phase 1 (`qa_dynamic_bindings` table).

- [ ] **T070 [V2-6]** Implement the `qa_dynamic_bindings` model/repository.
- [ ] **T071 [V2-6]** Implement the server-side table allowlist (Python
  mapping of table name → SQLAlchemy model); never accept a table/column
  identifier from anywhere else.
- [ ] **T072 [V2-6]** Implement `knowledge/dynamic_binding.py`: resolve a
  `qa_id`'s binding into a parameterized, filtered, `LIMIT`-bounded query
  against the allowlisted model.
- [ ] **T073 [V2-6]** Implement pattern substitution: single-row and
  multi-row rendering per `output_columns`; pin the exact multi-row template
  join syntax here (not left implicit).
- [ ] **T074 [V2-6]** Wire the resolver into both generation paths that can
  reach a Q&A entry with a binding: Phase 5's T053 (manual evidence
  selection) and Phase 4/6's RAG+LLM path when the selected/top evidence has
  a binding — resolver output takes priority over LLM composition in both.
- [ ] **T075 [V2-6]** Implement the unified fallback: no binding configured,
  allowlist miss, table/column mismatch, query error, or zero matching rows
  all produce `status = ABSTAIN`, `abstention_reason =
  DYNAMIC_DATA_UNAVAILABLE`, `dynamic_pattern_used = false`, an audit-only
  detailed cause, and a generic customer-safe fallback message.
- [ ] **T076 [V2-6]** Add tests: successful single-row and multi-row
  resolution against a seeded structured table.
- [ ] **T077 [V2-6]** Add tests for each failure mode individually (missing
  binding, allowlist miss, missing table/column, query error, empty result).
- [ ] **T078 [V2-6]** Add a negative test proving the audit-only cause string
  never appears in `draft_text` or any customer-facing field/response.
- [ ] **T079 [V2-6]** Add the regression test that closes the original V1
  finding: a `dynamic_data_required=true` entry with no binding behaves
  identically to a configured-but-failed one (never literal passthrough).

## Phase 8 — Knowledge-base CRUD [V2-8]

Depends on Phase 1 (`qa_dynamic_bindings`) and reuses Phase 7's binding
model.

- [ ] **T080 [V2-8]** Implement Q&A CRUD service (create/read/update/
  deactivate) including nested create/update of its `qa_dynamic_bindings`
  row.
- [ ] **T081 [V2-8]** Implement clinical parent-document CRUD service.
- [ ] **T082 [V2-8]** Implement clinical child-chunk CRUD service, nested
  under its parent.
- [ ] **T083 [V2-8]** Implement the endpoints in `plan.md` §10 under
  `/operator/knowledge/qa` and `/operator/knowledge/clinical-documents`
  (+ nested `/chunks`), `operatorBearer`-secured, no new role.
- [ ] **T084 [V2-8]** Wire create/update to `customer_care.knowledge.ingest`'s
  existing content-hash/re-embed logic by calling it, not reimplementing it.
- [ ] **T085 [V2-8]** Implement "delete" as `is_active = false` (soft
  delete), consistent with the existing column on all three content tables.
- [ ] **T086 [V2-8]** Emit an audit event for every CRUD mutation
  (`knowledge.qa_created/updated/deactivated`,
  `knowledge.clinical_document_created/updated/deactivated`,
  `knowledge.clinical_chunk_created/updated/deactivated`).
- [ ] **T087 [V2-8] [P]** Operator UI: knowledge CRUD screen (Q&A + clinical
  parent/child), reachable from operator navigation, separate from the
  conversation workspace.
- [ ] **T088 [V2-8] [P]** Operator UI: dynamic-binding editor (table, filter,
  output-column mapping) embedded in the Q&A entry form.
- [ ] **T089 [V2-8]** Add authorization tests (existing operator credentials
  work; no anonymous/customer-token path reaches these endpoints).
- [ ] **T090 [V2-8]** Add tests: re-embed triggers only when content hash
  actually changes (idempotency preserved), and soft-deleted records stop
  appearing in retrieval/search without breaking existing FK references from
  historical `ai_generation_sources`/`message_citations`.

## Phase 9 — Professional UX redesign [V2-1]

- [ ] **T100 [V2-1]** Define the V2 design system (color/typography/spacing
  tokens, component states) and document it for reuse across both surfaces.
  Use [accamargo.org.br](https://accamargo.org.br)'s UX patterns (tone,
  information hierarchy, professionalism level) as a reference point per
  `spec.md` V2-1 — do not copy its branding, logo, color identity, or
  content; this is a synthetic demo product with no affiliation to that
  organization.
- [ ] **T101 [V2-1] [P]** Redesign the customer SPA (start, message list,
  send, status, token header, close) to the new design system, including
  empty/loading/error states.
- [ ] **T102 [V2-1] [P]** Redesign the operator SPA, retaining the three-pane
  functional layout (`[ waiting/active list ] [ conversation ] [ AI/evidence
  panel ]`) with the new design system and this feature's new controls
  (checkboxes, "desmarcar conversas", "Gerar rascunho"/"Buscar evidências",
  "Usar sugestão", typing indicator, knowledge-CRUD entry point).
- [ ] **T103 [V2-1]** Ensure all redesigned/new controls are keyboard-usable
  and semantically labeled.
- [ ] **T104 [V2-1]** Ensure the UI never exposes a control the backend would
  reject for the current effective mode/feature flag — backend remains
  authoritative regardless of what the UI shows.
- [ ] **T105 [V2-1]** Add frontend regression coverage for the redesigned
  flows appropriate to the existing test stack (component/unit level; E2E
  coverage is Phase 11).

## Phase 10 — Audit and observability

- [ ] **T110** Add the new event types from `plan.md` §14 to
  `docs/architecture/EVENT_CATALOG.md`: `ai.draft_generated`'s new `trigger`
  payload field, `ai.dynamic_pattern_resolved`,
  `ai.dynamic_pattern_fallback`, the `knowledge.*` CRUD events, and
  `anonymous_access.token_validation_rate_limited`.
- [ ] **T111** Verify every new event type is actually emitted by its
  corresponding flow (cross-check against Phases 2–8).
- [ ] **T112** Document that `conversation.typing_heartbeat` is deliberately
  not audited (too frequent, no product-facing decision) as an explicit
  exception, not an oversight.
- [ ] **T113** Confirm no new audit payload or log line carries full message
  bodies, raw tokens, or dynamic-pattern diagnostic detail at a
  customer-reachable or INFO-log level.

## Phase 11 — Acceptance automation and DONE

- [ ] **T120** Update `contracts/openapi.yaml` per `plan.md` §12 (all new,
  changed, and removed endpoints/schemas) as the canonical V2 contract.
- [ ] **T121** Write `data-model.md` reflecting `plan.md` §3 in full.
- [ ] **T122** Write `acceptance.md` covering all 11 acceptance outcomes in
  `spec.md` §5 as executable scenarios.
- [ ] **T123** Write/update `checklists/security.md`,
  `checklists/requirements.md` (closing its two remaining open items), and
  `checklists/traceability.md` for V2.
- [ ] **T124** Implement an E2E scenario for the typing-debounced automatic
  trigger (correct batching across multiple bursts).
- [ ] **T125** Implement an E2E scenario proving "Buscar evidências" and
  "Gerar rascunho" are independent (selecting evidence in one does not leak
  into the other).
- [ ] **T126** Implement an E2E scenario for the dynamic-pattern happy path
  and its fallback path.
- [ ] **T127** Implement an E2E scenario: knowledge CRUD create → appears in
  retrieval/selection → used in a generation → deactivate → no longer
  retrievable.
- [ ] **T128** Implement an E2E scenario for the token rate-limit lockout.
- [ ] **T129** Run all backend/frontend/E2E/lint/type gates.
- [ ] **T130** Run a Spec Kit `analyze`-equivalent cross-artifact and
  V1-to-V2 convergence review; repair any drift; write the results into
  V2 `analysis.md`.
- [ ] **T131** Update `PROJECT_STATE.md` to record V2 DONE only once every
  `spec.md` §5 acceptance outcome passes.

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
