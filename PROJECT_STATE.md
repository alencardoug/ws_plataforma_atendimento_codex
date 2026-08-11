# Project State

Last updated: 2026-08-11

## Lifecycle

- long-term product discovery: sufficiently complete for roadmap;
- V1 requirements clarification: complete;
- V1 spec baseline: ready;
- V1 implementation plan: complete and repository-converged;
- V1 tasks: complete (T000–T200);
- V1 code: **DONE**; all required implementation and acceptance gates pass;
- V2+: roadmap only.

## Authorized feature

`001-v1-assisted-customer-service`

## External review

`specs/001-v1-assisted-customer-service/analysis.md` — cross-artifact analysis
performed by Claude Code (2026-08-10), acting as external reviewer, not the
authoring agent. Confirms the spec package is internally consistent; lists
concrete spec-vs-repository gaps (PostgreSQL 17 vs. 16 running, missing
Alembic/backend/frontend scaffolding, parent-child ingestion adapter design,
missing `.env.example` vars) and originally raised one open scope decision
about the pre-existing scheduling/identity/billing schema and `app/main.py`.
Read the Codex follow-up below before starting Phase 1.

Codex follow-up §§8–9 (2026-08-10) reconciles the version-controlled corpus and
repairs the plan: the existing 57 `content.documents` parents, 570
`content.chunks` children, and 86 flat `content.qa_entries` are adopted in
place; no synthetic PARENT chunks or duplicate knowledge tables are created.
The existing `app/`/pip project is evolved rather than replaced. Legacy
scheduling/payment/CPF endpoints are excluded from the V1 runtime while their
source/schema may remain dormant. The post-implementation convergence records
the completed V1 and confirms no material spec/code divergence.

## V1 decisions frozen

- anonymous customer, no account/password;
- customer browser close/session close ends V1 experience;
- operator authentication required;
- global N1/N2 configuration only;
- N1 optional manual knowledge search;
- N2 grounded AI draft + explicit operator send;
- operator may `Take over` N2 conversation -> conversation remains N1 until closed;
- no streaming;
- operator manually claims conversations;
- maximum 4 active conversations/operator;
- acceptance test: 6 client tabs, 4 active, 2 waiting;
- ingestion/vectorization is V1 scope;
- administrative Q&A uses flat retrieval records;
- clinical knowledge uses parent-child retrieval;
- clinical citations can be customer-visible; administrative Q&A citations cannot;
- insufficient evidence -> abstain draft; no automatic escalation;
- conversation history is persisted and used within the active conversation;
- no cross-session customer memory in V1;
- all data synthetic/demo;
- local Docker Compose only; no GCP acceptance requirement.

## V1 acceptance result

- PostgreSQL 17/pgvector and forward-only Alembic migration pass from empty and legacy-baseline databases.
- Canonical knowledge contains 57 clinical parents, 570 child chunks, and 86 flat administrative Q&A records.
- Deterministic API acceptance, real OpenAI adapter smoke, concurrent max-four capacity, restart/audit/security checks, and Chrome E2E N1/N2 scenarios pass.
- Backend Ruff/mypy/pytest and frontend ESLint/TypeScript/Vitest/build/Playwright gates pass.
- The normal Compose stack is restored from `.env` and healthy on 2026-08-10.

## Post-acceptance fixes — 2026-08-11

- operator workspace now polls the selected conversation as well as the queue,
  so new customer messages appear automatically;
- operator workspace now exposes an explicit `Encerrar conversa` action using
  the existing audited close endpoint.
- operator provisioning is now explicitly limited to the offline seed command;
  Compose allowlists supported backend settings and does not forward unsupported
  `LOGIN_OPERATOR_*` values, startup creates no account, and repeated normalized
  email seed updates/reactivates one account.

## Next action

Human acceptance may now be performed at `/customer` and `/operator`. Stop
before V2 unless a new feature is explicitly authorized.
