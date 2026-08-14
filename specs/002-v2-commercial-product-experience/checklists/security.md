# Security Checklist — V2

Extends `specs/001-v1-assisted-customer-service/checklists/security.md`,
which remains in force unchanged. New/changed items only:

- [ ] Short-format anonymous token still never stored raw server-side (only
  the digest, unchanged mechanism).
- [ ] Token validation is rate-limited (IP/source-keyed); lockout does not
  block legitimate use.
- [ ] Token display/copy affordance creates no session-recovery or
  cross-tab-resume path.
- [ ] `qa_dynamic_bindings.source_table` cannot resolve against any table
  outside the server-side allowlist, including via a crafted/malformed
  binding row.
- [ ] Dynamic-pattern resolution failure cause (table/column/query detail)
  never reaches `draft_text` or any customer-facing field — audit/operator
  only.
- [ ] "Buscar evidências" accepts exactly one `retrieval_hit_id`; no request
  shape allows multi-selection.
- [ ] Selected clinical evidence has no LLM-composed-short-reply alternative
  anywhere in V2 — full parent document only.
- [ ] `selected_message_ids` is re-validated server-side against the target
  conversation on every request; never trusted from the client as
  authorization.
- [ ] V2-8 knowledge CRUD routes require `operatorBearer` auth identically to
  the rest of the operator surface; no anonymous or customer-token path
  reaches them.
- [ ] V2-8 "delete" is soft (`is_active = false`) only; no route performs a
  hard delete that could break FK integrity for historical
  `ai_generation_sources`/`message_citations`.
- [ ] `conversation.typing_heartbeat` events are not audited (documented
  exception, not an oversight) and carry no message content.
- [ ] Prompt/model output still cannot alter authorization/maturity state
  (carried over from V1, re-verified against the new generation triggers).
