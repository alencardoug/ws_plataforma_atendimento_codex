# Implementation Plan: V1 Assisted Customer Service

## 1. Technical summary

Evolve the existing local Docker Compose repository into a V1 modular monolith:

- React/TypeScript/Vite SPA with `/customer` and `/operator` surfaces;
- FastAPI backend with explicit domain/application modules;
- PostgreSQL 17 + pgvector;
- OpenAI generation/embedding adapters behind interfaces;
- offline ingestion CLI that adopts the existing `content.*` corpus in place;
- pytest + frontend unit/component + E2E test stack.

The repository is not greenfield. `app/main.py`, raw `db/init/*.sql`, and the
`scheduling`/`identity`/`billing` demo predate this feature. V1 preserves those
files as historical/preparatory assets, but the V1 runtime must not expose the
legacy scheduling/payment/CPF endpoints. The existing clinical and Q&A content
is the source corpus and must not be copied into a parallel knowledge store.

## 2. Module boundaries

```text
app/
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

Use SQLAlchemy models + Alembic migrations. Keep `app/` as the backend project
root and retain the repository's pip/requirements workflow unless a later,
analyzed need justifies changing package managers. A Poetry conversion has no
V1 requirement and would add migration work without product value.

The existing `db/init/001_schema.sql` through `005_lifecycle.sql` are legacy
bootstrap files that may already have been applied. Do not edit or treat them as
the V1 migration history. Introduce Alembic with two verified paths:

- empty database: establish/adopt the existing content baseline, then apply V1
  revisions;
- existing legacy database: stamp only after schema preflight proves the
  expected baseline, then apply the same forward-only V1 revisions.

New V1 conversational tables should live in an explicit service schema (for
example `customer_service`) to avoid collisions with the existing legacy
schemas. Existing `content.documents`, `content.chunks`, and
`content.qa_entries` remain the canonical knowledge tables and are evolved by
forward migrations rather than duplicated as `knowledge_*` tables.

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

The offline `customer_care.auth.seed_operator` command is the only V1 operator
provisioning path. Backend/Compose startup must not create accounts from
environment credentials. In particular, `LOGIN_OPERATOR_USERNAME` and
`LOGIN_OPERATOR_PASSWORD` are not supported settings: keeping a reusable
plaintext login password in the backend process environment would unnecessarily
broaden secret exposure. Compose must explicitly allowlist supported backend
settings rather than forward every local `.env` entry. The seed command receives
the plaintext password only for that one-shot invocation, persists an Argon2
hash, normalizes email, and upserts by normalized email so rerunning it
updates/reactivates the same account.

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
2. accept final text + optional source_generation_id + selected retrieval-hit IDs as citation candidates;
3. validate every customer citation exposure server-side;
4. create operator Message;
5. record generation provenance and edited/accepted status;
6. audit send + draft accepted/edited;
7. return customer-visible DTO.

Message text is plain text. Persisted `\\n` line breaks must be rendered as line
breaks in both customer and operator message histories; rendering remains text-only
and must not interpret message content as HTML.

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

The source formats are already fixed and versioned:

- administrative: `documents/qa/qa-catalog.jsonl` and existing
  `content.qa_entries` (`qa_id` is the stable external ID);
- clinical parents: `documents/catalog.jsonl` plus each referenced Markdown
  file (`document_id` is the stable parent ID);
- clinical children: existing/generated `content.chunks`
  (`chunk_id`, `parent_document_id`).

The current parent-child relation is `content.documents.document_id` ->
`content.chunks.parent_document_id`; it is already the V1 hierarchy. Do not
synthesize duplicate `PARENT` chunk rows. During ingestion, parse and validate
the Markdown front matter/body, persist a canonical parent-body snapshot and
content hash on `content.documents`, then embed only Q&A and child rows. A
missing Markdown file, mismatched document ID, or orphan child fails validation.

Add the minimum forward-migrated fields needed for V1 traceability and policy:
parent body/hash, active state, citation exposure, and embedding
provider/model/dimension/hash/timestamp on searchable records. Preserve the
existing `vector(1536)` columns and HNSW indexes only if the configured model is
pinned to 1536 dimensions; otherwise require an explicit migration and full
re-embedding.

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

For `ANSWER`, `draft_text` is exclusively the concise, customer-ready reply:
normally one to three short sentences, expanded only when the grounded facts
need it. It has no explanatory preamble, operator instruction, source/citation
metadata, retrieval score, or copied evidence/chunk text. Simple greetings
receive a simple natural greeting. The provider receives the versioned prompt
content used to derive the persisted prompt version; the evidence projection
remains a separate operator-only field.

Generation strategy follows the highest-ranked retrieval result. A clinical
child hit already has its parent expanded in `Evidence.content`; use that parent
document verbatim as the draft so the operator can explicitly send the complete
approved document. For an administrative Q&A hit, pass only administrative Q&A
evidence to the LLM and require it to answer the latest customer request rather
than reproduce retrieval text. With no evidence, permit a brief general answer
or clarification request only; clinical and organization-specific claims still
require evidence and otherwise abstain.

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

Manual evidence search remains evidence-only in V1: it sends the text entered
in the manual-search field and displays each returned evidence item's title,
full content, and matching child excerpt when present. It does not alter the
separate N2 draft-generation retrieval query or select evidence for generation;
that workflow is deferred to V2.

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

- working backend/frontend/db compose stack using PostgreSQL 17 + pgvector;
- migrations;
- seed command;
- ingestion command and demo corpus mapping;
- OpenAPI implementation;
- tests;
- `.env.example` with both retained database variables and every V1 setting;
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
