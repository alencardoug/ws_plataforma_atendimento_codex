# Project State

Last updated: 2026-08-10

## Lifecycle

- long-term product discovery: sufficiently complete for roadmap;
- V1 requirements clarification: complete;
- V1 spec baseline: ready;
- V1 implementation plan: ready for analyze pass;
- V1 tasks: ready for analyze pass;
- V1 code: not started in this package;
- V2+: roadmap only.

## Authorized feature

`001-v1-assisted-customer-service`

## External review

`specs/001-v1-assisted-customer-service/analysis.md` — cross-artifact analysis
performed by Claude Code (2026-08-10), acting as external reviewer, not the
authoring agent. Confirms the spec package is internally consistent; lists
concrete spec-vs-repository gaps (PostgreSQL 17 vs. 16 running, missing
Alembic/backend/frontend scaffolding, parent-child ingestion adapter design,
missing `.env.example` vars) and one open scope decision (fate of the
pre-existing scheduling/identity/billing schema and `app/main.py`) that the
project owner must resolve before Phase 1. Read this before starting
`tasks.md` Phase 0/1.

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

## Next coding-agent action

1. Read `AGENTS.md` / `CLAUDE.md` and constitution.
2. Read the entire feature directory.
3. Run a cross-artifact consistency/analyze pass.
4. Fix documentation contradictions before code.
5. Implement tasks in dependency order.
6. Run all acceptance gates.
7. Converge implementation against the spec.
8. Stop before V2.
