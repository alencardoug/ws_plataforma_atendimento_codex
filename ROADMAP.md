# Product Roadmap — Frozen During V1

This roadmap preserves the long-term product vision. It is **not executable scope**. Future versions must receive their own Spec Kit feature directory and clarification before implementation.

## Era A — Existence

### V1 — Functional assisted-service core

Current scope. Anonymous web customer, operator, N1/N2, offline ingestion, dual RAG strategy, queue/capacity, audit, local Docker Compose.

### V2 — Commercial product experience

- professional UI/UX;
- streaming where beneficial;
- stronger operator workspace ergonomics;
- hybrid push/pull routing baseline;
- explicit runtime/admin configuration surface if justified;
- channel abstraction hardened.

## Era B — Trust

### V3 — Measured N2

- full operator feedback taxonomy;
- approve/edit/regenerate/regenerate-with-instruction/search/take-over/escalate/mark-incorrect;
- Human Correction Rate and related evidence;
- first read-only management metrics;
- evaluation datasets/suites tied to categories.

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
