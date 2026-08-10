# Customer Care AI — Spec-Driven Development Repository

Status: **V1 SPECIFICATION BASELINE — implementation not started**.

This repository defines a single-tenant AI-assisted customer-service platform for a Cancer Center. The long-term product evolves from manual human service to governed AI autonomy, but the currently authorized implementation scope is **V1 only**.

## Canonical engineering method

Use Spec-Driven Development (SDD) with GitHub Spec Kit conventions.

Canonical lifecycle for a feature:

1. constitution
2. specify
3. clarify when ambiguity remains
4. plan
5. tasks
6. analyze consistency
7. implement
8. converge against spec and acceptance criteria

`grill-me` / aggressive design interview is optional discovery before a future spec is frozen. It is not a second source of truth. Resolved answers must be written into the canonical spec/ADR.

## V1 product thesis

V1 proves a complete assisted-service loop:

`anonymous customer -> waiting queue -> operator -> RAG evidence -> AI draft in N2 -> explicit operator action -> customer-visible answer -> audit`

The application supports only two durable global maturity modes:

- **N1 Manual** — customer and operator converse manually. Optional assistive knowledge search can be enabled by configuration.
- **N2 Copilot** — RAG + AI can generate a grounded draft for the operator, but **AI output is never sent directly to the customer**. An operator may take over a conversation, reducing that conversation from N2 to N1 for the remainder of the session.

## V1 actors

- anonymous customer;
- authenticated operator;
- runtime configuration managed outside the UI.

Supervisor, manager, and AI Ops interfaces are future scope.

## V1 knowledge

V1 must build the usable RAG because the PostgreSQL environment exists but the knowledge is not yet vectorized.

Two source families are supported:

1. **Administrative Q&A** — flat Q&A records; no parent-child hierarchy.
2. **Clinical knowledge** — pre-structured parent-child content; child chunks are indexed for retrieval and parent context is supplied to generation.

Ingestion is an offline/administrative command or script, **not an ingestion UI**.

Clinical source references may be exposed to the customer. Administrative Q&A source details remain operator-only.

## V1 concurrency demo

One operator can have at most **4 active conversations**. The acceptance demo creates **6 anonymous customer sessions in separate browser tabs**. The operator claims 4; 2 remain waiting. This is a functional concurrency/queue test, not a production load target.

Anonymous customer session credentials are per-tab, not account credentials. A per-conversation opaque access token is stored in browser `sessionStorage`, allowing multiple independent customers to be simulated in tabs of one browser.

## Hard invariants

1. V1 supports N1/N2 only.
2. No AI draft can become customer-visible without explicit operator send action.
3. `Take over` is an operator-controlled per-conversation downgrade from N2 to N1.
4. Customer data is synthetic/demo only in V1.
5. No chain-of-thought is persisted or shown.
6. AI generations are traceable to prompt version, model configuration, retrieval run, and source records.
7. PostgreSQL is the transactional source of truth.
8. Critical operational facts are recorded as append-only audit events.
9. Failure of AI/RAG must not prevent manual customer service.
10. Web is the only channel implemented in V1, but conversation/application services must remain channel-neutral for later Telegram support.

## Repository map

```text
.
├── .specify/memory/constitution.md
├── AGENTS.md
├── CLAUDE.md
├── PROJECT_STATE.md
├── PROMPT_START_V1.md
├── REQUIREMENTS.md
├── ARCHITECTURE.md
├── DATA_MODEL.md
├── API_SPEC.md
├── SECURITY.md
├── THREAT_MODEL.md
├── TEST_PLAN.md
├── OBSERVABILITY.md
├── DEVELOPMENT.md
├── DEPLOYMENT.md
├── OPERATIONS.md
├── ROADMAP.md
├── DECISIONS.md
├── GLOSSARY.md
├── docs/
├── adr/
├── prompts/
└── specs/001-v1-assisted-customer-service/
    ├── spec.md
    ├── plan.md
    ├── tasks.md
    ├── research.md
    ├── data-model.md
    ├── quickstart.md
    ├── acceptance.md
    ├── contracts/openapi.yaml
    └── checklists/
```

## Agent instruction

Implement **only** `specs/001-v1-assisted-customer-service/` until a human explicitly authorizes a subsequent feature/version.
