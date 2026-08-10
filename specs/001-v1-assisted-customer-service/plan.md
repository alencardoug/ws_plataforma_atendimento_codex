# Implementation Plan: V1 Assisted Customer Service

## 1. Technical summary

Implement a local Docker Compose modular monolith:

- React/TypeScript/Vite SPA with `/customer` and `/operator` surfaces;
- FastAPI backend with explicit domain/application modules;
- PostgreSQL 17 + pgvector;
- OpenAI generation/embedding adapters behind interfaces;
- offline ingestion CLI;
- pytest + frontend unit/component + E2E test stack.

## 2. Module boundaries

```text
backend/app/
  auth/
  anonymous_access/
  conversations/
  autonomy/
  operator_workspace/
  knowledge/
  rag/
  ai/
  audit/
  shared/
  infrastructure/
```

Each module should expose application services and repository/provider ports where useful. Avoid generic abstraction layers that hide behavior.

## 3. Persistence strategy

Use SQLAlchemy models + Alembic migrations.

Transactions:

- create conversation + token digest atomically;
- claim capacity check + active assignment atomically;
- operator send + provenance + citations + audit event atomically where practical;
- ingestion upsert operations in bounded transactions.

Use PostgreSQL locking/advisory/transaction semantics sufficient to prevent concurrent capacity overflow. Do not solve capacity with frontend-only counting.

## 4. Anonymous access

Token generation:

- cryptographically secure random bytes;
- URL/header-safe encoding;
- returned once on create;
- backend stores HMAC/secure digest using server-side pepper or strong one-way digest strategy;
- token not embedded in URL;
- frontend stores in `sessionStorage` per tab.

Public request header may use `Authorization: Bearer <conversation-token>` or an explicit conversation token header. The OpenAPI contract is canonical.

## 5. Operator auth

Seed one or more synthetic operator accounts through a seed command.

Use strong password hashing. V1 may use stateless signed access tokens or secure server sessions; keep implementation simple and documented.

## 6. Queue and assignment

Queue is database-backed.

Conversation creation => `WAITING`.

Operator claim:

1. authenticate operator;
2. start DB transaction;
3. lock/check current active assignment count;
4. if count >= configured max, return `409 CAPACITY_EXCEEDED`;
5. verify target conversation is waiting/unassigned;
6. create active assignment + set status ACTIVE;
7. commit and emit audit event.

No push routing.

## 7. Messaging

Customer send:

1. validate conversation token;
2. require not CLOSED;
3. create customer Message;
4. audit receipt;
5. return quickly; do not synchronously require LLM generation.

Operator send:

1. validate operator assignment/authorization;
2. accept final text + optional source_generation_id + selected citation source IDs;
3. validate every customer citation exposure server-side;
4. create operator Message;
5. record generation provenance and edited/accepted status;
6. audit send + draft accepted/edited;
7. return customer-visible DTO.

## 8. N1/N2

Global configuration loaded centrally.

Conversation stores `initial_mode` and `effective_mode` snapshot to make audit/replay understandable.

N1:

- no draft endpoint/action allowed;
- manual search only if flag enabled.

N2:

- draft generation allowed only for assigned active conversation and eligible customer message;
- AI generation never sends;
- take-over changes effective mode to N1, then draft endpoint returns conflict/forbidden for that conversation.

## 9. Ingestion

Implement canonical adapters for:

- administrative Q&A;
- clinical parent-child.

Input format should be explicit JSONL/JSON/CSV mapping or adapter to existing prepared data. If source schema already exists in the implementation repository, write an adapter that maps it into the canonical DTO rather than rewriting source data.

Use content hashes and external IDs for idempotency.

Embeddings:

- model configured externally;
- persist embedding model/dimension metadata;
- pgvector column/index dimension must be consistent with the configured V1 embedding model;
- changing dimension is a migration/re-embedding operation.

## 10. Retrieval

Administrative:

- embed query;
- vector search Q&A records;
- return top-k.

Clinical:

- vector search child chunks;
- fetch/expand parents;
- dedupe parents while retaining child hit provenance.

Mixed query:

- simplest acceptable V1 strategy is querying both searchable families and combining/ranking results using comparable distance/score;
- do not add a learned classifier/router unless evaluation proves necessary.

## 11. AI generation

Define provider-neutral interface:

```text
GenerationRequest(conversation_context, evidence, prompt_version, model_config)
GenerationResult(status, draft_text, reason_code, used_source_ids, usage, latency)
```

Persist result before returning to operator UI.

Structured output validation is preferred to parsing free-form status.

Provider failure becomes an application error shown to operator without blocking manual response.

## 12. Frontend

### Customer

- start conversation;
- tab-local session token;
- message list;
- send box;
- waiting/active informational status;
- render final operator messages;
- render only approved attached clinical citations;
- close conversation.

No customer account UI.

V1 real-time refresh strategy: simple HTTP polling/refetch is sufficient (for example ~2 seconds while the relevant view is open). Do not introduce WebSocket/SSE solely for V1.

### Operator

Functional layout:

```text
[ waiting + active list ] [ selected conversation ] [ AI/evidence panel ]
```

Actions:

- claim;
- manual send;
- generate/use draft in N2;
- edit;
- regenerate;
- search evidence;
- take over;
- close.

Show effective N1/N2 badge prominently.

## 13. Audit

Central audit service receives typed event commands from application services. Persist JSON metadata with stable schema conventions.

Audit must not become a second business-logic path.

## 14. Testing implementation

Use real PostgreSQL/pgvector for integration tests, preferably ephemeral test container or isolated test database.

AI provider tests use deterministic fake adapter except a separately marked optional smoke test against real provider.

RAG integration tests can use deterministic embeddings/fake embedding adapter for logic and an optional real embedding smoke test. Acceptance demo uses configured real provider.

E2E uses browser automation and must explicitly exercise multiple tabs/contexts for anonymous-session isolation.

## 15. Performance

No premature optimization. Capture timings around embedding/retrieval/generation. Target <=10s for normal operator draft flow in demo conditions.

## 16. Deliverables

- working backend/frontend/db compose stack;
- migrations;
- seed command;
- ingestion command and demo corpus mapping;
- OpenAPI implementation;
- tests;
- `.env.example`;
- quickstart;
- acceptance evidence/log.

## 17. Prohibited shortcuts

- storing anonymous raw token in DB;
- using conversation UUID alone as customer authorization;
- representing AI draft as a Message before operator send;
- frontend-only capacity enforcement;
- customer-side citation filtering only;
- plaintext operator passwords;
- embedding ingestion performed manually in SQL as the only supported path;
- adding N3/N4 behavior to satisfy future roadmap.
