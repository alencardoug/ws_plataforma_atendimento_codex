# Security Baseline — V1

## Data classification

V1 is a portfolio/demo application and must use synthetic or fictitious customer data only. The architecture still treats free-text conversation content as potentially sensitive.

## Authentication

Operator:

- email + password;
- password stored using a modern password hash (Argon2id preferred, or framework-vetted equivalent);
- server issues an authenticated operator session/token;
- all operator authorization is server-side.
- account provisioning only through the explicit offline seed command;
- no plaintext operator credential retained in backend/Compose runtime
  settings and no account auto-created at application startup.

Anonymous customer:

- no account;
- unguessable random conversation access token;
- token is returned only at conversation creation;
- frontend stores it in per-tab `sessionStorage`;
- backend stores only a secure digest;
- token authorizes one conversation only.

## Authorization

- customer token cannot call operator endpoints;
- operator cannot use a customer token as authorization;
- customer can read/send only within token-bound conversation;
- customer cannot read AI drafts, internal retrieval hits, audit events, or operator-only metadata;
- customer-visible citations must pass server-side exposure policy.

## AI safety invariants

- AI generation is an internal artifact, never an outbound customer message;
- no direct AI-send endpoint;
- prompt injection from knowledge/customer text must not override system/application authorization rules;
- no hidden reasoning persistence;
- abstain when evidence is insufficient rather than inventing unsupported facts;
- RAG failure leaves manual operator flow available.

## Logging

Do not log full message bodies at INFO. Use identifiers, sizes, timings, outcomes, and redacted diagnostic fields. Debug content logging must be off by default and never enabled with real data.

## Secrets

Never commit:

- OpenAI/API keys;
- database credentials;
- JWT/session secrets;
- seed operator plaintext password in source history.

Use `.env` locally, with `.env.example` containing names only.

## Future CPF + password recovery

Not V1.

When implemented, the user experience may ask whether to save essential service data and then use CPF + password to resume a saved profile/session. Technical rules:

- explicit consent before creating a saved profile;
- CPF normalized and protected according to the deployment's privacy/security design;
- password never stored or compared in plaintext;
- password verifier uses strong salted hashing;
- successful CPF + password verification can resume saved state;
- an incorrect password must not reveal whether a CPF exists;
- CPF exists + wrong password must never grant, overwrite, merge, or create a second persisted memory tied to that identity;
- user may continue in a new **anonymous** session with no access/link to existing persisted history;
- saved data must be minimized to service-continuity needs;
- real deployment requires dedicated privacy/security/legal review before enabling personal/health-related data.
