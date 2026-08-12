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
4. Inspect `git status` and `git diff` before editing. The V1 post-acceptance
   changes described below are intentional and already committed at `c150e6c`;
   the working tree is clean as of the 2026-08-12 independent closure review.
   Never reset, checkout, or overwrite them as a shortcut.

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

## Intentional V1 changes (committed, gates reconfirmed)

Commit `c150e6c` covers the following V1 corrections:

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

Read V1 `analysis.md` §§11–15 for the diagnosis and verification evidence, and
§16 for the 2026-08-12 independent closure review that reran the previously
outstanding gates: backend ruff/mypy/pytest, frontend lint/typecheck/Vitest/
build, and the credential-backed E2E suite (`smoke_core`, `smoke_n2`,
`smoke_concurrent_capacity`, `smoke_ingestion_changed`, `smoke_real_provider`)
all pass. `smoke_resilience` needs a test-only update — see §16 — because the
clinical-rank-one full-parent shortcut now bypasses the provider call its
failure-injection technique relies on.

That same review confirmed the `dynamic_data_required=true` finding named in
`ROADMAP.md`/D-026 is still present (administrative evidence with literal
internal identifiers can reach the LLM with only a prompt-level safeguard).
The human decision on its correction is recorded in `DECISIONS.md` D-028: a
deterministic template-substitution mechanism (resolver fills variables from
the database into the chunk pattern; the LLM does not rewrite that response)
is planned, with its execution entering V2 planning rather than V1 code.

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
