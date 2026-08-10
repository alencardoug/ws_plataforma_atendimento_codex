# Threat Model — V1

## Assets

- operator credentials;
- anonymous conversation access tokens;
- conversation content;
- knowledge corpus;
- AI provider key;
- internal retrieval/source metadata;
- audit trail.

## Trust boundaries

1. browser customer -> backend;
2. browser operator -> backend;
3. backend -> PostgreSQL;
4. backend -> AI provider;
5. ingestion input -> knowledge store.

## Primary threats and controls

### Anonymous token theft

Threat: attacker reads another anonymous conversation.

Controls: high-entropy token, per-conversation scope, token digest at rest, HTTPS in deployed environments, sessionStorage rather than URL, never log raw token.

### Cross-conversation IDOR

Threat: customer changes conversation UUID.

Control: every public conversation operation verifies token digest + conversation binding, not UUID alone.

### Operator privilege bypass

Control: server-side role checks on all operator endpoints.

### AI direct-send bypass

Threat: code path accidentally publishes generation output.

Controls: generation and Message are separate entities; only operator send service can create `OPERATOR` customer-visible message; negative test; no public/provider callback can send.

### Prompt injection

Threat: customer or retrieved document asks model to reveal internals or ignore constraints.

Controls: model output has no authority to execute send; trusted prompt boundaries; source text clearly delimited; internal metadata excluded from customer output; operator gate in N2.

### Malicious/poisoned knowledge

Controls: ingestion is administrative/offline; source provenance stored; corpus is approved demo content; no customer uploads in V1.

### Citation leakage

Threat: internal administrative source details exposed to customer.

Control: server-side `customer_citation_allowed` rule; customer response DTO contains only approved citation projection.

### Capacity race

Threat: concurrent claims give operator >4 active conversations.

Control: transaction/locking strategy in claim service; integration test with concurrent claim attempts.

### Sensitive-content logs

Control: structured metadata logging, no message bodies by default.
