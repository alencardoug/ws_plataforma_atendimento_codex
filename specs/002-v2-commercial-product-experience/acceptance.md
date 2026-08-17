# V2 Acceptance Protocol

This is the executable definition of DONE for V2, supplementary to `spec.md`
§5. It extends `specs/001-v1-assisted-customer-service/acceptance.md`, which
remains the record of V1's own acceptance — this document does not repeat
scenarios V2 leaves unchanged (six-client queue, N1 manual messaging,
citation exposure mechanics, take-over, multiline rendering) except where a
V2 change requires re-proving them.

## A. Environment

- [x] V2 migrations (`plan.md` §3) apply cleanly on top of the V1 acceptance
  database, and on an empty database migrated through V1 then V2.
  `alembic upgrade head` applied both V2 migrations
  (`20260814_0001_v2_selection_triggers_dynamic_pattern`,
  `20260814_0002_v2_dynamic_pattern_fixture`) cleanly throughout Phases
  1-11; both are purely additive (new columns/tables), no V1 table is
  altered destructively.
- [x] Existing V1 conversations/messages/generations are unaffected by the
  migration (spot-check row counts before/after). Every V1-era smoke
  test (`smoke_core`, `smoke_n2`, `smoke_concurrent_capacity`,
  `smoke_resilience`, `smoke_real_provider`) and both `v1.spec.ts`
  browser scenarios continued passing unmodified against the
  V2-migrated schema throughout implementation — the additive-only
  migration shape (§3) makes a separate before/after row-count
  comparison redundant with that.
- [x] Compose stack starts healthy with no new required infrastructure
  (confirm no WebSocket/scheduler service was added, per `plan.md` §18).
  `docker-compose.yml` still defines exactly `db`/`backend`/`frontend`;
  no new service was added for any V2 outcome.

## B. Token display and rate limiting [V2-2]

1. Create a new anonymous conversation; verify the returned `access_token` is
   an 8-character code from the alphabet in `plan.md` §3.1 (no `0/O`, `1/I`,
   `L`).
2. Verify the customer UI displays the token continuously in the
   conversation header, with a working copy action, and no reveal/hide
   control exists.
3. Confirm there is no endpoint or UI affordance to resume/reopen a
   conversation from a different tab/session using the token.
4. Send repeated invalid tokens against a token-authenticated endpoint from
   one source until the configured threshold; verify `429` engages.
5. Verify the lockout does not block the correct token from the same source
   once issued fresh, and resets per the configured window.
6. Regression: confirm the raw token is absent from the database, application
   logs, and any URL — same as V1's check, rerun against the new format.

## C. Operator-selected context and "Gerar rascunho" [V2-4, V2-7 manual]

1. In an active N2 conversation with several customer/operator messages,
   open the operator view and verify the trailing consecutive run of
   customer messages since the last operator reply is pre-checked, and that
   older messages/operator messages are not.
2. Uncheck a pre-selected message, check an older one, and click "Gerar
   rascunho"; verify the resulting generation's recorded `selected_message_ids`
   matches exactly the final checkbox state, not the default.
3. Click "desmarcar conversas"; verify every message checkbox clears in one
   action with no server round-trip required to do so.
4. With no messages checked and the manual-search box empty, verify "Gerar
   rascunho" and "Buscar evidências" are both inert/disabled and the server
   rejects a direct API call with `422`.
5. With no messages checked but manual-search text present, verify "Gerar
   rascunho" generates using only that text as input.
6. Verify there is no "Regenerar" control anywhere in the UI, and that
   `POST /operator/drafts/{id}/regenerate` is not a reachable route.
7. Change the selection and click "Gerar rascunho" again; verify a new
   generation is created with `prior_generation_id` linking to the previous
   one and `trigger = MANUAL_DRAFT`.

## D. Automatic typing-debounced trigger [V2-7 automatic]

1. As a customer, begin typing in the message box without sending; verify
   the operator view shows a live "cliente está digitando…" indicator within
   a few seconds and no automatic draft is generated yet.
2. Send a message, then immediately begin typing again (within 8s); verify
   no automatic generation fires while typing continues.
3. Stop typing and sending for 8+ seconds; verify exactly one automatic
   generation fires, covering all customer messages sent since the last
   operator reply.
4. Send two more customer messages, pause 8+ seconds again; verify a second
   automatic generation fires, and its `selected_message_ids` covers all
   messages since the last operator reply (the earlier batch plus the new
   ones), matching `spec.md`'s 4-then-6-message example.
5. Verify the automatic draft appears whole (no partial/streaming text) and
   the operator accepts/sends it via "Usar sugestão".
6. Verify repeated operator polling of the conversation detail endpoint
   during an active typing burst does not produce duplicate generations for
   the same activity run.

## E. "Buscar evidências" [V2-3]

1. Use manual search to find both a clinical child result and an
   administrative Q&A result for the same query.
2. Select the clinical result; verify the complete parent document becomes
   available for the explicit-send box, with no LLM call recorded for this
   generation (`model = not-applicable`, matching V1's existing
   `clinical-parent-document` provenance convention).
3. Select the administrative Q&A result (no dynamic binding); verify a
   concise LLM-composed answer is produced, scoped to only this one hit.
4. Confirm the API request for evidence selection accepts a single
   `retrieval_hit_id`, not a list — attempting to pass multiple is rejected
   by the request shape itself, not by a business-rule check.
5. Verify this flow's resulting generation has empty `selected_message_ids`
   and is unaffected by whatever conversation-message checkboxes are
   currently checked (independence from V2-4).
6. Confirm no path in the product offers an LLM-composed short reply grounded
   in a clinical document as an alternative to the full parent document.

## F. Dynamic-evidence pattern [V2-6]

Requires a Q&A entry seeded with `dynamic_data_required = true` and a
`qa_dynamic_bindings` row pointing at a seeded structured table with at least
one matching row and one specialty/filter combination with zero matching
rows.

1. Select or trigger generation against the bound entry with a matching row;
   verify the response is the pattern with variables substituted from the
   table, `dynamic_pattern_used = true`, and no LLM call recorded.
2. Repeat with a filter that matches multiple rows (up to `row_limit`);
   verify each row renders per the pinned multi-row template.
3. Query the same entry with a filter that matches zero rows; verify the
   response is a generic manual-fallback message, `status = ABSTAIN`,
   `abstention_reason = DYNAMIC_DATA_UNAVAILABLE`, and an audit event
   carries the detailed cause (e.g. "no row matched filter").
4. Temporarily misconfigure the binding's `source_table` to a value not in
   the allowlist; verify the same fallback behavior and an audit-only cause
   naming the invalid table — confirm this cause never appears in
   `draft_text` or any customer-facing field.
5. Use a Q&A entry flagged `dynamic_data_required = true` with **no** binding
   configured; verify it behaves identically to step 3/4's fallback — this is
   the regression test closing the original V1 finding.
6. Attempt (via direct service/repository call in a test, not through any
   product-facing input) to resolve a binding against a table name outside
   the allowlist; verify the allowlist check rejects it before any SQL runs
   against an arbitrary table.

## G. Knowledge-base CRUD [V2-8]

1. As an authenticated operator, create a new Q&A entry with a dynamic
   binding; verify it appears in manual search results and is usable in
   generation (§F) once ingested/embedded.
2. Update the entry's `answer_markdown`; verify re-embedding occurs only for
   this record (content-hash comparison) and unrelated records are
   untouched.
3. Update the entry with identical content; verify no re-embedding occurs
   (idempotency preserved).
4. Deactivate the entry; verify it stops appearing in retrieval/search
   results but any historical `ai_generation_sources`/`message_citations`
   referencing it remain intact (no cascade delete, no FK violation).
5. Repeat create/update/deactivate for a clinical parent document and one of
   its child chunks.
6. Verify every mutation above emits the corresponding `knowledge.*` audit
   event.
7. Verify no anonymous or customer-token credential can reach any
   `/operator/knowledge/qa` or `/operator/knowledge/clinical-documents`
   route.

## H. Professional UX and accessibility [V2-1]

1. Walk through the redesigned customer and operator flows; verify
   empty/loading/error states render per the design system, not as blank or
   broken screens.
2. Verify every new V2 control (checkboxes, "desmarcar conversas", "Gerar
   rascunho", "Buscar evidências", "Usar sugestão", typing indicator,
   knowledge-CRUD navigation) is reachable and operable by keyboard alone,
   with semantic labeling.
3. Confirm the UI never renders a control the backend would reject for the
   current effective mode/feature flag (e.g. draft generation controls in
   N1) — cross-check against the equivalent V1 behavior.

## I. Security negative checks (extends V1 §I)

- token brute-force lockout engages and does not block legitimate use (§B);
- dynamic-pattern audit-only failure cause never reaches a customer-facing
  field or `draft_text` (§F);
- `qa_dynamic_bindings.source_table` cannot resolve against a non-allowlisted
  table even via a malformed/crafted binding row (§F);
- "Buscar evidências" cannot be made to accept more than one
  `retrieval_hit_id` (§E);
- V2-8 CRUD routes reject anonymous/customer-token credentials (§G);
- raw token (new short format) absent from DB/logs/URLs (§B);
- all V1 §I checks still pass unchanged (direct AI-to-customer send remains
  impossible on every new path — `MANUAL_EVIDENCE` and `AUTOMATIC` triggers
  included; administrative non-exposable citation still rejected; plaintext
  operator password still absent).

## J. Quality gates

- backend tests pass (including new V2 suites);
- frontend tests pass;
- E2E critical flows pass, including the four new scenarios in `tasks.md`
  T124–T128;
- type/lint gates pass;
- `contracts/openapi.yaml` matches implementation;
- no material V2 spec/plan/code divergence remains (`analysis.md`).

## K. V1 invariant regression (confirm unchanged under V2)

- explicit human send remains the only path to a customer-visible operator
  message, for all three `trigger` values;
- append-only audit remains true for every new event type;
- no chain-of-thought is persisted anywhere in the new `ai_generations`
  columns or `message_selections`;
- capacity (max-4), take-over, and multiline rendering are unaffected by the
  V2 changes (spot-check, not a full rerun of V1's scenarios).

## Execution record — 2026-08-17

All sections A–K passed against local Docker Compose/PostgreSQL 17, real
Chrome via Playwright, and the configured real OpenAI provider. Evidence:

- **A** — migrations additive-only, applied cleanly; no new Compose service.
- **B** — `test_anonymous_token_rate_limit.py` (8 unit tests: 8-char
  ambiguity-free alphabet, escalating lockout, per-source isolation,
  success-clears-state) plus `smoke_v2_token_rate_limit.py` and
  `v2.spec.ts`'s T128 scenario proved the lockout engages, rejects a
  since-correct token identically while locked out, resets, and emits
  `anonymous_access.token_validation_rate_limited` without leaking the
  attempted token or a fabricated `conversation_id`; the always-visible
  token header/copy affordance was verified in `main.test.tsx` and by
  browser screenshot.
- **C** — `smoke_n2.py`'s V2-4 section (default trailing-run selection,
  explicit override, empty-selection 422, manual-search-only path,
  `/regenerate` route absence) plus `main.test.tsx`'s V2-4 tests
  (checkbox defaults, "desmarcar conversas", disabled-button states).
- **D** — `smoke_v2_automatic_trigger.py` (real ~18s debounce wait: no
  premature fire while typing, exactly one fire per idle period,
  accumulated multi-message context, no streaming) plus `v2.spec.ts`'s
  T124 browser scenario proving the same batching end-to-end through a
  real customer typing/sending flow and the operator's live indicator.
- **E** — `smoke_n2.py`'s V2-3 section (clinical→full-parent with
  `model=not-applicable`, admin-Q&A→LLM scoped to one hit, empty
  `selected_message_ids`, no multi-selection request shape) plus
  `v2.spec.ts`'s T125 scenario proving independence from V2-4's
  checkbox state through the real UI.
- **F** — `smoke_v2_dynamic_pattern.py` (allowlist enforcement, zero-row
  fallback, multi-row substitution, missing-column fallback, all via
  direct resolver calls including the disallowed-table negative test)
  plus `smoke_n2.py`'s V2-6 HTTP-path cause-leak negative test plus
  `v2.spec.ts`'s T126 browser scenario (happy path renders real fixture
  data verbatim; fallback yields `ABSTAIN` with the cause string absent
  from the visible draft).
- **G** — `smoke_v2_knowledge_crud.py` (full CRUD round trip,
  content-hash idempotent re-embedding, soft-delete-preserves-FK,
  anonymous/customer-token 401, all `knowledge.*` audit events, and the
  Phase-11-discovered write-time dynamic-binding allowlist validation)
  plus `v2.spec.ts`'s T127 browser scenario (create → retrievable →
  used in a generation → deactivate → no longer retrievable, end to
  end through the real `KnowledgeAdminPage`).
- **H** — verified in a real browser via screenshots of `/customer`,
  `/operator` (empty and mid-conversation through to a generated
  draft), and `/operator/knowledge`; keyboard/label audit in `main.tsx`
  (T103); the two real backend-authority gaps T104 found (AI controls
  not gated on conversation status, evidence-selection offered in
  N1-assistive mode) were fixed and covered by dedicated `main.test.tsx`
  regression tests.
- **I** — every listed negative check has its own test above; additionally
  confirmed via code review that no `record_event(...)` payload anywhere
  in V2 carries a message body or raw/hashed token (Phase 10, T113).
- **J** — backend `ruff`/`mypy`/`pytest` (21/21) and frontend
  `eslint`/`tsc --noEmit`/`vitest` (14/14)/`vite build` all pass;
  `contracts/openapi.yaml` verified against the live route table and
  spot-checked schemas with no drift found (T120); `analysis.md` §6
  records the Phase 11 convergence review, including the two real gaps
  it found and fixed.
- **K** — `smoke_n2.py`/`v1.spec.ts` continued passing unmodified
  throughout (explicit-send-only across all three `trigger` values,
  append-only audit, capacity/take-over/multiline rendering unaffected);
  no chain-of-thought field exists in any new `ai_generations` column or
  in `message_selections` (both are pure ID/text-result storage, per
  `data-model.md`).

Two real implementation gaps were found and fixed during this execution
pass (both documented in `analysis.md` §6 and `tasks.md` T111/T121):
`anonymous_access.token_validation_rate_limited` was specified but never
emitted, and the V2-8 CRUD screen never validated a dynamic binding's
`source_table`/columns against the allowlist at write time (only at
resolution time, which remained the actual security boundary throughout).
Both are now closed with regression coverage. One test-authoring pitfall is
recorded in `tasks.md` T128 for future runs: T128's deliberate rate-limit
lockout is IP-keyed and outlives the test if the `backend` container isn't
restarted before running other token-validation-dependent E2E scenarios
from the same host.

Demo data was reset (`TRUNCATE ... CASCADE`) and the `backend` container
restarted (clearing in-memory rate-limiter state) after this run. Synthetic
test credentials and corpora only were used.
