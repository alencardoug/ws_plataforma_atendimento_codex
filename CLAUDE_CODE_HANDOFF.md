# Claude Code Handoff — V1 Baseline to V2 Specification

**Prepared:** 2026-08-11
**Human authorization:** continue V2 in SDD order; do not begin V2 production
implementation before its SDD gates are satisfied.

## Start here

1. Read `AGENTS.md` first, then `.specify/memory/constitution.md`.
2. Read `PROJECT_STATE.md`, this handoff, and
   `specs/002-v2-commercial-product-experience/spec.md`.
3. Read the whole V1 feature package and the root architecture/security/data/
   test/operations/decision documents.
4. Inspect `git status` and `git diff` before editing. The current V1
   post-acceptance changes are intentional and uncommitted. Preserve them;
   never reset, checkout, or overwrite them as a shortcut.

`CLAUDE.md` contains the repository-specific operating protocol.

## Current product boundary

V1 remains the running baseline. Its non-negotiable safety boundaries are:

- customer token is per-conversation and raw value is never persisted, logged,
  or put in URLs;
- only an authenticated operator's explicit send produces a customer-visible
  operator message; AI has no send authority;
- customer never receives drafts/internal retrieval or non-exposable Q&A source
  metadata;
- clinical citation exposure, authorization, capacity, and audit are enforced
  server-side;
- RAG/AI failure leaves manual service available;
- no chain-of-thought persistence and synthetic/demo data only.

V2 must preserve these until an approved V2 artifact explicitly and safely
supersedes a behavior. Dynamic appointment availability is not V2 scope.

## Human-approved V2 inputs

- professional UI/UX;
- show the customer their own conversation token and provide copy, safely;
- manual-search result selection before generation;
- selected clinical child -> complete parent document available for explicit
  operator send;
- selected Q&A -> LLM creates only a concise response focused on the customer
  request, with no chunk dump or drafting commentary;
- a checkbox on every customer/operator message lets the operator choose the
  context given to draft generation;
- selections, parent expansion, generation inputs/provenance, and final send
  are traceable/audited.

The V2 draft specification contains the acceptance intent and the unanswered
decisions. Do not guess their behavior. Clarify them with the human, record the
answers in V2 `spec.md`, then proceed through plan, tasks, contracts/data model,
acceptance, and analysis.

## Intentional V1 worktree changes to review

The current diff covers the following V1 corrections:

- newline-preserving message rendering in customer/operator histories;
- label `Assumir controle` in place of `Take over`;
- versioned concise-draft prompt passed to the provider, with no artificial
  output token cap (a cap caused empty `gpt-5-mini` completions because its
  reasoning consumed the budget);
- strategy by highest-ranked retrieval: complete clinical parent for explicit
  send; Q&A LLM interpretation; short safe no-evidence response;
- manual-search display of full evidence content and clinical matched-child
  excerpt, still without V2 selection/generation coupling;
- regression coverage and synchronized V1 documentation.

Read V1 `analysis.md` §§11–15 for the diagnosis and verification evidence.

Before committing those V1 changes, rerun the relevant gates where the
environment allows them. The last refinement pass passed frontend ESLint,
TypeScript, Vitest, production build, Python compilation, deterministic
generation tests, and Compose readiness. Full backend lint/type/pytest and the
credential-backed E2E run were unavailable at that time; run them when their
tools/credentials are available. Do not claim a new full-gate result otherwise.

## Suggested V2 sequence

1. Resolve section 7 of the V2 draft spec with the human.
2. Turn confirmed outcomes into stories, FR/NFRs, abuse/security cases, and
   measurable acceptance scenarios.
3. Design migrations and audit/provenance records before APIs/UI.
4. Update contracts, plan, tasks, data model, security/test documents, and
   checklists; run cross-artifact analysis and repair contradictions.
5. Implement in dependency order and rerun all affected unit, integration, API,
   frontend, E2E, and convergence gates.

## Documentation decisions already made

- `002-v2-commercial-product-experience` is the next V2 package.
- Dynamic appointment availability was moved from “next cycle” to a separate
  roadmap item (D-026); it is not implicitly folded into V2.
- D-027 records the V2 specification authorization.
- `AGENTS.md`, `CLAUDE.md`, `PROJECT_STATE.md`, `README.md`, and
  `SDD_MANIFEST.md` were updated to make that scope and stop condition explicit.

No commit was created as part of this handoff.
