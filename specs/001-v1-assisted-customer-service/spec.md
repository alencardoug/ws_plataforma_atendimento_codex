# Feature Specification: V1 Assisted Customer Service

**Feature ID:** `001-v1-assisted-customer-service`  
**Status:** Ready for implementation (repository-aware analyze pass complete)
**Created:** 2026-08-10  
**Scope:** V1 only

## 1. Problem statement

Build the smallest complete version of an AI-assisted Cancer Center customer-service application that is demonstrably useful, safe enough for synthetic/demo use, auditable, and extensible without implementing future autonomy complexity.

The V1 must support anonymous customer conversations and an authenticated operator. It must demonstrate manual service (N1), AI copilot service (N2), a real RAG built from currently non-vectorized knowledge, a basic manual queue, and traceability from customer question to evidence/draft/final human-sent answer.

V1 is not a production clinical system and does not use real patient data.

## 2. Goals

### G1 — End-to-end existence

A user can run the system locally, open a customer chat, send a question, have an operator respond, and inspect the complete persisted/audited workflow.

### G2 — Safe N2 copilot

AI assists the operator with grounded drafts but cannot directly send a customer-visible message.

### G3 — Real retrieval

V1 creates embeddings and performs vector retrieval from two knowledge families: flat administrative Q&A and clinical parent-child content.

### G4 — Basic operational realism

A single operator can manually manage four active conversations while additional conversations remain waiting.

### G5 — Future-compatible foundations

Conversation, channel, AI-provider, audit, and knowledge models must not force later Telegram or autonomy redesign, while future features remain out of V1 behavior.

## 3. Actors

### A1 — Anonymous Customer

A browser-tab-local customer with no account. Can create one conversation, send/read messages for that conversation, and close it while the tab retains the opaque token.

### A2 — Operator

Authenticated call-center operator. Can view queue, claim up to four conversations, manually send messages, use N1 assistive search if enabled, use N2 AI draft tools, and take over an N2 conversation into N1.

### A3 — Runtime Configuration

Non-UI deployment configuration defining global maturity mode and feature flags for V1.

## 4. Definitions

- **Global mode:** deployment-wide `N1` or `N2` configuration.
- **Effective mode:** mode currently governing one conversation. Starts at global mode and may be reduced from N2 to N1 by `Take over`.
- **AI draft:** internal generation artifact visible only to operator.
- **Final message:** customer-visible operator message created only through explicit operator send action.
- **Waiting conversation:** not currently assigned active to an operator.
- **Active conversation:** currently assigned to an operator and counts toward capacity.
- **Abstention:** structured AI outcome declaring insufficient/conflicting/out-of-scope evidence rather than fabricating an answer.

## 5. User stories and acceptance scenarios

### US1 [P1] — Anonymous customer starts and uses a conversation

As an anonymous customer, I want to start a chat without creating an account so I can ask a question immediately.

**Acceptance scenarios**

1. Given a new browser tab with no conversation token, when the customer starts a conversation, then the backend creates a new `WAITING` conversation and returns an opaque access token.
2. The frontend stores the token in the tab's `sessionStorage`, not a shared persistent identity cookie.
3. Given six separate tabs, each tab can create a distinct conversation and send messages independently.
4. A customer token can read/send only within its bound conversation.
5. Closing the V1 tab/session provides no recovery workflow.

### US2 [P1] — Operator authenticates

As an operator, I want to log in so operator-only actions are protected.

**Acceptance scenarios**

1. Valid seeded credentials create an authenticated operator session/token.
2. Invalid credentials fail without revealing password details.
3. Customer token cannot call operator endpoints.
4. Operator password is stored only as a strong hash.

### US3 [P1] — Operator manually claims conversations with capacity

As an operator, I want to see waiting conversations and claim up to four so I can manage concurrent customer service.

**Acceptance scenarios**

1. Operator can list waiting and own active conversations.
2. Claiming a waiting conversation makes it `ACTIVE` and assigns it to the operator.
3. Operator may have at most 4 active conversations with the V1 acceptance configuration.
4. Attempting to claim a fifth returns a conflict and does not modify the conversation.
5. With six waiting conversations, after four successful claims, exactly four are active and two remain waiting.
6. Capacity enforcement is safe under concurrent claim attempts.

### US4 [P1] — N1 manual service

As an operator in N1, I want to answer the customer manually without automatic AI generation.

**Acceptance scenarios**

1. In global/effective N1, customer message is persisted and visible to the assigned operator.
2. No AI draft is automatically generated as part of receiving the customer message.
3. Operator can type and explicitly send a final message.
4. Customer sees only the final operator message.
5. AI/provider outage does not prevent this manual send flow.

### US5 [P1] — N1 optional assistive knowledge search

As an operator in N1, I want to manually search approved knowledge when the feature flag is enabled.

**Acceptance scenarios**

1. If `N1_ASSISTIVE_SEARCH_ENABLED=false`, the N1 assistive search action is unavailable/forbidden.
2. If enabled, operator can submit a query and receive ranked evidence only.
3. Manual search does not generate a customer response.
4. Search action and retrieval run are audited.

### US6 [P1] — N2 grounded copilot draft

As an operator in N2, I want a grounded draft for the customer's latest unanswered message so I can respond faster without surrendering final control.

**Acceptance scenarios**

1. Operator selects/opens an active N2 conversation containing a customer message and can request/trigger a draft for that message.
2. System performs RAG and persists the retrieval run/hits.
3. System generates and persists an AI draft linked to triggering message + retrieval run + prompt/model configuration.
4. Customer cannot access the draft or internal evidence.
5. Operator can inspect draft and evidence.
6. A draft is never automatically converted to a customer-visible message.
7. If AI/RAG fails, operator can still manually send a response.

### US7 [P1] — Operator accepts or edits and explicitly sends

As an operator, I want to use or modify an AI draft and explicitly send the final content.

**Acceptance scenarios**

1. Operator can accept/use a selected draft as final text.
2. Operator can edit text before send.
3. Send creates a new customer-visible `Message` authored by operator.
4. Message may reference the source `AIGeneration` for provenance.
5. Audit distinguishes accepted unchanged vs edited final text.
6. No API operation exists that sends an `AIGeneration` directly without operator authorization/action.

### US8 [P2] — Operator regenerates a draft

As an operator in effective N2, I want another grounded draft when the first is not satisfactory.

**Acceptance scenarios**

1. Regenerate creates a new generation record and preserves the old record.
2. New record links to prior generation lineage.
3. All grounding/abstention rules still apply.
4. Regeneration is audited.

### US9 [P1] — Operator takes over N2 conversation

As an operator, I want to take over an N2 conversation so I can continue entirely manually when necessary.

**Acceptance scenarios**

1. In effective N2, operator can invoke `Take over`.
2. Conversation effective mode changes N2 -> N1.
3. Transition is persisted and audited with operator identity.
4. Conversation remains N1 until closed in V1.
5. Existing drafts remain immutable historical artifacts.
6. Subsequent normal N2 draft action is rejected/disabled for that conversation.
7. Manual send and optional N1 search remain available according to feature flag.

### US10 [P1] — Administrative Q&A ingestion and retrieval

As the application, I need administrative Q&A embedded/indexed so operators can ground service answers in approved organizational information.

**Acceptance scenarios**

1. Offline ingestion accepts canonical administrative Q&A records.
2. Re-run is idempotent for unchanged content.
3. New/changed records are embedded and searchable.
4. Retrieval returns answer/source metadata to operator.
5. Administrative source details have `customer_citation_allowed=false` by default.
6. Administrative Q&A does not require or fabricate parent-child hierarchy.

### US11 [P1] — Clinical parent-child ingestion and retrieval

As the application, I need child-level semantic retrieval with parent context so clinical informational answers use the prepared hierarchy correctly.

**Acceptance scenarios**

1. Offline ingestion accepts parent and child records with stable external IDs.
2. Child referencing missing parent fails validation.
3. Child content is embedded/searchable.
4. Retrieval selects child hits and expands to parent context for generation.
5. Child->parent relation is traceable in retrieval hits.
6. Approved clinical parent source projection can be customer-visible.

### US12 [P1] — Evidence-based abstention

As an operator, I want the AI to say it lacks sufficient evidence rather than fabricate organization-specific information.

**Acceptance scenarios**

1. Generation result has structured `ANSWER|ABSTAIN` status.
2. Insufficient/conflicting/out-of-scope evidence can produce `ABSTAIN`.
3. Abstention draft is visible to operator, not sent automatically.
4. Operator remains able to answer manually.
5. No automatic specialist escalation is implemented in V1.

### US13 [P1] — Customer-visible clinical citations only

As a customer, I want approved clinical references when they support the final answer, without exposing internal administrative source metadata.

**Acceptance scenarios**

1. Operator sees all retrieval hits.
2. Customer response DTO includes only citations attached to final message whose source is `customer_citation_allowed=true`.
3. Administrative Q&A source cannot be attached/exposed to customer even if model requests it.
4. Clinical citation projection contains approved fields only, not internal IDs/scores/storage paths.

### US14 [P1] — Durable audit trail

As the system owner, I want critical facts recorded so future quality/governance metrics are possible.

**Acceptance scenarios**

1. Required event catalog is persisted.
2. Events are append-only through application APIs.
3. Events use stable IDs/correlation identifiers and minimal metadata.
4. Full message bodies are not duplicated into event payloads by default.

## 6. Functional requirements

### Conversation / anonymous access

- **FR-001:** System shall create an anonymous conversation without customer account credentials.
- **FR-002:** Creation shall issue an unguessable access token scoped to exactly one conversation.
- **FR-003:** Backend shall persist only a secure digest/hash of the anonymous token.
- **FR-004:** Frontend shall store raw anonymous token in per-tab `sessionStorage`.
- **FR-005:** Public conversation operations shall validate token binding for every read/write.
- **FR-006:** V1 shall not implement cross-session recovery for anonymous customers.
- **FR-007:** Conversation statuses shall include `WAITING`, `ACTIVE`, `CLOSED`.

### Operator / queue

- **FR-010:** Operator login shall be required for operator endpoints.
- **FR-011:** Operator passwords shall be hashed.
- **FR-012:** Operator shall list waiting and own active conversations.
- **FR-013:** Operator shall manually claim a waiting conversation.
- **FR-014:** Maximum active conversations per operator shall be configurable; V1 acceptance value = 4.
- **FR-015:** Capacity check shall prevent a fifth active assignment and be safe against race conditions.
- **FR-016:** Six simultaneous anonymous conversations shall coexist for acceptance testing.

### Maturity / take-over

- **FR-020:** Global maturity mode shall be configured as exactly `N1` or `N2` outside the V1 UI.
- **FR-021:** New conversation effective mode shall initialize from global mode.
- **FR-022:** Operator UI shall display current effective mode.
- **FR-023:** In N2, operator may `Take over`, setting effective mode to N1 until conversation close.
- **FR-024:** V1 shall have no action that increases a conversation above configured/effective mode.

### Messaging

- **FR-030:** Customer messages shall persist before AI assistance is required.
- **FR-031:** Operator may manually send customer-visible messages in N1 and N2.
- **FR-032:** AI draft shall be a separate entity from `Message`.
- **FR-033:** Only explicit authenticated operator send shall create an operator customer-visible message.
- **FR-034:** Final message may reference one source AI generation for provenance.
- **FR-035:** Customer API shall never return internal AI draft text or internal evidence.

### N1 assistive search

- **FR-040:** N1 assistive knowledge search shall be controlled by deployment flag.
- **FR-041:** Enabled N1 search returns evidence only, never generated final answer.
- **FR-042:** Disabled N1 search shall be forbidden/hidden.

### N2 AI draft

- **FR-050:** Effective N2 operator shall be able to request a grounded draft for a customer message.
- **FR-051:** Draft generation shall persist retrieval run before/with generation traceability.
- **FR-052:** Generation shall persist prompt version, model/provider metadata, latency and usage metadata when available.
- **FR-053:** Operator shall be able to accept/use, edit, regenerate, search evidence, and send.
- **FR-054:** Regeneration shall create a new immutable generation with lineage.
- **FR-055:** Effective N1 conversation after take-over shall reject normal N2 draft generation.

### Knowledge ingestion

- **FR-060:** V1 shall include offline/CLI ingestion; no ingestion UI required.
- **FR-061:** Ingestion shall support flat administrative Q&A.
- **FR-062:** Ingestion shall support clinical parent-child records.
- **FR-063:** Ingestion shall be idempotent for unchanged records.
- **FR-064:** Changed searchable content shall be re-embedded.
- **FR-065:** Ingestion shall persist source/content hash and embedding metadata.
- **FR-066:** Invalid child-parent references shall fail validation.

### Retrieval

- **FR-070:** Administrative Q&A retrieval shall search flat vector records without parent expansion.
- **FR-071:** Clinical retrieval shall vector-search child chunks and expand selected hits to parent context.
- **FR-072:** Retrieval shall persist hit rank/score and hierarchy references sufficient for traceability.
- **FR-073:** Operator shall be able to inspect retrieved evidence.
- **FR-074:** RAG shall not require a separate vector database from PostgreSQL/pgvector in V1.

### Grounding / abstention

- **FR-080:** AI draft shall use conversation context + supplied evidence for organization-specific claims.
- **FR-081:** Generation result shall have structured `ANSWER|ABSTAIN` status.
- **FR-082:** `ABSTAIN` shall support at least insufficient evidence, conflicting evidence, out-of-scope, and retrieval failure reason classes.
- **FR-083:** V1 shall not automatically escalate to clinical staff/specialist.
- **FR-084:** AI/RAG failure shall leave manual operator send available.

### Citation exposure

- **FR-090:** Knowledge evidence shall carry `customer_citation_allowed` policy.
- **FR-091:** Administrative Q&A default shall be non-exposable.
- **FR-092:** Approved clinical parent/source projection may be exposable.
- **FR-093:** Server shall filter customer-visible citations; frontend/model output cannot override exposure.
- **FR-094:** Customer citation projection shall exclude internal score, DB IDs, storage paths, and unapproved URLs.

### Audit

- **FR-100:** System shall persist events in `docs/architecture/EVENT_CATALOG.md` applicable to executed flows.
- **FR-101:** Application APIs shall not update/delete audit events.
- **FR-102:** Operator send event shall identify whether an AI draft was accepted unchanged or modified.
- **FR-103:** Take-over shall emit a dedicated audit event.
- **FR-104:** Ingestion shall emit started/completed/failed events.

## 7. Non-functional requirements

- **NFR-001 Performance:** Normal operator-requested RAG + generation target <=10 seconds in demo conditions, excluding external provider incident.
- **NFR-002 Concurrency:** Six customer sessions can coexist; one operator can hold four active conversations while two wait.
- **NFR-003 Resilience:** AI/RAG failure does not prevent manual message send.
- **NFR-004 Persistence:** Restart shall not lose persisted conversations/messages/knowledge/audit records.
- **NFR-005 Security:** Secrets never committed; operator authorization server-side; anonymous token scoped to one conversation.
- **NFR-006 Privacy:** Synthetic/demo data only; message bodies not logged at INFO by default.
- **NFR-007 Traceability:** Every AI draft links to evidence/model/prompt/triggering message.
- **NFR-008 Testability:** Critical negative invariants have automated tests.
- **NFR-009 Architecture:** Modular monolith; no distributed infrastructure unless spec changes.
- **NFR-010 Channel boundary:** Core application logic contains no requirement that prevents a future Telegram adapter.
- **NFR-011 Accessibility:** Functional customer/operator UIs use semantic controls and keyboard-usable core actions.

## 8. Configuration requirements

At minimum:

```text
GLOBAL_MATURITY_MODE=N1|N2
N1_ASSISTIVE_SEARCH_ENABLED=true|false
OPERATOR_MAX_ACTIVE_CONVERSATIONS=4
DATABASE_URL=...
OPENAI_API_KEY=...
AI_GENERATION_MODEL=...
AI_EMBEDDING_MODEL=...
ANONYMOUS_TOKEN_PEPPER=...
OPERATOR_AUTH_SECRET=...
```

Exact variable names may differ if plan/code/docs stay synchronized.

## 9. Data requirements

V1 persists:

- operator users;
- anonymous conversations and token digest;
- assignments;
- messages;
- AI generations;
- retrieval runs/hits;
- knowledge documents/chunks and embeddings;
- final-message citations;
- audit events.

V1 does not persist a customer person/account/profile.

## 10. Explicit out of scope

- customer account creation/login;
- CPF/password session recovery;
- saved appointment continuity data;
- Telegram;
- streaming;
- supervisor/manager/AI Ops UI;
- N3/N4;
- autonomous AI-to-customer send;
- automatic queue distribution;
- dynamic wait-time estimate;
- specialist escalation workflow;
- autonomous appointment scheduling/rescheduling/cancellation;
- GCP deployment acceptance;
- real patient data;
- medical diagnosis/treatment decision support;
- document upload UI;
- LLM-based autonomous policy changes;
- automatic autonomy increase.

## 11. V1 DONE definition

V1 is complete only when:

1. `docker compose up --build` starts the full local application from documented prerequisites;
2. migrations and demo seed/ingestion are reproducible;
3. operator login succeeds;
4. six independent customer tabs can create/send messages;
5. operator sees six waiting conversations;
6. operator can claim four and cannot claim a fifth; two remain waiting;
7. N2 RAG retrieves evidence and creates an internal draft;
8. customer cannot see draft/internal evidence;
9. operator can accept or edit and explicitly send;
10. customer receives final message;
11. clinical citation exposure works and administrative citation leakage is blocked;
12. operator can take over N2 -> N1 and continue manually;
13. N1 assistive search works only when enabled;
14. abstention works for an unsupported query;
15. AI/RAG failure path still allows manual send;
16. required audit events exist;
17. automated test suite passes;
18. spec-to-code convergence finds no material V1 mismatch.
