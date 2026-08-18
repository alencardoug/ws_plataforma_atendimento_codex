# V3 Acceptance Protocol

This is the executable definition of DONE for V3, supplementary to `spec.md`
§5. It extends `specs/002-v2-commercial-product-experience/acceptance.md`
(which itself extends V1's), and does not repeat scenarios V3 leaves
unchanged except where a V3 change requires re-proving them.

## A. Environment

- [x] V3 migration (`20260818_0001_v3_categories_taxonomy_evaluation_satisfaction`)
  applies cleanly on top of the V1+V2 acceptance database, purely additive
  (new `content.categories`/`content.evaluation_cases`/
  `customer_service.conversation_satisfaction_responses` tables, six new
  `ai_generations` columns, two new FKs on existing category-shaped
  columns) — forward-only, `downgrade()` raises by design.
- [x] Existing V1/V2 conversations/messages/generations are unaffected —
  confirmed throughout implementation by every pre-existing smoke script
  and `v1.spec.ts`/`v2.spec.ts` continuing to pass unmodified against the
  V3-migrated schema (§G below).
- [x] Compose stack still starts healthy with no new required
  infrastructure — `docker-compose.yml` still defines exactly
  `db`/`backend`/`frontend`; no new service was added for any V3 outcome.

## B. Eight-tag taxonomy, observable and unambiguous [V3-1, outcome 1]

1. Send a draft unmodified (quick-approve, §C): the generation is tagged
   `approve`.
2. Send a draft with edited text: tagged `edit`, derived solely from
   `sent_text != draft_text` — no magnitude, no operator-chosen category.
3. Use "Buscar evidências" → select a hit: tagged `search`
   (`trigger = MANUAL_EVIDENCE`).
4. Take over a conversation: every generation on it is tagged `take-over`.
5. Regenerate (with or without instruction text): tagged `regenerate` or
   `regenerate-with-instruction` from `prior_generation_id`/`instruction_text`
   alone.
6. Mark any generation in history — not only the latest — incorrect: tagged
   `mark-incorrect`; repeating is idempotent (updates the timestamp, does
   not reject or duplicate).
7. Escalate a generation: tagged `escalate`, verified tag-only — no queue or
   routing table exists for it to write to.
8. All eight tags are computed by one function, `classify_generation()`,
   from existing durable facts only (audit events, `trigger`,
   `taken_over_at`, `prior_generation_id`/`instruction_text`, the two new
   retroactive columns) — no new parallel classification record.

## C. Quick-approve [V3-2, outcome 2]

1. Generate a draft with `status = ANSWER`; click "Aprovar"; verify the
   sent message body is byte-for-byte identical to `draft_text`.
2. Verify the resulting generation is tagged `approve` via the same
   `ai.draft_accepted` event every other unmodified send already produces —
   no dedicated accept endpoint exists.
3. Negative test: confirm no route in the OpenAPI schema matches
   `accept`/`quick-approve`; the only path to this tag is an authenticated
   operator's explicit `POST .../messages` — same authorization boundary as
   every other send, per V1/V2's explicit-send invariant (§K).

## D. Human Correction Rate [V3-3, outcome 3]

1. `docs/metrics/v3_queries.sql` query 2 computes HCR
   (`edit / (edit + approve)`) purely from `audit_events`/`ai_generations`
   rows, overall and by `category_slug` (including an explicit
   "sem categoria" row — never a silent drop).
2. `smoke_v3_metrics_agreement.py` and `smoke_v3_taxonomy_hcr.py` each
   independently tally approve/edit counts via `classify_generation()` in
   Python and compare to this same SQL query's own aggregation over the
   same rows — confirmed exact agreement.

## E. Read-only metrics surface [V3-4, outcome 4]

1. `docs/metrics/v3_queries.sql` is a static file; zero API route is wired
   to it anywhere in the backend — nothing to disable, by construction, not
   by an access-control check that could be bypassed.
2. The same four queries (abstention rate, HCR, volume by trigger/category,
   V3-12 satisfaction) also surface V3-12's results — confirmed by query 4.

## F. Evaluation cases [V3-5, outcome 5]

1. Create an evaluation case via `/operator/evaluation/cases`; verify
   `content.evaluation_cases` has no FK path to/from `conversations` or
   `ai_generations` — structural isolation, not a runtime filter that could
   be forgotten in a future query.
2. Confirm no evaluation-case write ever creates a `messages` row (no
   customer-visible artifact).
3. Confirm no automated re-run mechanism exists — only a reviewer's manual
   `evaluation.case_reviewed` update.
4. `test_evaluation_isolation.py` covers all three points against a live
   database.

## G. Regenerate-with-instruction [V3-6, outcome 6]

1. Fill "Instrução para regenerar" and click "Gerar rascunho": the
   resulting generation is `trigger`-independent internal-draft-only
   (same as every other trigger — never sent without an explicit operator
   action).
2. `instruction_text` is present in the operator conversation-detail view
   and in `ai.draft_generated`/`ai.draft_abstained`'s audit payload.
3. `instruction_text` never appears in any `/public/*` response schema
   (T122, confirmed by static grep of `anonymous_access/router.py` and
   `conversations/projections.py` — the only modules building
   `/public/*`-facing payloads — and by earlier live HTTP verification)
   unless an operator explicitly sends text containing it in a message
   body, which is then just ordinary message content.
4. `prompts/rag_answer.md`'s "Operator steering instruction" section tells
   the model this role is never customer speech and must never be echoed
   into `draft_text`.

## H. Clear/reset [V3-7, outcome 8]

1. Generate a draft and/or run a manual search; click "Limpar"; verify the
   draft panel and evidence-search results are both gone.
2. Verify message-selection checkboxes are unaffected (independent of
   V2-4's "desmarcar conversas").
3. Verify no durably stored `ai_generations`/`audit_events` row is deleted
   — this is pure client-side state, no server round-trip.
4. Verify no navigation away from the conversation occurs.

## I. Guided knowledge-CRUD inputs and "transformar em Q&A" [V3-8, outcomes 9/9a]

1. The category selector (`GET /operator/knowledge/categories`) reflects a
   category created moments earlier by another request — no client-side
   staleness layer.
2. The dynamic-table dropdown (`GET /operator/knowledge/dynamic-tables`)
   lists exactly `ALLOWLISTED_TABLES`' keys, never a sensitive/arbitrary
   table name.
3. Filter/output-column suggestions for a selected table
   (`GET .../dynamic-tables/{table}/columns`) come only from that table's
   real columns via live `sqlalchemy.inspect()` reflection; a
   non-allowlisted table 404s before any introspection happens.
4. On an `edit`-tagged message, "Transformar em Q&A" opens the guided
   create-entry form pre-filled with the customer's triggering message,
   `sent_text`, and a suggested category (via a one-time sessionStorage
   handoff, not a new endpoint); no `content.qa_entries` row is created
   until the operator explicitly submits the form.
5. The shared registry backs both administrative (`qa_entries.category`)
   and clinical-site (`documents.cancer_type`) categorization — proven by
   the migration's backfill and `test_category_derivation.py`.

## J. Countdown indicator [V3-9, outcome 10]

1. With uncovered customer activity, the countdown is visible and counts
   down, never showing a negative value.
2. New customer activity while the countdown is active extends/resets it —
   matching V2-7's existing reset behavior, not a separate clock.
3. The countdown never itself triggers a generation — it only reflects
   server-computed `automatic_draft_eligible`/`automatic_draft_seconds_remaining`
   state (`automatic_draft_status()`, read-only, mirrors
   `evaluate_automatic_trigger`'s guard minus the elapsed-time check).
4. V2's own typing-debounce acceptance outcome (`acceptance.md` §D) is
   unaffected — confirmed by `v2.spec.ts`'s T124 continuing to pass
   unmodified.

## K. Scroll-to-top on evidence selection [V3-10, outcome 11]

1. Scrolled away from the top, selecting a manual-search evidence item
   scrolls the page to the top.
2. Scrolled back down afterward, the unrelated 2-second conversation poll
   does not yank the position back to top — scoped to the evidence-select
   click handler only, never a `useEffect` keyed on poll-refreshed state.
3. "Gerar rascunho"/regenerate-with-instruction do not trigger this
   scroll — scoped to evidence selection only.

## L. Confirm-before-close [V3-11, outcome 12]

1. On both the customer and operator surfaces, clicking "Encerrar
   conversa" shows a confirm prompt; the conversation's status is
   unchanged until confirmed.
2. Choosing "Retornar e continuar conversa" leaves the conversation's
   status and all other state completely unchanged — no request is sent
   (`main.test.tsx`'s two V3-11 tests assert zero network calls on cancel).
3. Confirming actually closes the conversation on both surfaces.

## M. Satisfaction survey [V3-12, outcome 13]

1. The survey appears only after the conversation is already closed — it
   never blocks or delays the close itself (`V3-11`'s close action and
   `V3-12`'s survey are two independent steps).
2. Submitting before close is rejected (`409 NOT_CLOSED`); skipping the
   survey leaves no `conversation_satisfaction_responses` row at all — not
   a partial one.
3. A submitted response is tied to the correct `conversation_id`, and its
   `category_slug` is denormalized from that conversation's most recent
   `ANSWER` generation with a non-null category at submission time.
4. A second submission for the same conversation is rejected
   (`409 ALREADY_SUBMITTED`) — not silently overwritten or duplicated.
5. The response is reflected in V3-4's metrics (`docs/metrics/v3_queries.sql`
   query 4: average score and resolved-rate, overall and by category).

## N. Security negative checks (extends V2 §I)

- quick-approve cannot fire without an explicit authenticated-operator
  action (§C);
- `escalate`/`mark-incorrect` write only their own dedicated columns — no
  queue/routing/re-classification table exists for them to reach (§B);
- evaluation cases have no FK path to/from conversations or generations,
  so they cannot be mistaken for production data in a query that forgets
  to filter them (§F);
- `instruction_text` never reaches a `/public/*` schema (§G);
- the dynamic-table/column introspection endpoints never expose a
  non-allowlisted table, even via a crafted table-name path parameter (§I);
- **a real, distinct finding from this cycle**: the V2-2 per-source
  token-validation rate limiter's client key was `request.client.host`,
  which — behind this project's one same-origin reverse-proxy hop (local
  nginx; Firebase Hosting → Cloud Run in production) — collapsed every
  real customer onto one shared value, making the lockout global instead
  of per-customer (DECISIONS.md D-030). Found while adding this file's
  `v3.spec.ts` (running immediately after `v2.spec.ts`'s T128, which
  deliberately trips the lockout, made the collision reproducible for the
  first time). Fixed via `customer_care/shared/http.py`'s `client_ip()`
  (trusts `X-Forwarded-For`'s first entry, set — never appended/passed
  through — by the one trusted proxy hop) plus `frontend/nginx.conf`
  setting that header from its own view of the connecting peer. Regression
  covered by `test_client_ip.py` (4 tests) and confirmed via
  `smoke_v2_token_rate_limit.py` and `v2.spec.ts`'s T128 continuing to pass
  unmodified;
- all V1/V2 §I checks still pass unchanged (§G below).

## O. V1/V2 invariant regression (confirm unchanged under V3) [outcome 7]

- explicit human send remains the only path to a customer-visible operator
  message, for every `trigger` value including the two new
  regenerate-with-instruction/quick-approve paths;
- append-only audit remains true for every new V3 event type;
- no chain-of-thought is persisted anywhere in the new `ai_generations`
  columns, `content.evaluation_cases`, or
  `conversation_satisfaction_responses`;
- capacity (max-4), take-over, multiline rendering, token display/lockout
  (modulo D-030's fix), dynamic-pattern resolution, and knowledge-CRUD are
  unaffected by the V3 changes — confirmed by the full pre-existing
  `smoke_*` suite (9/9 pass, Phase 12/T121) and by `v1.spec.ts`/`v2.spec.ts`
  continuing to pass unmodified in the same `playwright test` run as this
  file's own `v3.spec.ts` (T132).

## P. Quality gates

- backend `ruff`/`mypy customer_care`/`pytest` all pass, including every
  new V3 test file;
- frontend `eslint`/`tsc --noEmit`/`vitest`/`vite build` all pass;
- `contracts/openapi.yaml` matches the implemented route table (no drift);
- no material V3 spec/plan/code divergence remains (`analysis.md`).

## Execution record — 2026-08-18

All sections A–O passed against local Docker Compose/PostgreSQL 17, real
Chrome via Playwright, and the configured real OpenAI provider. Evidence:

- **A** — migration additive-only, applied cleanly; no new Compose service.
- **B** — `test_taxonomy.py` (unit, fake-session) plus
  `smoke_v3_taxonomy_hcr.py` (all eight tags via real HTTP against a live
  backend: approve, edit, mark-incorrect idempotency, escalate tag-only,
  search, regenerate-with-instruction, take-over) plus `v3.spec.ts`'s first
  scenario (the same flows end-to-end through the real UI, including the
  quick-approve byte-for-byte assertion).
- **C** — `smoke_v3_taxonomy_hcr.py`'s approve section (byte-for-byte send
  + OpenAPI-route-absence negative test) plus `v3.spec.ts`.
- **D** — `docs/metrics/v3_queries.sql` query 2 plus
  `smoke_v3_metrics_agreement.py` (Phase 11) plus
  `smoke_v3_taxonomy_hcr.py`'s own SQL/Python HCR agreement check.
- **E** — structural check (T112: zero routes reference the metrics SQL
  file) plus `docs/metrics/v3_queries.sql` query 4.
- **F** — `test_evaluation_isolation.py` (structural FK-absence,
  no-customer-message, no-auto-rerun) plus `scripts/seed_evaluation_cases.py`
  seeding through the real API.
- **G** — `test_taxonomy.py`'s regenerate-with-instruction tests plus T122's
  static-grep leak check plus `prompts/rag_answer.md`'s steering-instruction
  section plus `v3.spec.ts`.
- **H** — `v3.spec.ts`'s "Limpar" scenario (draft/evidence cleared,
  checkbox selection unaffected, no navigation).
- **I** — `smoke_v3_knowledge_guided.py` (category freshness, allowlisted
  dropdown, real-column introspection, non-allowlisted 404) plus
  `test_category_derivation.py` plus `test_qa_transform.py` plus
  `v3.spec.ts`'s "transformar em Q&A" flow (pre-filled form, real
  navigation, no premature write).
- **J** — `v3.spec.ts`'s countdown scenario (visible, moves, never
  negative, extends on new activity) plus `test_automatic_draft_status.py`
  plus `v2.spec.ts`'s T124 continuing to pass unmodified.
- **K** — `v3.spec.ts`'s scroll-to-top scenario (scrolls on select, poll
  does not re-yank it).
- **L** — `main.test.tsx`'s two V3-11 cancel tests (customer + operator,
  zero network calls) plus `v3.spec.ts`'s confirm-and-actually-close
  scenario (both surfaces).
- **M** — `smoke_v3_satisfaction.py` (blocked-before-close, skip-leaves-
  no-row, submit ties to conversation/category, duplicate rejected, audit
  event present) plus live Playwright verification of the survey UI during
  implementation.
- **N** — every listed check has its own test above; the D-030 rate-limiter
  finding is covered by `test_client_ip.py`, `smoke_v2_token_rate_limit.py`,
  and `v2.spec.ts`'s T128, all passing after the fix.
- **O** — the full 9-script pre-existing `smoke_*` suite passes (Phase
  12/T121); `v1.spec.ts` (1 scenario) and `v2.spec.ts` (4 scenarios,
  T124/T125/T126/T127 updated in this cycle to use V3-8's guided selectors
  in place of the free-text inputs they replaced) both pass unmodified in
  behavior, run together with `v3.spec.ts` in the same bare
  `playwright test` pass (12 tests, 1 skipped by design, 11 passed) —
  confirmed stable across two consecutive full runs.
- **P** — backend `ruff` (clean)/`mypy customer_care` (40 files clean)/
  `pytest` (55/55) and frontend `eslint`/`tsc --noEmit`/`vitest` (16/16)/
  `vite build` all pass; `contracts/openapi.yaml` spot-checked against the
  live route table with no drift found.

One real, previously-latent defect was found and fixed during this
execution pass, documented in `DECISIONS.md` D-030 and §N above: the V2-2
rate limiter's global-instead-of-per-customer lockout. This is a security
correction to a V2 mechanism, not a V3 product-behavior change; it required
no `spec.md`/`plan.md` text changes since plan.md §13.1's own requirement
("does not block legitimate customers") was already correct — only the
implementation was wrong.

Demo data was reset (`TRUNCATE ... CASCADE`) between test-file runs and the
`backend` container restarted where rate-limiter state needed clearing (a
now-necessary step after `v2.spec.ts`'s T128 in any full suite run, per
`v2.spec.ts`'s own `afterAll`). Synthetic data only, per Constitution
Article VI.
