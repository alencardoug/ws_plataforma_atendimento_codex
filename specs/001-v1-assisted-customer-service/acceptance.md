# V1 Acceptance Protocol

This is the executable definition of DONE, supplementary to `spec.md`.

## A. Environment

- [ ] Fresh/known local environment can start with documented Docker Compose commands.
- [ ] PostgreSQL 17 + pgvector is healthy.
- [ ] Migrations apply from empty database.
- [ ] Synthetic operator seed is reproducible.
- [ ] Administrative demo Q&A ingestion succeeds.
- [ ] Clinical parent-child demo ingestion succeeds.
- [ ] Re-running ingestion does not duplicate unchanged records.

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

## D. Take-over scenario

1. In another active N2 conversation, generate/observe a draft if desired.
2. Click `Take over`.
3. Verify effective mode badge becomes N1.
4. Verify transition persisted/audited.
5. Verify normal N2 draft generation now fails/is disabled.
6. Send manual operator response successfully.

## E. N1 scenario

1. Run/test global N1.
2. Receive customer message.
3. Verify no AI draft is created automatically.
4. Send manual response.
5. Enable N1 assistive search and verify evidence-only search works.
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
