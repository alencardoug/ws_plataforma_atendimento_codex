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

## Current uncommitted V1 refinements

The worktree intentionally contains post-acceptance refinements. Do not reset,
checkout, or overwrite them while starting V2. Review them, run the applicable
gates, and commit only on human instruction.

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
The full Python lint/type/pytest tools and credential-backed E2E were not
available in the final refinement environment, so rerun them before committing
or declaring a new full-gate record.

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
