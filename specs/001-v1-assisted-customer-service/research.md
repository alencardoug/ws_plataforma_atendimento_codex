# V1 Research / Design Rationale

## R1 — React/TypeScript/Vite instead of Streamlit

The operator workspace is a core portfolio surface and requires multiple simultaneous conversations, role-aware views, per-tab anonymous customer simulation, and future streaming/channel evolution. A SPA avoids likely UI rewrite debt.

## R2 — Per-tab sessionStorage token

Cookies/localStorage are shared across tabs/origin and complicate simulating six independent anonymous customers. `sessionStorage` is tab-scoped. Server still verifies an opaque conversation token and stores only its digest.

## R3 — Operator-triggered/selected-conversation N2 draft

V1 intentionally avoids adding a durable background-job system. Customer message persistence/acknowledgement must not wait on LLM latency. When operator opens/selects an active N2 conversation, UI can request the draft for the latest unanswered customer message. This keeps behavior useful and implementation deterministic.

## R4 — PostgreSQL + pgvector

The project already uses PostgreSQL and V1 needs transactional state + vector retrieval. A separate vector database adds unnecessary operational complexity.

## R5 — Dual knowledge strategy

Forcing parent-child hierarchy onto flat administrative Q&A provides no benefit. Clinical content already has parent-child structure and should exploit child precision + parent context.

## R6 — Separate AIGeneration and Message

This makes the no-auto-send invariant structural, supports immutable generations/regeneration lineage, and lets future Human Correction Rate compare draft to final message.

## R7 — Offline ingestion

RAG cannot be demonstrated without vectorization. Ingestion therefore belongs in V1, but an ingestion UI does not.

## R8 — No heavy orchestration framework required

The V1 flow is simple enough to implement with explicit application services and provider ports. A framework such as LangChain/LlamaIndex is not prohibited, but it must not be added without a concrete, documented V1 advantage.
