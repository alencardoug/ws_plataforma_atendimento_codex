# Test Plan — V1

Canonical acceptance scenarios are in `specs/001-v1-assisted-customer-service/acceptance.md`.

## Test layers

### Unit

- maturity/effective mode policy;
- take-over N2 -> N1;
- citation exposure policy;
- abstention decision mapping;
- active capacity rule;
- token hashing/validation;
- parent-child context expansion.

### Integration

- PostgreSQL repositories;
- pgvector retrieval;
- migration correctness;
- claim capacity with concurrent attempts;
- AI generation persistence;
- message send provenance;
- audit event persistence;
- ingestion idempotency.

### API/contract

OpenAPI response/status behavior including authorization failures and capacity conflicts.

### Frontend

- customer tab creates isolated anonymous session;
- operator queue/status display;
- N1 manual flow;
- N2 draft/edit/send;
- take-over control;
- internal vs customer-visible citations.

### End-to-end

Critical demo:

1. start full stack with Docker Compose;
2. login as operator;
3. open six customer tabs;
4. create six independent anonymous conversations;
5. send a message from each;
6. operator sees six waiting conversations;
7. claim four;
8. fifth claim attempt is rejected and two remain waiting;
9. execute an N2 RAG draft for an active conversation;
10. verify customer cannot see draft;
11. operator accepts or edits and explicitly sends;
12. customer receives final response;
13. take over another N2 conversation and verify effective mode N1;
14. verify no AI draft is generated/available through normal N2 action after take-over;
15. switch/test global N1 and manual knowledge search when enabled;
16. verify required audit events.

## Critical negative tests

- direct creation of customer-visible AI message is impossible;
- customer token cannot retrieve AI generation;
- admin Q&A internal source cannot be exposed as customer citation;
- wrong conversation token cannot access another conversation;
- operator cannot exceed four active conversations;
- insufficient evidence does not produce invented grounded claim;
- failed AI provider still permits manual operator send.

## V1 performance acceptance

- normal RAG+generation operator request target <=10 seconds in demo conditions, excluding external provider incidents;
- one operator can maintain four active conversations;
- six simulated customer sessions can coexist, with two waiting when four are active.
