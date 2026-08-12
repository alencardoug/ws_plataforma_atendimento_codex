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
| D-026 | Dynamic appointment availability is a separate future feature; unresolved `dynamic_data_required` evidence must abstain/fall back safely and never expose internal implementation text | Roadmap |
| D-027 | The next authorized specification cycle is V2 commercial product experience: professional UX, customer-safe token display/copy, operator-selected evidence, and operator-selected conversation context. Dynamic appointment availability is excluded unless explicitly added later. | Accepted for V2 specification |
| D-028 | Correction for the `dynamic_data_required=true` finding (D-026): when selected/retrieved evidence has `dynamic_data_required=true`, the final response must follow a developed chunk pattern with its variables substituted from live database content; the LLM must not compose or rewrite that response for this case — the resolved pattern is the final message. This does not, by itself, authorize the appointment-booking behaviors D-026/ROADMAP.md still defer. Human decided 2026-08-12 that this correction's execution is planned within the V2 specification cycle rather than as an immediate V1 patch. | Accepted for V2 specification |
