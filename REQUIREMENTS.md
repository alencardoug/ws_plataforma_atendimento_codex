# Repository Requirements Index

Executable V1 requirements are canonical in `specs/001-v1-assisted-customer-service/spec.md`.

## Product goals

- G-01: deliver an end-to-end customer service conversation experience.
- G-02: demonstrate manual N1 and AI-copilot N2 without autonomous customer messaging.
- G-03: build a usable RAG from currently non-vectorized administrative and clinical knowledge.
- G-04: make RAG evidence, AI drafts, human edits, and sends auditable.
- G-05: support manual queue handling with an operator capacity of four active conversations.
- G-06: preserve channel abstraction for later Telegram without implementing Telegram in V1.
- G-07: preserve future autonomy evolution without leaking N3/N4 complexity into V1.

## Repository-wide invariants

- NFR-ARCH-01: modular monolith; no microservices in V1.
- NFR-ARCH-02: core conversation logic is independent of web transport.
- NFR-DATA-01: PostgreSQL is source of truth.
- NFR-DATA-02: schema changes use migrations.
- NFR-AI-01: provider/model selection is configuration, not domain logic.
- NFR-AI-02: generation traceability includes retrieval evidence and prompt/model identifiers.
- NFR-AI-03: no hidden reasoning/chain-of-thought persistence.
- NFR-AUD-01: critical operational facts emit immutable application audit events.
- NFR-SEC-01: operator authorization is server-side.
- NFR-SEC-02: secrets are externalized.
- NFR-SEC-03: anonymous customer access is scoped to one conversation token.
- NFR-DEMO-01: synthetic/demo data only.
- NFR-FAIL-01: AI/RAG failure does not break manual service.
- NFR-TEST-01: direct AI-to-customer send has a negative automated test.
