# Product Roadmap

This roadmap preserves the long-term product vision. It is **not executable
scope** for any entry not already implemented. The human authorized the V2
specification cycle on 2026-08-11; **V2 is now DONE (2026-08-17)** — see
`PROJECT_STATE.md` and `specs/002-v2-commercial-product-experience/`. All
other entries (including the separate future "Dynamic appointment
availability" feature below, which is not part of completed V2) remain
roadmap only until their own Spec Kit flow is authorized and completed.

## Era A — Existence

### V1 — Functional assisted-service core

Current scope. Anonymous web customer, operator, N1/N2, offline ingestion, dual RAG strategy, queue/capacity, audit, local Docker Compose.

### Future feature — Dynamic appointment availability

This is intentionally separate from V2, with one narrow exception (see below).
Choose a feature ID and create its Spec Kit directory only when a human
authorizes this scope. This entry records agreed intent but is not executable
scope until its own specification, plan, tasks, and consistency analysis are
approved.

The cycle must begin with a safety correction: administrative evidence marked
`dynamic_data_required=true` must never be passed through as a literal answer
when its resolver is unavailable. It must produce a controlled abstention or a
manual-service instruction without exposing internal table names, resolver
names, placeholders, or implementation guidance.

**Scope exception (D-028, human decision 2026-08-12):** the corrective
mechanism itself — a deterministic chunk pattern whose variables are
substituted from live database content, used verbatim as the final response
with no LLM rewriting for `dynamic_data_required=true` evidence — is now
planned within the V2 specification cycle rather than waiting for this
separate feature's authorization. Everything else below (actual booking
operations, resolver implementations, holds/reservations) remains deferred to
this separate future feature and still requires its own Spec Kit package.

Planned in scope:

- allowlisted resolution of `dynamic_resolver=appointment_availability`;
- read-only consultation of synthetic availability in PostgreSQL;
- structured, time-zone-aware evidence for RAG and operator review;
- explicit operator send remains the only customer-visible outbound action;
- append-only audit of resolver request, outcome, and safe provenance;
- manual fallback for unavailable, stale, empty, or failed dynamic data;
- tests for unresolved dynamic data, fabrication prevention, data freshness,
  resolver allowlisting, failure fallback, and information exposure.

Explicitly deferred from this cycle:

- holding, reserving, confirming, rescheduling, or cancelling appointments;
- CPF, customer identity/profile persistence, payment, or saved continuity;
- autonomous AI send or autonomous scheduling.

### V2 — Commercial product experience — **DONE (2026-08-17)**

Feature package: `specs/002-v2-commercial-product-experience/`. All items
below were implemented and passed acceptance; see that package's
`acceptance.md` Execution record and `tasks.md` T000-T131 for evidence. This
section is kept as the historical record of the authorized scope.

- professional UI/UX;
- customer-facing display and copy action for that customer's own conversation
  token, without placing the token in URLs or logs;
- operator-selected evidence workflow: manual search displays retrieved Q&A
  records and clinical child chunks; the operator may select them before
  generation. A selected clinical child returns its complete parent document
  for explicit operator send, while selected Q&A records are supplied to the
  LLM to compose a concise response focused on the customer request. Selection,
  parent expansion, generation provenance, and explicit human send remain
  auditable;
- operator-selected conversation context: each message has a checkbox so the
  operator can choose which customer and operator messages are provided to
  draft generation; the selected message IDs and resulting generation remain
  traceable and auditable;
- streaming where beneficial;
- stronger operator workspace ergonomics;
- hybrid push/pull routing baseline;
- explicit runtime/admin configuration surface if justified;
- channel abstraction hardened;
- `dynamic_data_required=true` safety correction (D-028): deterministic,
  database-driven chunk-pattern substitution as the final response, with no
  LLM rewrite, for administrative evidence flagged this way. Scoped to the
  correction itself, not to appointment-booking operations.

## Era B — Trust

### V3 — Measured N2 — Implemented (DONE 2026-08-18)

- full operator feedback taxonomy;
- approve/edit/regenerate/regenerate-with-instruction/search/take-over/escalate/mark-incorrect;
- Human Correction Rate and related evidence;
- first read-only management metrics;
- evaluation datasets/suites tied to categories.

See `specs/003-v3-measured-n2/` for the full spec/plan/tasks/acceptance
package and `PROJECT_STATE.md`'s "V3 implementation — DONE" section for
the closure summary.

### V4 — N3 governed autonomy / Supervisor

- supervisor interface;
- category-level ON/OFF/REVIEW/ESCALATE policies;
- policy audit/justification;
- HITL for categories not authorized for autonomous sending;
- operator may reduce autonomy, never increase above policy.

### V5 — Mature human handoff and queue operations

- structured one-time handoff package;
- call-center specialist escalation;
- dynamic queue ETA;
- richer routing/assignment;
- customer reconnect/contact-capture workflow.

### Cross-cutting — Telegram

Implement after the channel boundary is stable. Telegram maps into the same conversation engine; no duplicated RAG/business logic.

### Future persisted customer continuity

Only when needed:

- ask explicit consent to save essential continuity data;
- CPF + password verification to resume saved profile/state;
- persisted data minimized to operational needs such as confirmed appointment date/time/location, contact details, relevant preparation/document reminders, and essential identity fields;
- incorrect credentials never disclose or expose prior data;
- new anonymous session remains possible.

## Era C — Autonomy

### V6 — Team-level controlled rollout

Organization default + team overrides + pilot cohorts.

### V7 — Autonomy control plane

Policy controls adjacent to evidence: acceptance, edit, rejection, error, abstention, evaluation status, policy history.

### V8 — Automatic safety downgrade

`AUTO -> REVIEW` can happen automatically when operational/evaluation evidence degrades. Autonomy never increases automatically.

### V9 — N4 HOTL

Eligible categories operate autonomously. Operator sees pending answer and has a policy-driven veto window with PAUSE / EDIT / TAKE OVER. N4 remains bounded by policy.

## Era D — Platform

### V10 — Autonomy Timeline

Human-readable reconstruction of autonomy, responses, interventions, and policy changes from durable events.

### V11 — Technical Admin / AI Ops

Knowledge snapshots, prompt/model versions, evaluation suites, publishing, rollback, incidents, technical configuration audit.

### V12 — Contextual per-interaction autonomy

Durable organization/team maturity remains, but individual interactions can automatically reduce autonomy based on evidence/risk/conflict. No automatic upward promotion.
