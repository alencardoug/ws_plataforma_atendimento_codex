# Security Checklist — V2

Extends `specs/001-v1-assisted-customer-service/checklists/security.md`,
which remains in force unchanged. New/changed items only:

- [x] Short-format anonymous token still never stored raw server-side (only
  the digest, unchanged mechanism). `anonymous_access/security.py`
  (`issue_conversation_token`/`digest_conversation_token`);
  `test_security_and_ingestion.py::test_anonymous_token_is_returned_only_as_one_way_digest`.
- [x] Token validation is rate-limited (IP/source-keyed); lockout does not
  block legitimate use. `test_anonymous_token_rate_limit.py` (8 unit
  tests) + `smoke_v2_token_rate_limit.py` (E2E through the real HTTP
  route; also proves the audit event fires, T111).
- [x] Token display/copy affordance creates no session-recovery or
  cross-tab-resume path. Confirmed by code review: no endpoint accepts a
  bare token to look up/resume a conversation without also supplying its
  `conversation_id`; `CustomerPage` only ever reads its own token from
  `sessionStorage`, never persists it elsewhere.
- [x] `qa_dynamic_bindings.source_table` cannot resolve against any table
  outside the server-side allowlist, including via a crafted/malformed
  binding row. `smoke_v2_dynamic_pattern.py` (resolution-time). Also
  now enforced at write time — `knowledge/router.py`'s `validate_binding`
  (added during Phase 11 convergence, T121: `data-model.md` §6 already
  documented this as required but it had not been implemented) rejects a
  non-allowlisted `source_table` or unknown column with `422` at
  creation/update, proven by `smoke_v2_knowledge_crud.py`.
- [x] Dynamic-pattern resolution failure cause (table/column/query detail)
  never reaches `draft_text` or any customer-facing field — audit/operator
  only. `smoke_n2.py`'s V2-6 section (cause-string-absent-from-response
  negative test) + `smoke_v2_dynamic_pattern.py`.
- [x] "Buscar evidências" accepts exactly one `retrieval_hit_id`; no request
  shape allows multi-selection. Structural: `select_evidence(retrieval_hit_id:
  UUID, ...)` takes it as a single path parameter, not a request-body list.
- [x] Selected clinical evidence has no LLM-composed-short-reply alternative
  anywhere in V2 — full parent document only. `full_parent_draft` always
  takes the rank-1-CLINICAL branch before any LLM call in both
  `generate_draft` and `select_evidence`; `smoke_n2.py` T057
  (`model == "not-applicable"`).
- [x] `selected_message_ids` is re-validated server-side against the target
  conversation on every request; never trusted from the client as
  authorization. `ai/router.py` `draft()`: queries messages scoped to
  `conversation_id` and 422s as `MESSAGE_NOT_IN_CONVERSATION` on any ID
  not found in that scoped set.
- [x] V2-8 knowledge CRUD routes require `operatorBearer` auth identically to
  the rest of the operator surface; no anonymous or customer-token path
  reaches them. `smoke_v2_knowledge_crud.py` (401 for both anonymous and
  customer-token credentials).
- [x] V2-8 "delete" is soft (`is_active = false`) only; no route performs a
  hard delete that could break FK integrity for historical
  `ai_generation_sources`/`message_citations`. Code review: every
  `deactivate_*` handler sets `is_active = False`; no `session.delete(...)`
  on content rows anywhere in `knowledge/router.py`.
  `smoke_v2_knowledge_crud.py` confirms a deactivated entry stays
  `GET`-able by ID.
- [x] `conversation.typing_heartbeat` events are not audited (documented
  exception, not an oversight) and carry no message content. Code review:
  `typing_heartbeat()` in `anonymous_access/router.py` never calls
  `record_event`; documented explicitly in `EVENT_CATALOG.md` (T112).
- [x] Prompt/model output still cannot alter authorization/maturity state
  (carried over from V1, re-verified against the new generation triggers).
  Code review: `effective_mode` is only ever written by `take_over()` (an
  explicit operator action); no code path in `ai/router.py` or
  `knowledge/dynamic_binding.py` writes to `Conversation.effective_mode`,
  `status`, or any auth-related column.
