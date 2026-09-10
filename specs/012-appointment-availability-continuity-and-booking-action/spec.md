# Feature Specification: Appointment-Availability Continuity + Operator Booking-Offer Action

## 1. Purpose

Two connected defects were found by the human on 2026-08-27, running a real
conversation ("Olá" → "Quero agendar uma consulta") against a freshly
rebuilt local Docker stack (screenshot: `DOCS_PESSOAIS/`-referenced
`deletar.jpg`). The customer received an autonomous "Claro — posso
agendar. Por favor me informe: nome completo, telefone…" reply that
gathers data forever and never books anything.

Root cause, confirmed by direct inspection (`app/customer_care/ai/router.py`,
`app/customer_care/scheduling/availability.py`, live DB):

- **Retrieval is fine.** For "Quero agendar uma consulta" the rank-1
  evidence is `QA-011` (`dynamic_resolver = appointment_availability`,
  cosine distance ≈ 0.33 against real `text-embedding-3-small` output),
  well ahead of every other entry. `dynamic_pattern_result()` *does*
  select the named resolver.
- **The resolver abstained.** `resolve_appointment_availability()` raised
  `DynamicResolutionError` → `GenerationResult("ABSTAIN",
  "DYNAMIC_DATA_UNAVAILABLE")` because `schedule_slots` had nothing to
  offer for the generalist specialty. A freshly built stack starts with
  **zero** seeded slots; `specs/004-dynamic-appointment-availability/`
  AA-9 makes slot creation an *explicit operator button* that had never
  been clicked.
- **N5 masked the abstention.** With this project's standing demo config
  (`autonomy_kill_switch_enabled = false`, `n5_kill_switch_enabled =
  true`, `autonomy_window_seconds = 0`), `maybe_open_autonomous_window()`
  took the `status != "ANSWER"` branch and sent a free-form, evidence-free
  `generate_ungoverned_reply()` completion immediately. Constitution
  Amendment 1.3.0 clause (b) explicitly authorizes exactly this
  ABSTAIN-override, so N5's behavior here is **correct and stays
  unchanged** (human decision 2026-08-27).

Since N5's masking is by-design, the fix is to stop the resolver
abstaining in the first place (**Availability Continuity**, AC) and to
give the operator a direct, deterministic way to put a real slot offer in
front of the customer instead of depending on RAG ranking plus the idle
auto-trigger (**Operator Booking-Offer action**, OB).

## 2. Authorization

Human decision 2026-08-27 (`DECISIONS.md` D-044), after a scoping exchange:

1. Keep N5 exactly as-is; do **not** add a runtime "N5 must not mask
   `DYNAMIC_DATA_UNAVAILABLE`" rule.
2. Keep the simulated agenda continuously populated so the resolver has
   real data to return — via a **query-independent** reseed only
   (bootstrap fill + a low-water-mark top-up evaluated on the operator
   dashboard poll, the same lazy hook `evaluate_unclaimed_autonomous_trigger()`
   already rides). The "check inventory inside the booking flow and seed
   there" variant was explicitly rejected as it would reverse
   `specs/004` clarification item 6.
3. Add a per-conversation operator button, between "Enviar" and "Encerrar
   conversa", that generates an appointment-availability **draft** for
   ordinary operator review — never a new autonomous-send path.

No Constitution amendment is required. This cycle **narrowly supersedes
one clause of `specs/004-dynamic-appointment-availability/` AA-9** (see
§4) and adds a new operator surface; both are documentation-authority
changes handled in-package per `AGENTS.md`.

## 3. Definitions

- **AC — Availability Continuity**: the mechanism that keeps
  `scheduling.schedule_slots` non-empty for the generalist specialty (and
  the wider specialty set) without any customer- or operator-*query* ever
  creating a slot.
- **Bootstrap fill**: a one-time, idempotent wide seed run as an explicit
  deployment/startup step — not a request handler, not a query side
  effect.
- **Low-water-mark top-up**: an idempotent check, evaluated lazily from
  the operator queue poll (`GET /operator/conversations` →
  `list_conversations()`), that creates generalist slots only when
  available future inventory for the relevant window has fallen to or
  below a floor. Never reachable from `resolve_appointment_availability()`,
  `resolve_price_lookup()`, `generate_draft()`, or any anonymous-customer
  endpoint.
- **OB — Operator Booking-Offer action**: a new authenticated,
  conversation-scoped operator endpoint + button that runs the
  `appointment_availability` resolver directly for the selected
  conversation and persists the result as an ordinary `AIGeneration`
  draft (`status = ANSWER` or `status = ABSTAIN`), returned to the
  operator for manual review/send. Deterministic, read-only, never
  LLM-composed, never autonomously sent.
- **`MANUAL_BOOKING_OFFER`**: the new `ai_generations.trigger` value for
  an OB-produced generation. Chosen so it is unambiguously **not**
  `AUTOMATIC` and not any GB flow trigger — `maybe_open_autonomous_window()`
  never sees it as eligible (Constitution Amendment 1.2.0 clause (b):
  a manually requested draft is never eligible for autonomous send).

## 4. Supersession of `specs/004` AA-9

`specs/004-dynamic-appointment-availability/spec.md` AA-9 item 5 states
the D+1/D+7 button was "originally the *only* write path in this feature"
and that "the query path (AA-2) still never writes under any
circumstance," and clarification item 6 (second round, 2026-08-18) states
"**no on-demand slot generation as a side effect of a customer/operator
query, at all.**"

This cycle changes AA-9 **only** as follows, and only in this direction:

- Slot creation is no longer reachable **exclusively** through the
  operator D+1/D+7 button. Two additional write entry points exist: the
  bootstrap fill (AC-1) and the low-water-mark top-up (AC-2).
- Clarification item 6 is **preserved intact**: no
  customer/operator *query* — no RAG retrieval, no resolver, no
  draft-generation call, no anonymous endpoint — ever creates a slot. The
  top-up (AC-2) rides the operator *queue poll*, which is the same lazy
  non-query evaluation point feature 010 already established for
  autonomous-trigger evaluation; it is explicitly not the "resolver tops
  up its own data" pattern item 6 struck down.
- AA-9's own button (`POST /operator/scheduling/ensure-availability`) and
  the 006 wide button (`POST /operator/scheduling/ensure-wide-availability`)
  are unchanged and remain available.
- AA-10's containment is untouched. `booking_script/service.py` is not
  imported, read, or modified by anything in this cycle.

`analysis.md` for this package must carry the cross-artifact note
recording this supersession, and `specs/004`'s spec.md gets a one-line
forward pointer to it (documentation-drift rule, `AGENTS.md`).

## 5. Functional requirements — Availability Continuity (AC)

### AC-1 — Bootstrap fill

A single idempotent operation fills `schedule_slots` for the full
specialty set across the standard wide horizon (reuse
`scheduling/seeding.py::ensure_wide_availability()` verbatim — it is
already `ON CONFLICT DO NOTHING` idempotent, already reads every specialty
live from `scheduling.specialties`, already bounded by
`WIDE_SEED_END_DATE`).

- It runs as an explicit startup/deployment step, **not** inside any
  request handler and **not** as an import-time side effect. Concretely:
  a small module entry point (e.g. `python -m customer_care.scheduling.bootstrap_seed`)
  invoked by the backend container's start command / compose command
  before/alongside `uvicorn`, idempotent enough to run on every container
  start.
- It must be safe to run when slots already exist (no duplication, fast
  no-op path).
- It must not run automatically in the unit/integration test process
  (tests seed their own fixtures); gate on an explicit env flag or the
  same `AI_PROVIDER`/settings switch pattern already used to distinguish
  environments, decided in `plan.md`.
- Audit: emit one `scheduling.availability_bootstrap_seeded` event
  (SYSTEM actor) with the created-count and specialty/day counts,
  mirroring `ensure_wide_availability`'s existing result shape.

### AC-2 — Low-water-mark top-up

A new idempotent function — `ensure_generalist_floor(session)` in
`scheduling/seeding.py` — evaluated lazily from `list_conversations()`
(the operator queue poll), immediately alongside the existing
per-conversation `evaluate_unclaimed_autonomous_trigger()` loop, and
nowhere else.

- **Floor**: available future generalist-specialty (`oncologia-geral`)
  slots, counted with `starts_at >= now()` and `status = 'available'`,
  for the AA-9 D+1 and D+7 target business days. When either day's count
  is `<= AC_FLOOR_MIN`, top it back up to `AC_FLOOR_TARGET`. Concrete
  numbers (`AC_FLOOR_MIN`, `AC_FLOOR_TARGET`) are set in `plan.md`;
  starting proposal `AC_FLOOR_MIN = 2`, `AC_FLOOR_TARGET = 8`, matching
  the human's "sempre que sobrar 2 ou 1 agenda somente" phrasing with
  headroom so the top-up is not re-triggered every single poll.
- Reuses `create_slots_on()` / `next_business_day_sql()` /
  `_generalist_specialty_id()` — no new slot-creation code path.
- Holds the same transaction-scoped `pg_advisory_xact_lock` discipline
  `ensure_seed_availability()` already uses (a distinct lock key), so two
  operators' concurrent polls can never both create beyond target.
- Debounce: it must not run a counting query on every single poll for
  every operator. Gate on a cheap precondition first — e.g. a
  `system_settings.availability_floor_checked_at` timestamp with a
  minimum interval (proposal: 60 s), decided in `plan.md`. The interval
  gate is a plain time check, not a slot query.
- Never raises into the caller: any failure is swallowed exactly like
  `evaluate_automatic_trigger()`'s own `except Exception: pass`, so a
  seeding hiccup never breaks the operator's queue load.
- Audit: when it actually creates slots, emit one
  `scheduling.availability_floor_topped_up` event (SYSTEM actor) with the
  before/after counts and created count. A no-op check emits nothing.

### AC-3 — Query path stays read-only

`resolve_appointment_availability()` and `resolve_price_lookup()` are
**not modified** by this cycle. No slot-creation call is added to
`ai/router.py`, `anonymous_access/router.py`'s customer-message path, or
any resolver. A negative test proves a customer booking message against an
empty agenda still `ABSTAIN`s (and, with N5 on, still falls to
`generate_ungoverned_reply()`) — i.e. the query path itself never
self-heals. AC only changes what inventory exists *before* the query
runs.

## 6. Functional requirements — Operator Booking-Offer action (OB)

### OB-1 — Endpoint

`POST /operator/conversations/{conversation_id}/booking-offer-draft`

- Auth: `CurrentOperator`, and the conversation must be assigned to that
  operator — identical guard to the existing `POST /operator/conversations/{id}/drafts`
  (`draft()`), returning the same `403 FORBIDDEN` shape otherwise.
- Rejected with the existing `409 MODE_NOT_ALLOWED` shape when the
  conversation is not an active effective-N2 conversation (same
  precondition `generate_draft()` already enforces).
- Optional body `{ "manual_search_text": string }` — free-text hint
  ("mastologia amanhã de manhã") passed straight into the resolver's own
  `extract_parameters()` (specialty / date / period keywords, plus the
  006 LLM date fallback the resolver already does). Empty/omitted → the
  resolver runs on the conversation's trailing customer-message text, the
  same selection `_uncovered_customer_run()` builds.

### OB-2 — Deterministic resolution, ordinary draft

The handler calls `resolve_appointment_availability(session, query_text)`
directly — bypassing RAG ranking entirely, since the operator has
explicitly asked for an availability offer.

- On success: persist an `AIGeneration` with `status = ANSWER`,
  `draft_text` = the rendered offer block, `provider =
  "dynamic-pattern-resolver"`, `model = "not-applicable"`, `trigger =
  "MANUAL_BOOKING_OFFER"`, `dynamic_pattern_used = true`,
  `retrieval_run_id` = a real retrieval run recorded for this call
  (Article V traceability — reuse `generate_draft()`'s existing
  `retrieve()` call so evidence is still attributable), linked
  `AIGenerationSource` to the `appointment_availability` QA hit when it is
  present in that run.
- Persist the offered rows via the existing
  `persist_presented_offers(session, embedding_provider, generation.id,
  offered_rows)` so a subsequent customer slot-choice reply is matched by
  `interpret_slot_choice()` (005/GB-1) exactly as it is for a
  resolver-driven offer today.
- On `DynamicResolutionError`: persist an `AIGeneration` with `status =
  ABSTAIN`, `abstention_reason = "DYNAMIC_DATA_UNAVAILABLE"`,
  `draft_text = ""`. The operator sees "sem agenda simulada disponível"
  in the draft panel (client renders the existing abstention state). This
  must never be sent to the customer by this endpoint.
- Emit `ai.draft_generated` / `ai.draft_abstained` and, on success,
  `ai.dynamic_pattern_resolved` — the same events `generate_draft()`
  already emits for a dynamic resolution, so metrics/timeline are
  consistent.

### OB-3 — Never an autonomous send

`trigger = "MANUAL_BOOKING_OFFER"` is never in
`maybe_open_autonomous_window()`'s eligible set (neither `"AUTOMATIC"` nor
a `_N5_ELIGIBLE_GB_TRIGGERS` value). A negative test asserts that calling
OB with **both** kill switches on, `autonomy_window_seconds = 0`, still
produces **no** `pending_autonomous_sends` row and **no** customer-visible
message — only a draft. The customer message appears only after the
operator's ordinary explicit send of that draft (existing mechanism,
unchanged).

### OB-4 — Button placement

`frontend/src/main.tsx`: a new button in the **operator** conversation
detail action row, positioned **between "Enviar" and "Encerrar conversa"**
(the operator panel's own pair, ~L816/820 — *not* the customer chat
widget's Enviar/Encerrar pair ~L415/426, which has no draft panel or
operator endpoint).

- Label: "Gerar oferta de agendamento".
- Enabled only when the conversation is claimed by the current operator
  and `status !== "CLOSED"` and effective mode is N2 — same enablement
  logic as the existing "Gerar rascunho" button.
- On click: calls OB-1, then refreshes the draft panel exactly as
  "Gerar rascunho" does (reuses the existing latest-generation poll/render
  path — no new draft-display component).
- No new customer-facing UI. The customer sees nothing until the operator
  sends the resulting draft.

## 7. Data model impact (elaborated in `data-model.md`)

- `ai_generations.trigger`: its CHECK constraint (widened before by
  features 005/010 for the GB flow triggers) widens once more for
  `'MANUAL_BOOKING_OFFER'`. Confirm during implementation whether a
  second independent trigger CHECK exists (as happened for `messages` in
  feature 010) and widen it too.
- `system_settings`: gains `availability_floor_checked_at timestamptz
  NULL` (AC-2 debounce). No other column.
- No new tables. AC reuses `schedule_slots` and the existing seeding
  functions; OB reuses `ai_generations` / `ai_generation_sources` /
  `appointment_offer_presentations`.
- New audit event types: `scheduling.availability_bootstrap_seeded`,
  `scheduling.availability_floor_topped_up`. Registered in
  `docs/architecture/EVENT_CATALOG.md`.

## 8. Acceptance outcomes to develop into executable tests

1. **AC bootstrap** — starting from an empty `schedule_slots`, the
   bootstrap entry point creates generalist + specialty inventory across
   the wide horizon; a second run is a fast no-op (`ON CONFLICT DO
   NOTHING`, zero new rows) and emits no second "created" count.
2. **AC top-up fires** — with generalist D+1 inventory manually reduced to
   `<= AC_FLOOR_MIN` available future slots, one `list_conversations()`
   call restores it to `AC_FLOOR_TARGET` and writes exactly one
   `scheduling.availability_floor_topped_up` event; inventory already
   above the floor → no event, no new rows.
3. **AC top-up is debounced** — two `list_conversations()` calls inside
   the minimum interval run the counting query at most once (assert via
   `availability_floor_checked_at` movement or a query counter).
4. **AC top-up is query-independent** — a customer booking message
   (`POST` anonymous send → `evaluate_automatic_trigger`) against an empty
   agenda still `ABSTAIN`s / still falls to `generate_ungoverned_reply()`
   under N5; no slot is created by that path. (Negative test for the
   `specs/004` clarification-6 invariant.)
5. **AC concurrency** — two concurrent `ensure_generalist_floor()` calls
   never create beyond `AC_FLOOR_TARGET` (advisory-lock test, mirrors
   `ensure_seed_availability`'s own).
6. **OB happy path** — operator clicks the button on a conversation whose
   customer said "quero agendar uma consulta"; a `MANUAL_BOOKING_OFFER`
   `AIGeneration` (`status = ANSWER`) is created with the rendered offer
   block and `appointment_offer_presentations` rows; the operator then
   sends it with the ordinary send; the customer's next "opção 2" reply
   resolves via `interpret_slot_choice()` unchanged.
7. **OB with hint** — `manual_search_text = "mastologia amanhã de manhã"`
   filters the resolver output to that specialty/day/period.
8. **OB abstains cleanly** — same call against a genuinely empty agenda
   yields a `status = ABSTAIN` / `DYNAMIC_DATA_UNAVAILABLE` draft and
   **no** customer message.
9. **OB never autonomous** — OB call with both kill switches on and
   `autonomy_window_seconds = 0` produces no `pending_autonomous_sends`
   row and no customer-visible message (negative safety test, Article X /
   Amendment 1.2.0(b)).
10. **OB auth** — unauthenticated call rejected; authenticated call on a
    conversation the operator has not claimed rejected with `403
    FORBIDDEN`; call on a `CLOSED` conversation rejected with `409`.
11. **Frontend** — the "Gerar oferta de agendamento" button renders
    between "Enviar" and "Encerrar conversa" at both panel sites, is
    disabled on a `CLOSED`/unclaimed/non-N2 conversation, and on click
    populates the draft panel without sending anything.
12. **Regression** — the six existing scheduling/GB/autonomy smoke suites
    (`smoke_v4_*`, `smoke_v5_guided_booking`, `smoke_v6_*`,
    `smoke_v10_*`, `smoke_v11_*`) still pass; `test_booking_script_containment.py`
    and `test_010_governed_autonomy_containment.py` unchanged and green.

## 9. What this cycle does **not** do

- Does not change N5, N3/N4, or the veto-window mechanism in any way.
- Does not change `resolve_appointment_availability()` /
  `resolve_price_lookup()` logic, or add any slot write to a query path.
- Does not touch `booking_script/service.py` or widen Amendment 1.1.0 /
  1.2.0 / 1.3.0.
- Does not implement real booking, holds, payment, persisted identity, or
  `insurance_lookup` — all still deferred per `specs/004` §6 and
  `specs/005` §6.
- Does not add a customer-facing "request availability" control — OB is
  operator-only; the customer path remains: message → resolver (now with
  real inventory) → draft → autonomous or manual send.
- Does not add a scheduler, cron, worker, or any distributed
  infrastructure (Article VIII) — AC-2 is lazy-evaluated on an existing
  poll, AC-1 is a start command step.

## 10. Open questions for `plan.md` / a short grill

1. `AC_FLOOR_MIN` / `AC_FLOOR_TARGET` / debounce interval final values.
2. Whether AC-1 also runs the AA-9 narrow D+1/D+7 generalist top-up (for
   the exact `count_d1 >= 1 && count_d7 >= 3` guarantee the query path's
   generalist fallback leans on) or whether AC-2's floor subsumes it.
3. AC-1 gating: env flag name vs. reuse of an existing settings switch, so
   it never fires in the pytest process.
4. Whether OB should default its query text to *only the latest* customer
   message vs. the full trailing customer run (the resolver is
   keyword-based, so more text is usually harmless, but a long unrelated
   trailing message could pull in a stray specialty keyword).
5. Whether the OB button should be hidden entirely (vs. disabled) when the
   conversation has no customer message yet.
