# Project State

Last updated: 2026-08-11

## Lifecycle and authority

- V1 (`specs/001-v1-assisted-customer-service`) is the completed executable
  baseline. Its original acceptance gates completed on 2026-08-10.
- The human explicitly authorized the **V2 specification cycle** on 2026-08-11.
  Its feature package is `specs/002-v2-commercial-product-experience/`.
- V2 implementation is authorized only in SDD order: it must first complete
  `specify -> clarify -> plan -> tasks -> analyze`, with acceptance coverage,
  before production code is written.
- Dynamic appointment availability is a separate future feature, recorded in
  `ROADMAP.md` and D-026. It is not V2 scope unless explicitly added later.

## V1 baseline

V1 provides anonymous per-tab web conversations, authenticated operator
service, manual queue/capacity, global N1/N2 modes, RAG ingestion/retrieval,
internal AI drafts, explicit operator send, clinical-only customer citation
exposure, and append-only audit events. The V1 hard safety boundaries remain in
force while V2 is designed: no direct AI send, no raw anonymous token at rest
or in URLs/logs, server-side authorization/exposure enforcement, and manual
service when AI/RAG fails.

The 2026-08-10 acceptance record covers PostgreSQL 17/pgvector migrations,
ingestion (57 clinical parents, 570 children, 86 Q&A records), N1/N2 API and
E2E paths, capacity, security negatives, real-provider smoke, and the normal
quality gates. Refer to `specs/001-v1-assisted-customer-service/acceptance.md`
and `analysis.md` §9 for details.

## V1 post-acceptance refinements (committed)

The post-acceptance refinements are committed at `c150e6c` (2026-08-11); the
working tree is clean. An earlier version of this section described them as
uncommitted — that was stale from the moment it was written, since it was
authored in the same commit that landed them. Corrected 2026-08-12 during the
independent closure review below.

They cover:

- preserved multiline rendering for customer and operator messages;
- renamed operator control `Assumir controle`;
- concise customer-ready draft prompt/provider behavior, without an artificial
  completion-token ceiling;
- retrieval-specific behavior: clinical rank-one result yields the complete
  parent document for explicit send; administrative Q&A is interpreted by the
  LLM; no-evidence replies stay general/clarifying and safe;
- manual evidence results now show full content and matching clinical child
  excerpt, but remain evidence-only in V1;
- V1 spec/plan/tasks/OpenAPI/acceptance/analysis updates and deterministic
  provider regression tests supporting those behaviors.

The refinements are recorded in V1 `analysis.md` §§11–15. Frontend lint,
TypeScript, Vitest, and production build passed; Python compilation and the
deterministic generation strategy tests passed; the Compose stack was healthy.

## Independent closure review — 2026-08-12

A read-only closure review (`PROMPT_REVIEW_V1_CLAUDE.md`) verified the above
refinements against the running code, then reran the previously-outstanding
gates with human authorization. Full detail in V1 `analysis.md` §16.

- Backend `ruff`, `mypy`, and `pytest` (13/13): pass.
- Frontend ESLint, TypeScript, Vitest (5/5), production build: pass.
- Credential-backed E2E against a rebuilt Compose stack with a real
  `OPENAI_API_KEY`: `smoke_core`, `smoke_n2`, `smoke_concurrent_capacity`,
  `smoke_ingestion_changed`, and `smoke_real_provider` all pass.
- `smoke_resilience` fails to exercise its intended assertion: the retrieval-
  specific refinement above (clinical rank-one → full parent document) never
  calls `configured_generation_provider()` for a triggering message whose top
  evidence is clinical, so the test's provider-failure monkeypatch has nothing
  to intercept. The underlying invariant (AI/RAG failure leaves manual service
  available) is independently confirmed by code inspection of the `except`
  branch in `app/customer_care/ai/router.py`, but this specific negative test
  needs to be updated to a query/path that actually reaches the provider call.
  Tracked as a small V1 test-only fix, not a product defect.
- The `dynamic_data_required=true` finding (administrative evidence with
  literal internal identifiers such as `scheduling.available_offers` reaching
  the LLM with only a prompt-level, not code-level, safeguard) is confirmed
  still present. The human decision on its correction is recorded in
  `DECISIONS.md` D-028 and `ROADMAP.md`: the correction is planned, not
  implemented in V1, and its execution enters V2 planning.

## V2 handoff

Read `CLAUDE_CODE_HANDOFF.md` after this file. The V2 draft specification
captures only decisions already made by the human:

- professional customer/operator experience;
- customer-safe display/copy of the conversation token;
- operator-selected evidence from manual search, with full clinical parent
  expansion for explicit send and Q&A evidence for LLM composition;
- operator-selected customer and operator message context for draft generation;
- durable traceability/audit of selections, expansions, generations, and final
  sends.

It also lists the product decisions that require clarification before a V2 plan
or code can be honestly produced.

## Immediate next action for Claude Code

1. Read `AGENTS.md`, the constitution, this file, `CLAUDE_CODE_HANDOFF.md`,
   the V2 draft spec, complete V1 package, and current Git diff.
2. Preserve the V1 worktree; verify/commit it only with human authorization.
3. Clarify the open V2 decisions and update V2 `spec.md` as their canonical
   resolution.
4. Create V2 plan/tasks/contracts/data model/acceptance, run cross-artifact
   analysis, and then implement V2 in dependency order.
