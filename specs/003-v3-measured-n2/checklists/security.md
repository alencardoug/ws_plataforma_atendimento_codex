# Security Checklist — V3

Extends `specs/002-v2-commercial-product-experience/checklists/security.md`
(itself extending V1's), which remains in force unchanged. New/changed items
only. Finalized against the implemented state (2026-08-18) — every item
below was re-verified against real code/tests during Phase 13, not just
carried over from the plan-time draft.

- [x] Every new operator endpoint (mark-incorrect, escalate, categories
  list/create, dynamic-tables list, column introspection, evaluation cases
  list/create/patch) requires `operatorBearer` auth identically to the rest
  of the operator surface; no anonymous or customer-token path reaches
  them. Evidenced by: `tasks.md` T035, T064, T074;
  `smoke_v3_knowledge_guided.py`'s explicit 401 checks.
- [x] Mark-incorrect/escalate additionally require the requesting operator
  to be the conversation's assigned operator (`require_assignment`), same
  as every other conversation-scoped action; a `generation_id` that
  belongs to a different conversation than the path's `conversation_id`
  returns `422`, never a silent no-op. `tasks.md` T031/T032/T035.
- [x] The new public endpoint (satisfaction) requires the existing
  `token_bound_conversation` dependency; no new customer-auth mechanism was
  introduced; the raw token is never persisted or logged (unchanged
  mechanism, re-verified). `tasks.md` T100/T104; `smoke_v3_satisfaction.py`.
- [x] Column introspection (V3-8) never resolves a table name outside
  `ALLOWLISTED_TABLES` — 404 before any SQL/reflection call for an
  unlisted name, including crafted/malformed table-name input.
  `tasks.md` T061/T064; `smoke_v3_knowledge_guided.py`'s two 404 checks
  (existing-but-not-allowlisted, and nonexistent); `plan.md` §11/§18
  explains why this is a stronger guarantee than literal
  `information_schema` SQL would give.
- [x] `content.categories`'s FK constraints (on `qa_entries.category` and
  `documents.cancer_type`) make it structurally impossible to write an
  unregistered category value to either table, closing the fragmentation
  risk V3-8 was raised to fix. `tasks.md` T012; `test_category_derivation.py`.
- [x] `instruction_text` (V3-6) gets the same non-customer-facing treatment
  `manual_search_text` already gets — present only in operator/audit
  responses, absent from every public/customer-facing schema. `tasks.md`
  T053/T122, `acceptance.md` §G.
- [x] Quick-approve (V3-2) cannot be invoked without `CurrentOperator` +
  assignment-gating + the `STALE_GENERATION` freshness check — no
  parallel/lighter-weight send path was introduced for it. `tasks.md` T040,
  `acceptance.md` §C.
- [x] `content.evaluation_cases` has no FK path into
  `conversations`/`ai_generations`, and no production query
  (`docs/metrics/v3_queries.sql`) joins against it — isolation is
  structural, verified by schema review, not just by a `WHERE` clause that
  could later be forgotten. `tasks.md` T074; `test_evaluation_isolation.py`.
- [x] `conversation_satisfaction_responses` writes are rejected unless the
  conversation is already `CLOSED`; a second submission against the same
  conversation is rejected (`UNIQUE(conversation_id)` plus a clean
  `409 ALREADY_SUBMITTED`). `tasks.md` T100/T104; `smoke_v3_satisfaction.py`.
- [x] Prompt/model output still cannot alter authorization/maturity state
  or the new taxonomy columns — `marked_incorrect_at`/`escalated_at`/
  `category_slug` are only ever written by explicit operator-triggered
  endpoints or the server-side derivation in `generate_draft`/
  `select_evidence`, never by LLM output. Code review at `tasks.md` T134
  (`analysis.md`).
- [x] **Found during this cycle, not anticipated at plan time**: the V2-2
  per-source token-validation rate limiter's client key
  (`request.client.host`) collapsed every real customer behind this
  project's one reverse-proxy hop onto one shared value, making the
  "per-source" lockout global — one attacker's lockout would deny every
  legitimate customer. Fixed via `customer_care/shared/http.py`'s
  `client_ip()` (trusts `X-Forwarded-For`'s first entry, which the one
  trusted proxy hop always sets from its own view of the peer, never a
  client-supplied value) plus `frontend/nginx.conf`. Recorded as
  `DECISIONS.md` D-030; regression-covered by `test_client_ip.py` (4
  tests); `acceptance.md` §N.
