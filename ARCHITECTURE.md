# Architecture

## Style

V1 is a **modular monolith** with a React/TypeScript SPA frontend, a Python/FastAPI backend, PostgreSQL 17 + pgvector, and an external LLM/embedding provider behind ports/adapters.

No Redis, Kafka, Celery, service mesh, or microservices are required for V1.

## Target stack

Backend:

- Python 3.11+;
- FastAPI;
- Pydantic;
- SQLAlchemy 2.x;
- Alembic;
- PostgreSQL 17;
- pgvector;
- Poetry;
- OpenAI adapter behind provider-neutral interfaces.

Frontend:

- React;
- TypeScript;
- Vite;
- React Router or equivalent SPA routing;
- functional accessible styling; no product-polish requirement in V1.

Runtime:

- Docker Compose;
- backend, frontend, PostgreSQL;
- optional one-shot ingestion command/container profile;
- no cloud dependency for acceptance.

## Logical modules

### `auth`

Operator login, password verification, operator session/JWT, role authorization.

### `anonymous_access`

Issues opaque per-conversation customer token, validates token scope, never creates a persistent customer identity in V1.

### `conversations`

Conversation lifecycle, messages, queue states, assignment, active-capacity enforcement, close behavior.

### `autonomy`

V1 global mode N1/N2 and per-conversation effective mode. `Take over` can only reduce N2 -> N1. There is no V1 operation that raises a conversation above the configured global mode.

### `knowledge`

Canonical document/chunk storage, ingestion adapters, embeddings, vector retrieval, source exposure policy.

### `rag`

Retrieval orchestration and grounding context construction. Supports two strategies:

- administrative Q&A flat record retrieval;
- clinical child-vector retrieval + parent-context expansion.

### `ai`

Draft generation/regeneration, abstention, model metadata, token/latency metadata. Never sends messages to customers.

### `operator_workspace`

Queue/list, claim/release/close, max-four active capacity, selected conversation, manual send, AI draft actions, manual knowledge search, take-over action.

### `audit`

Append-only operational event store/query.

## Dependency rule

```text
web UI / future channel adapter
           |
           v
FastAPI transport/controllers
           |
           v
application services
     |       |       |
     v       v       v
domain    AI port   RAG port
policies     |       |
             v       v
        provider   pgvector
        adapter    adapter
             \       /
              v     v
             PostgreSQL
```

Domain/application code must not depend on React components, HTTP request objects, or OpenAI SDK response types.

## Anonymous per-tab sessions

V1 must support six independent customer simulations in tabs of a single browser. A normal shared cookie would collapse tabs onto one anonymous identity. Therefore:

1. `POST /public/conversations` creates a conversation and returns an opaque customer access token once.
2. Frontend stores it in that tab's `sessionStorage`.
3. Customer requests present that token in an authorization header.
4. Backend stores only a secure hash/digest of the token.
5. Closing the tab/browser removes browser access to the token; V1 provides no recovery.

The token grants access only to the associated conversation.

## Queue/capacity model

Conversation status:

- `WAITING`: not actively assigned;
- `ACTIVE`: assigned to one operator;
- `CLOSED`: terminal.

An operator may have at most 4 `ACTIVE` conversations. Claiming a fifth returns a domain conflict. In the acceptance scenario, six conversations exist; four are claimed; two remain `WAITING`.

No automatic distribution is implemented in V1.

## N1 / N2 behavior

### Global N1

No automatic draft generation. Operator manually writes messages. If `N1_ASSISTIVE_SEARCH_ENABLED=true`, operator may invoke a search tool that returns evidence only.

### Global N2

Operator may obtain AI drafts grounded in RAG. Customer messages do not wait for AI generation before being persisted/acknowledged. The operator workspace can trigger draft generation for the latest unanswered customer message when selected/opened.

This avoids introducing a durable async job system into V1 while keeping the copilot experience functional.

### Take over

When global mode is N2, operator can take over a conversation. `effective_mode` becomes N1 until conversation close. Existing AI drafts remain audit records but no new automatic/copilot draft is produced unless explicitly allowed by future versions.

## Knowledge ingestion

No ingestion UI.

V1 exposes a CLI/application command with idempotent/upsert semantics. Inputs are mapped into canonical `KnowledgeDocument` and `KnowledgeChunk` records.

- Administrative Q&A: searchable text should combine normalized question + answer; answer is grounding content.
- Clinical parent-child: only child records are vector-indexed; retrieval expands each selected child to its parent context.

See `docs/architecture/KNOWLEDGE_INGESTION.md` and `RAG_DESIGN.md`.

## Customer-visible citations

Every retrieval hit is operator-visible.

Only evidence with `customer_citation_allowed=true` can be attached to a customer-visible message. Clinical parent-source references default to allowed; administrative Q&A defaults to not allowed.

The authorization/exposure rule is enforced server-side, not by the frontend.

## Event architecture

State is persisted transactionally in normal relational tables. Audit events record facts. This is **not event sourcing**.
