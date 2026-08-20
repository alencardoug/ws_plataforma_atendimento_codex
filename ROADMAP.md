# Product Roadmap

This roadmap preserves the long-term product vision. It is **not executable
scope** for any entry not already implemented. The human authorized the V2
specification cycle on 2026-08-11; **V2 is now DONE (2026-08-17)** — see
`PROJECT_STATE.md` and `specs/002-v2-commercial-product-experience/`.
Dynamic appointment availability is also **DONE (2026-08-19)** under its
own package, as is dynamic pricing and guided booking selection (also
**DONE 2026-08-19**, D-032). All other entries remain roadmap only until
their own Spec Kit flow is authorized and completed.

## Priority ordering (human decision, 2026-08-19)

Not a scope change — a sequencing decision for what gets authorized next,
once the items already registered under "Era A — Existence" below
(specialty scheduling breadth and its date-range/volume seeding, and
natural-language date/time parsing) are done:

1. **V4 (N3 governed autonomy/Supervisor) and V9 (N4 HOTL), built with
   real frontend support** — not backend-only; the human wants these
   viable end-to-end through the UI, together.
2. **Then Telegram** (`Cross-cutting — Telegram` below).
3. That completes what the human calls "the essential phase."

**Deferred until after the essential phase** (explicitly, by the human):
V5 (mature human handoff and queue operations), a scheduling-data CRUD
admin UI (analogous to V2-8's knowledge-entry CRUD, not yet its own named
roadmap item — managing `professional_specialties`/`schedule_slots` etc.
through an admin UI instead of direct seeding/SQL), and other remaining
construction items not listed above.

**Stated goal:** after the essential phase, shift from building new
capabilities to refining what exists — the human's own framing is making
this project's production deployment ("plataforma_atendimento_prod") a
satisfactory product, not adding more construction for its own sake.

## Era A — Existence

### V1 — Functional assisted-service core

Current scope. Anonymous web customer, operator, N1/N2, offline ingestion, dual RAG strategy, queue/capacity, audit, local Docker Compose.

### Dynamic appointment availability — **DONE (2026-08-19)**

This was intentionally separate from V2/V3, with one narrow exception (see
below). The human authorized its own Spec Kit cycle on 2026-08-18:
`specs/004-dynamic-appointment-availability/`. Its `spec.md`/`plan.md`/
`data-model.md`/`tasks.md`/`acceptance.md`/`analysis.md` are complete;
implementation and final acceptance are recorded in that package's
Execution record and `analysis.md` §18. See `PROJECT_STATE.md` for the
closure summary. The bullets below preserve the original agreed intent
and deferred boundary.

The cycle's prerequisite safety correction was already completed in V2:
administrative evidence marked
`dynamic_data_required=true` must never be passed through as a literal answer
when its resolver is unavailable. It must produce a controlled abstention or a
manual-service instruction without exposing internal table names, resolver
names, placeholders, or implementation guidance.

**Scope exception (D-028, human decision 2026-08-12):** the corrective
mechanism itself — a deterministic chunk pattern whose variables are
substituted from live database content, used verbatim as the final response
with no LLM rewriting for `dynamic_data_required=true` evidence — was
implemented in V2. The now-completed availability package implemented only
the allowlisted appointment resolver and its documented simulation; actual
booking operations and holds/reservations remain deferred and require their
own Spec Kit package.

Implemented scope:

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
- autonomous AI send or autonomous scheduling;
- a full operator-facing CRUD screen for the `scheduling` schema (create/
  edit/deactivate specialties, professionals, and individual time slots,
  mirroring the existing `/operator/knowledge` Q&A/clinical-document CRUD
  pattern) — human decision 2026-08-18, discussed as an alternative to
  `specs/004-dynamic-appointment-availability`'s one-button idempotent
  D+1/D+7 seed action and deliberately deferred as separate future work,
  since the button alone covers this cycle's actual need. Its own Spec Kit
  package would be required before implementation, same as this feature.

### Dynamic pricing and guided booking selection — **DONE (2026-08-19)**

Closes the RAG coverage gap `teste_humano.md` §6.2 documented for
`preco`/`pagamento`/`convenio` after this feature's own launch (the same
over-flagged-`dynamic_data_required` pattern `agenda` had before this
feature). Human-authorized 2026-08-19 (D-032):
`specs/005-dynamic-pricing-and-guided-booking/`.

Implemented scope:

- a real `price_lookup` named resolver for genuinely per-query price
  questions, reusing this feature's own `professional_specialties` data —
  no new source;
- content correction for the other `preco` entries and all `pagamento`
  entries (static, accurate to what AA-10 actually does — the old content
  described a payment-link/timer mechanism that was never built);
- embedding-assisted guided booking selection: helping the customer pick
  one of the resolver's offered slots, and interpreting a confirmation
  reply, both via real-embedding similarity classification against a
  small candidate/reference set — never an LLM call, never autonomous
  send (stays inside N2, ordinary operator-reviewable drafts only).

Explicitly deferred:

- `insurance_lookup`/`convenio` — stays abstaining, unchanged;
- a real `payment_simulator` resolver, any payment link, or any payment
  timer mechanism;
- any extension of Constitution Amendment 1.1.0's AA-10 exception — the
  human explicitly chose to keep the new guided-selection interpretation
  inside N2 rather than extend the exception, after that tradeoff was made
  explicit (D-032).

### Registered for a future SDD round — specialty citation and scheduling breadth

Not authorized for implementation yet — a note for discovery/specification
before any code changes. Human request, 2026-08-19 (content-only correction
made the same day: unprompted self-harm/"autoagressão" phrasing was removed
from Q&A and clinical content per the same instruction; see D-033's
correction record and `documents/GOVERNANCE.md`'s "Sofrimento emocional
intenso" section):

- when relevant to what the customer's own message is actually asking,
  encourage the generated answer to cite psico-oncologia — already partly
  present in existing content (QA-080/QA-081, `apoio-emocional.md`) — and
  extend the same encouragement to nutrição, endocrinologia, and
  fisioterapia specialized in oncology, when genuinely connected to the
  customer's call, rather than only appearing incidentally;
- add a scheduling/booking option for each of these four specialties
  (psico-oncologia, nutrição, endocrinologia, fisioterapia oncológica) —
  today `price_lookup`/`appointment_availability` cover only the
  specialties already seeded in `professional_specialties`;
- **added 2026-08-19, human request:** once seeded, availability should
  not be limited to today's D+1/D+7 pattern (`ensure-availability`, AA-9)
  — populate a much wider window of bookable slots, for every specialty
  (both the existing ones and the four new ones above), through
  **2026-12-30**, 08:00-18:00, spaced 45 minutes apart, skipping
  holidays. This is a seeding-volume/date-range decision, separate from
  (but related to) `extract_parameters` (AA-3) not yet parsing an
  explicit calendar date like "23/11/2026" from a customer's own message
  (D-035, `DECISIONS.md`) — both need to work together for a customer to
  actually reach one of these far-future slots by naming a specific date;
- **Decided 2026-08-19 (human decision):** `extract_parameters` (AA-3)
  needs to understand richer natural-language date/time expressions
  beyond its current fixed keyword table — human's own examples: "daqui a
  2 terças-feira", "daqui a um mês", "terceira quinta de outubro entre 10
  da manhã e 2 da tarde". Design: **LLM for structured extraction, code
  for the arithmetic** — an LLM call turns the free-text expression into
  a structured intent (e.g. `{relative_unit, relative_count, weekday,
  nth_weekday_of_month, month, time_range}`, exact shape TBD by the
  future spec), and deterministic code (extending AA-3's existing
  pattern, same category as GB-2's ordinal parser) computes the actual
  date/time range from that structure and queries `schedule_slots` —
  the LLM never computes or states a date itself, only classifies/
  structures the customer's phrasing; calendar arithmetic is a known LLM
  failure mode (miscounting "terceira quinta"), so keeping that
  deterministic preserves the auditability this project's other
  date/ordinal parsing already relies on. Still not authorized for
  implementation — the future spec/plan cycle still needs to define the
  exact structured-intent shape, prompt, and fallback behavior when the
  LLM's extraction doesn't cleanly resolve to a query.
- must go through a proper discovery/spec/plan/tasks cycle like every
  other feature — in particular, whether/how this interacts with the
  Constitution Amendment 1.1.0 boundary (it shouldn't need to) and with
  GB's existing offer-presentation/slot-choice mechanics needs its own
  analysis, not an ad hoc content tweak.

### Registered for a future SDD round — completed booking visible to the operator

Not authorized for implementation yet. Human request, 2026-08-19: once a
guided-booking (GB) flow reaches `GUIDED_BOOKING_COMPLETE` (or AA-10's own
autonomous script completes), the specific appointment that was booked —
e.g. "Oncologia geral (triagem) com Dra. Renata Silveira (simulação),
quarta-feira 26/08 às 08:00" — should be visible somewhere in the
operator's conversation view, not only recoverable by reading back through
the chat transcript.

- today neither GB nor AA-10 writes anything to `schedule_slots` or any
  other durable record marking a slot as booked (both are deliberately
  read/interpret/draft-only, GB-5/spec.md §5 AA-10) — there is no queryable
  "this conversation's booking" fact yet, only the chat messages
  themselves; this needs its own data-model decision (a durable booking
  record, or a cheaper derived-from-messages view?), not just a UI change;
- must go through a proper discovery/spec/plan/tasks cycle — in
  particular, whether a durable booking record changes any V1/AA-10 safety
  invariant (identity/payment persistence is explicitly deferred, `specs/
  004-dynamic-appointment-availability/spec.md` §6) needs its own analysis
  before implementation, not an ad hoc frontend addition.

**Added 2026-08-20, human decision — customer-side rendering, session-only,
no persistence:** once the appointment is booked (the same
`GUIDED_BOOKING_COMPLETE`/AA-10-completion trigger as above), a single
summary line of the specific details chosen — e.g. "Oncologia geral
(triagem) — Dra. Renata Silveira (simulação), Unidade Central (simulação),
quinta-feira 27/08 às 08:00 (America/São_Paulo)" — should also appear in
the **customer's own tab** (`CustomerPage`), positioned directly below the
"Enviar" button and above the "Encerrar conversa" button.

- explicitly **not** a durable/persisted field — unlike the operator-facing
  bullet above (which still needs its own data-model decision if a
  durable booking record is chosen), this customer-facing line must be
  session-only, scoped the same way `conversation_id`/`conversation_token`
  already are (`sessionStorage`, cleared on tab close) — closing the
  browser session or ending the conversation must lose it, with nothing
  written to the database for this specific rendering;
- this still needs its own discovery/spec/plan/tasks cycle before
  implementation — in particular, exactly how the client derives this
  line without persistence (e.g. computed client-side from the messages
  already loaded in the open conversation, matching the trigger this
  section's operator-facing bullet already identifies) is a decision for
  that future cycle, not resolved by this note.

### Registered for a future SDD round — draft-generation status visible to the customer

Not authorized for implementation yet. Human request, 2026-08-19: the
"gerando resposta" status the operator already sees while an automatic
draft is being prepared should also show to the customer, next to the
send button.

- today this status only exists operator-side: `frontend/src/main.tsx`
  renders "Respondendo em Ns…" / "Gerando resposta…" (~line 606) from
  `automatic_draft_eligible`/`automatic_draft_seconds_remaining`,
  fields returned only by the
  operator-authenticated `GET /operator/conversations/:id` endpoint
  (polled every 2s) — there is no equivalent field on any customer-facing
  endpoint today;
- `CustomerPage` deliberately renders no such status today — confirmed by
  explicit code comments in `main.tsx` stating these fields/UI are kept
  off the customer projection; exposing any part of it is a new decision,
  not a bug fix — needs its own analysis of exactly what's safe/useful to
  reveal to the customer (a generic "preparando resposta" cue vs. the
  literal countdown-in-seconds AA-2/AA-9 currently show only internally,
  and whether it should also cover the customer-typing-heartbeat-driven
  draft trigger, not just the idle-timeout one);
- must go through a proper discovery/spec/plan/tasks cycle like every
  other feature, not an ad hoc frontend addition.

### Registered for a future SDD round — two-phase clinical evidence: child chunk first, parent on demand

Not authorized for implementation yet. Human request, 2026-08-19, clarified
through follow-up questions (see below) — goal stated by the human: "duas
fases para verificações clínicas, mais controle" (two phases for clinical
checks, more control).

**Today:** `ManualEvidence` (`frontend/src/main.tsx:127-129`, rendered in
the "IA e evidências" sidebar, `main.tsx:638-662`) shows one card per
evidence item with the *full* `content` (the parent document's entire
text, for CLINICAL hits) and one "Selecionar" button that immediately
POSTs to `/operator/knowledge/evidence/{retrieval_hit_id}/select`
(`ai/router.py`'s `select_evidence()`), which reuses `full_parent_draft()`
and replaces the draft with that full text right away. Automatic
(idle-triggered) draft evidence has no select mechanism at all today —
citations are inert labels next to an already-composed LLM draft
(`main.tsx:657`). The `Evidence` dataclass (`rag/service.py:15-25`)
already carries the child chunk's own text separately
(`matched_child_excerpt`) alongside the full parent `content` — both are
already computed, just not displayed separately today.

**Requested design (from the human's clarification):**

- For a clinical question, the sidebar should show multiple *simultaneous*
  candidate options, not one evidence list feeding one draft:
  - the auto-generated **LLM suggestion** (unchanged mechanism — still
    auto-composed, still goes through the D-034 clinical-question
    reranker) — button **"Usar sugestão"**/**"Selecionar"**;
  - any matching **Q&A entries** — same button, directly usable;
  - the retrieved **clinical child chunk(s)** — shown with *only* the
    child excerpt, **not** the full parent — button **"Trazer
    documento"** instead of a direct select.
- **Hard constraint, added 2026-08-19: a parent document must never be
  displayed by default/up front.** It only appears after the operator
  explicitly clicks "Trazer documento" on its corresponding child chunk —
  there is no path that shows a clinical parent's full content before
  that action, for any evidence source (manual search or automatic
  draft).
- Clicking **"Trazer documento"** on a child chunk brings the *full
  parent document* into the sidebar (a new/expanded card) — this parent
  card gets its own selection action.
- **Resolved 2026-08-19:** "Selecionar" was the human's general
  suggestion, not a fixed requirement — the actual button label/action for
  selecting the revealed parent (and whether/how it becomes editable
  before send) should follow whatever the current selection/edit flow
  already does, adapted for least impact, rather than introducing new
  selection semantics. Implementer should read the existing
  `select_evidence()`/draft-editing behavior first and fit this into it.
- **Resolved 2026-08-19:** hiding the parent is a **frontend-only**
  concern — the backend does not need to withhold the parent's full text
  from the payload; today's `Evidence` object already carries both, so no
  new endpoint or response-shape change is required just for this.
- Scroll behavior, requested alongside this: clicking any "Selecionar"
  button (whichever kind) scrolls to the send button; clicking "Trazer
  documento" scrolls to the top of the page.
- Explicitly confirmed by the human: the automatic LLM-generation +
  reranking pipeline itself is **unchanged** — this adds child-chunk
  options *alongside* it, it does not replace or gate the LLM suggestion
  behind an extra click.

**Open design questions for the future spec/plan cycle (not yet
resolved):**

- how manual search (`/operator/knowledge/search`) and automatic-draft
  evidence display converge on one shared sidebar component showing
  multiple simultaneously-selectable candidates, given today's manual
  search and automatic draft are different code paths with different UI
  treatments;
- exact rendering rule for when a "child chunk" card vs. an "LLM
  suggestion" card vs. a "Q&A" card applies (keyed off `knowledge_type`
  and whatever marks a hit as clinical-child vs. clinical-parent-already-
  matched, vs. `provider_name` for the LLM/dynamic-pattern candidate);
- must go through a proper discovery/spec/plan/tasks cycle — this is a
  meaningful evidence-UI redesign, not a small tweak, and should confirm
  it doesn't regress D-013/D-014's clinical parent-context-expansion
  guarantee (the parent must remain reachable and unmodified when
  selected, just gated behind one more click for clinical content).

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
