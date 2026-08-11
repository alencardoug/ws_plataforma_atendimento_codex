# Decision Register

Canonical design decisions are also captured as ADRs under `adr/`.

| ID | Decision | Status |
|---|---|---|
| D-001 | Modular monolith for V1 | Accepted |
| D-002 | Web customer + operator SPA, React/TypeScript/Vite | Accepted |
| D-003 | Anonymous customer; no V1 account recovery | Accepted |
| D-004 | Per-tab anonymous conversation token in sessionStorage | Accepted |
| D-005 | Operator authenticated; customer anonymous | Accepted |
| D-006 | Global N1/N2 only in V1 | Accepted |
| D-007 | N2 AI draft requires explicit operator send | Accepted |
| D-008 | `Take over` permanently reduces current conversation N2->N1 until close | Accepted |
| D-009 | Operator max active conversations = 4; manual claim | Accepted |
| D-010 | Six-tab acceptance scenario: 4 active, 2 waiting | Accepted |
| D-011 | V1 includes offline knowledge ingestion/vectorization | Accepted |
| D-012 | Administrative Q&A flat retrieval | Accepted |
| D-013 | Clinical child retrieval + parent context expansion | Accepted |
| D-014 | Clinical citations may be customer-visible; administrative source details may not | Accepted |
| D-015 | Insufficient evidence -> abstain draft; no auto-escalation in V1 | Accepted |
| D-016 | No streaming V1 | Accepted |
| D-017 | Docker Compose local acceptance; GCP deferred | Accepted |
| D-018 | Audit event catalog begins in V1 | Accepted |
| D-019 | Future saved-session recovery uses consent + CPF identifier + safely hashed password; no plaintext password | Roadmap |
| D-020 | Future wrong CPF/password combination can fall back to new anonymous session but cannot access/overwrite persisted identity | Roadmap |
| D-021 | Telegram is a later channel adapter, not a parallel engine | Roadmap |
| D-022 | Autonomy may auto-decrease in future; never auto-increase | Roadmap |
| D-023 | Adopt existing `content.documents` parent -> `content.chunks` child and flat `content.qa_entries` in place; do not duplicate the corpus | Accepted |
| D-024 | Preserve legacy scheduling/identity/billing source and schema as dormant historical assets, but exclude their endpoints and behavior from the V1 runtime | Accepted |
| D-025 | Keep the existing `app/` + pip backend root; reorganize it into required logical modules instead of a greenfield `backend/`/Poetry migration | Accepted |
