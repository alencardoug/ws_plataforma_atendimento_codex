# AGENTS.md — Codex / Coding Agent Contract

## Authority order

1. human instruction in current session;
2. `.specify/memory/constitution.md`;
3. active feature `spec.md`;
4. active feature `plan.md`;
5. active feature `tasks.md`;
6. root architecture/security/test/data docs;
7. ADRs;
8. roadmap/readme.

Do not silently invent a resolution to conflicting requirements. Update the highest-authority artifact that must change.

## Current authorized scope

V1 baseline: `specs/001-v1-assisted-customer-service` — implemented and closed
for new product behavior.

V2: `specs/002-v2-commercial-product-experience` — DONE (2026-08-17). See
`PROJECT_STATE.md`.

V3 ("Measured N2"): `specs/003-v3-measured-n2` — DONE (2026-08-18). See
`PROJECT_STATE.md`.

Dynamic appointment availability (read-only resolver plus its explicitly
bounded seed action/AA-10 simulation):
`specs/004-dynamic-appointment-availability` — explicitly authorized by the
human on 2026-08-18 and **DONE 2026-08-19**. All 10 phases passed final
acceptance (`acceptance.md` Execution record; `analysis.md` §18). AA-10's
fixed booking simulation is the sole Constitution Amendment 1.1.0 outbound
exception; it performs no real booking/payment/identity persistence and is
structurally contained to one function/one trigger. Real booking, holds,
payment, identity persistence, scheduling CRUD, and every other
`dynamic_resolver` besides `appointment_availability` remain out of scope —
see that package's `spec.md` §6.

Dynamic pricing and guided booking selection: `specs/005-dynamic-pricing-
and-guided-booking` — explicitly authorized by the human on 2026-08-19 and
**DONE 2026-08-19** (D-032, corrected same day by D-033). Implements a
real `price_lookup` named resolver (reuses 004's `professional_specialties`
data, no new source), corrects the `preco`/`pagamento` Q&A content, and
adds guided booking selection — ordinal/positional and embedding-assisted
slot-choice interpretation, then a direct-to-CPF/payment flow reusing
`booking_script.parsing`'s deterministic parsers — entirely inside N2:
every output is an ordinary operator-reviewable draft, never an autonomous
send. Constitution Amendment 1.1.0's AA-10 exception is unchanged and
unextended (verified structurally — `booking_script/service.py`
byte-identical, `booking_script/parsing.py`'s two pure functions are the
one disclosed, narrow import GB has). `insurance_lookup`/`convenio`
remains deferred — see that package's `spec.md` §6/§10.

## Required SDD flow

Before code:

1. read constitution;
2. read all active feature artifacts;
3. run Spec Kit `analyze` or an equivalent cross-artifact consistency review;
4. repair documentation contradictions;
5. confirm acceptance checklist coverage;
6. then implement tasks in dependency order.

After code:

1. run unit/integration/API/frontend/E2E gates;
2. run spec-to-code convergence review;
3. update docs for any approved implementation detail;
4. do not begin a later feature without its own authorized specification.

## V1 non-negotiables

- anonymous customer; no customer account/password;
- operator authentication required;
- global N1 or N2 configuration only;
- no streaming;
- web only;
- operator manually claims conversations;
- maximum 4 active conversations/operator;
- six-tab acceptance demo must work: 4 active, 2 waiting;
- N1 manual search is evidence-only and feature-flagged;
- N2 AI output is internal draft only;
- only explicit operator send creates customer-visible operator message;
- operator can `Take over`, reducing effective N2 -> N1 until close;
- V1 includes ingestion/vectorization;
- administrative Q&A is flat; clinical knowledge is parent-child;
- clinical citations may be customer-visible; administrative source details may not;
- insufficient evidence creates abstention state/draft, not unsupported answer;
- AI/RAG failure must preserve manual service;
- append-only audit events required;
- synthetic/demo data only;
- no chain-of-thought persistence.

These rules remain the V1 baseline. A V2 artifact may deliberately supersede a
rule only when the human-approved V2 specification says so and preserves the
constitution's safety constraints.

## Architecture rules

Required logical modules:

- auth;
- anonymous_access;
- conversations;
- autonomy;
- operator_workspace;
- knowledge;
- rag;
- ai;
- audit;
- shared/infrastructure.

Keep domain/application logic independent of FastAPI request classes and provider SDK response objects.

The AI provider is behind an interface. The initial adapter may use OpenAI.

The channel boundary must allow a later Telegram adapter without duplicating conversation/business/RAG logic.

Do not add LangChain, LlamaIndex, Redis, Kafka, Celery, microservices, or a
vector database separate from PostgreSQL unless an analyzed active-feature
requirement proves necessity.

## Data rules

- PostgreSQL 17 + pgvector;
- migrations via Alembic;
- never edit already-applied migrations;
- raw anonymous customer access token is never persisted;
- operator passwords are hashed;
- AI generations and Messages are separate entities;
- audit events are immutable through application services;
- retrieval evidence is persisted sufficiently for traceability.

## Security rules

- never commit secrets;
- enforce roles/token scope server-side;
- no raw token in logs/URLs;
- no message bodies at INFO by default;
- sanitize/render untrusted content safely;
- customer cannot fetch internal AI draft, audit events, or non-exposable source metadata;
- provider/model output has no authority to send messages or change policy.

## Testing minimum

- backend unit tests;
- PostgreSQL integration tests;
- OpenAPI/API tests;
- frontend component tests;
- end-to-end happy path;
- six-tab / max-four capacity acceptance;
- RAG grounding tests;
- parent-child expansion tests;
- ingestion idempotency tests;
- negative security/safety tests.

## Documentation drift rule

If code requires a behavior not present in the active spec, stop affected implementation and update spec -> plan -> tasks -> analyze before proceeding.
