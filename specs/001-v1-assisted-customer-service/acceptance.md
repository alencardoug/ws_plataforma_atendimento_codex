# V1 Acceptance Protocol

This is the executable definition of DONE, supplementary to `spec.md`.

## A. Environment

- [x] Fresh/known local environment can start with documented Docker Compose commands.
- [x] PostgreSQL 17 + pgvector is healthy.
- [x] Migrations apply from empty database.
- [x] Synthetic operator seed is reproducible.
- [x] Operator provisioning has exactly one V1 path: the explicit offline seed
  command; application/Compose startup creates no operator from environment
  credentials.
- [x] Re-seeding the same normalized operator email updates/reactivates exactly
  one account and does not create a duplicate.
- [x] Administrative demo Q&A ingestion succeeds.
- [x] Clinical parent-child demo ingestion succeeds.
- [x] Re-running ingestion does not duplicate unchanged records.

## B. Six-client queue scenario

1. Open operator page and authenticate.
2. Open six customer tabs in one browser.
3. Start a conversation in each tab.
4. Verify six distinct conversation IDs/tokens.
5. Send one message from each customer.
6. Verify operator queue shows six waiting conversations.
7. Claim four.
8. Verify those four are ACTIVE and assigned.
9. Attempt to claim a fifth.
10. Verify `409 CAPACITY_EXCEEDED` (or semantically equivalent) and no inconsistent assignment.
11. Verify exactly two remain waiting.

Pass condition: independent tabs + durable queue + max-four rule.

## C. N2 copilot scenario

1. Run with global N2.
2. Select one active conversation.
3. Request/trigger grounded draft for latest customer message.
4. Verify retrieval run + hits exist.
5. Verify operator sees draft + evidence.
6. From customer tab, verify draft/internal evidence is not visible.
7. Accept draft unchanged and send.
8. Verify customer receives final message.
9. Verify final message references generation provenance.
10. Verify audit contains draft generated + accepted + operator sent.

Repeat with operator editing draft before send and verify `ai.draft_edited` semantics.

For a simple `Oi`, verify the generated `draft_text` is a short, natural
greeting. For a RAG-backed question, verify `draft_text` contains only the
customer-ready answer, while source/chunk content remains only in the separate
operator evidence projection.

For a question whose highest-ranked result is clinical parent-child evidence,
verify `draft_text` is the complete parent document and `Usar documento completo`
places that complete text in the operator send box. For an administrative Q&A result,
verify the LLM answers the customer's request from the Q&A content rather than
returning the retrieved record verbatim. With no evidence, verify the response
is brief and general/clarifying and contains no unsupported clinical or
organization-specific fact.

## D. Take-over scenario

1. In another active N2 conversation, generate/observe a draft if desired.
2. Click `Assumir controle`.
3. Verify effective mode badge becomes N1.
4. Verify transition persisted/audited.
5. Verify normal N2 draft generation now fails/is disabled.
6. Send manual operator response successfully.

## E. N1 scenario

1. Run/test global N1.
2. Receive customer message.
3. Verify no AI draft is created automatically.
4. Send manual response.
5. Enable N1 assistive search, enter a distinctive manual query, and verify the
   returned evidence title and full content correspond to that query; it remains
   evidence-only and does not alter draft generation.
6. Disable flag and verify action is unavailable/forbidden.

## F. Dual RAG scenario

### Administrative

- ask a question answerable by admin Q&A;
- verify flat Q&A hit;
- verify operator can inspect evidence;
- verify customer cannot receive internal administrative source citation.

### Clinical parent-child

- ask a question whose relevant child maps to a known parent;
- verify child is vector hit;
- verify parent context is used/available;
- verify child->parent traceability;
- send a final answer with approved clinical citation;
- verify customer sees safe citation projection.

## G. Abstention scenario

Ask an unsupported/out-of-corpus organization-specific question.

- generation returns `ABSTAIN` or equivalent structured status;
- no unsupported factual answer is fabricated;
- operator can manually reply;
- no auto-escalation occurs.

## H. Failure fallback

Simulate/fake generation provider failure.

- operator sees error;
- conversation remains usable;
- operator manual send succeeds.

## I. Security negative checks

- customer A token cannot read customer B conversation;
- customer token cannot access operator route;
- customer cannot fetch AI generation by guessed ID;
- direct AI generation cannot be published without operator send service;
- administrative non-exposable citation rejected;
- raw anonymous token absent from DB/logs;
- plaintext operator password absent from DB.

## J. Quality gates

- backend tests pass;
- frontend tests pass;
- E2E critical flows pass;
- type/lint gates pass;
- OpenAPI matches implementation;
- no material spec/code divergence remains.

## K. Multiline message rendering

1. An operator enters and explicitly sends a response containing at least one
   line break.
2. Verify the customer sees each line separately, in the original order.
3. Verify the operator history presents the same line breaks.

Pass condition: message content remains plain text and intentional line breaks
are not collapsed into spaces on either web surface.

## Execution record — 2026-08-10

All sections A–J passed against local Docker Compose/PostgreSQL 17. Evidence:

- migrations passed both on an empty database and over the legacy bootstrap schema;
- ingestion reconciled 57 clinical parents, 570 children, and 86 flat Q&A records; a second run embedded zero records, while a controlled one-record change re-embedded exactly one record;
- concurrent capacity returned four `200` claims and two `409` conflicts;
- deterministic API smokes covered N1/N2, dual RAG, parent expansion, citations, abstention/provider failure, explicit human send, take-over, security negatives, and append-only audit;
- real-provider smoke used the configured OpenAI embedding/generation adapters and verified grounded draft, abstention normalization, explicit send, and safe citation projection;
- Playwright with local Chrome passed the six independent browser-context N2 scenario and the N1 manual-service/disabled-search scenario;
- backend Ruff, mypy, pytest and frontend ESLint, TypeScript, Vitest, production build, and Playwright gates passed.

Temporary deterministic databases were isolated from the normal Compose database. Synthetic test credentials and corpora only were used.
