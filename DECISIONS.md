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
| D-027 | The next authorized specification cycle is V2 commercial product experience: professional UX, customer-safe token display/copy, operator-selected evidence, and operator-selected conversation context. Dynamic appointment availability is excluded unless explicitly added later. | Implemented — V2 DONE 2026-08-17 |
| D-028 | Correction for the `dynamic_data_required=true` finding (D-026): when selected/retrieved evidence has `dynamic_data_required=true`, the final response must follow a developed chunk pattern with its variables substituted from live database content; the LLM must not compose or rewrite that response for this case — the resolved pattern is the final message. This does not, by itself, authorize the appointment-booking behaviors D-026/ROADMAP.md still defer. Human decided 2026-08-12 that this correction's execution is planned within the V2 specification cycle rather than as an immediate V1 patch. | Implemented — V2 Phase 7, DONE 2026-08-17 |
| D-029 | Prioritize a production deployment of the completed V1+V2 system ahead of starting the V3 specification cycle. Target: GCP Cloud Run (backend, `min-instances=0`) + Firebase Hosting (frontend, free `*.web.app` domain, automatic TLS, `/api/**` rewrite to Cloud Run instead of CORS) + Neon serverless Postgres (chosen over Supabase because Neon auto-resumes on connection while Supabase's free tier fully pauses the project after inactivity, which is incompatible with a scale-to-zero backend). Explicitly infrastructure only — data remains synthetic/demo per Constitution Article VI; deploying real patient/customer data is a separate, larger decision requiring a constitution amendment and the privacy/security/legal review `SECURITY.md` already requires. Human decided 2026-08-17. See `DEPLOYMENT.md` "Production deployment" section for the full runbook. | Implemented — deployed and verified end-to-end 2026-08-17 |
| D-030 | Correction to V2's per-source token-validation rate limiter (D-018/plan.md §13.1): the client key was derived from `request.client.host`, the immediate TCP peer — behind the project's one same-origin reverse-proxy hop (local docker-compose nginx; Firebase Hosting's `/api/**` rewrite to Cloud Run in production, D-029), that collapses every real customer onto one shared value, making the "per-source" lockout global instead of per-customer (one attacker's lockout would deny every legitimate customer, not just themselves) — a violation of plan.md §13.1's own explicit acceptance requirement that the limiter "does not block legitimate customers." Found 2026-08-18 while adding V3's `v3.spec.ts` (tasks.md T132): running it immediately after `v2.spec.ts`'s T128 (which deliberately trips the lockout) made the collision reproducible for the first time. Fixed by adding `customer_care/shared/http.py`'s `client_ip()`, which trusts `X-Forwarded-For`'s first entry when present (both proxies are configured to *set*, never append/pass through, this header from their own view of the connecting peer — `frontend/nginx.conf`'s `proxy_set_header X-Forwarded-For $remote_addr`), falling back to `request.client.host`. No spec/plan text changed — plan.md §13.1's own requirement was already correct; only the implementation was wrong. Human decided 2026-08-18 to fix immediately as an approved V2 correction rather than deferring. | Implemented — V3 Phase 13, DONE 2026-08-18 |
| D-031 | **Constitution Amendment 1.1.0 — first-ever amendment to Article III** (`.specify/memory/constitution.md`). Authorizes one narrowly-scoped exception to human-authority-over-outbound-AI: the dynamic-appointment-availability feature's simulated identity/payment-confirmation script (`specs/004-dynamic-appointment-availability/`) may send its fixed, pre-scripted, human-authored template messages to the customer automatically, without a per-message operator click — strictly limited to that one script's CPF-format-only validation and sim/não confirmation steps, never LLM-composed or LLM-rewritten, with no real booking/payment/identity persistence (booking itself, D-026, remains separately deferred). Every other outbound message in the system remains governed by Article III's original explicit-operator-send-only rule without exception; this does not set a precedent for broader autonomy (N3/N4) discussions, which remain separately gated. Human explicitly weighed this against the one-click-per-message (quick-approve) alternative that would have preserved Article III without exception, and chose the autonomous-send exception after that tradeoff was made clear. Human decided 2026-08-18. | Accepted — specification pending, not yet implemented |
