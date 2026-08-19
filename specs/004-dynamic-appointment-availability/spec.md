# Feature Specification: Dynamic Appointment Availability

**Feature ID:** `004-dynamic-appointment-availability`
**Status:** Clarification complete (2026-08-18, revised same day) —
planning, tasks, analysis, and acceptance coverage required before
implementation
**Authorized for specification:** 2026-08-18
**Scope:** read-only appointment-availability consultation, one explicit
operator-triggered demo-seeding action, and one narrowly-scoped simulated
identity/payment-confirmation script authorized under Constitution
Amendment 1.1.0 (see §6)

## 1. Purpose

`ROADMAP.md`'s "Future feature — Dynamic appointment availability" has been
deferred since V1 (`DECISIONS.md` D-026), with one narrow exception already
carved out and implemented: D-028's safety correction, which made
`dynamic_data_required=true` evidence resolve through a deterministic,
allowlist-only chunk-pattern substitution (no LLM rewrite) instead of ever
being passed through as a literal answer or silently fabricated
(`specs/002-v2-commercial-product-experience/` Phase 7, DONE). That
correction built the *safety* mechanism. It did not build a *resolver* for
appointment availability — no `qa_dynamic_bindings` row or equivalent exists
for the Q&A entries seeded with `dynamic_resolver = 'appointment_availability'`
(`db/init/004_qa.sql`, originally QA-011..QA-024), so they all correctly
abstain today.

This feature closes that gap for **availability consultation only**: let the
chatbot answer "is there an appointment available soon / this week / on a
given day / with a given specialty" using the real (synthetic) data already
sitting dormant in the `scheduling` schema (`db/init/001_schema.sql`,
`002_seed_and_schedule.sql` — `units`, `specialties`, `professionals`,
`professional_specialties`, `holidays`, `schedule_slots`, and
`scheduling.next_business_day()`). It does **not** build booking, holds,
payment, identity, or any other resolver name (`price_lookup`/
`payment_simulator`/`insurance_lookup` remain separately deferred,
unauthorized by this cycle — see §6).

The human's first clarification round (2026-08-18, §5 items 1-5) explicitly
prioritized correct, simple *logic* over preserving the existing
`slot_offers`/`available_offers`/`ensure_demo_availability()`
D+1-and-D+7-window machinery or the exact wording of the 14 seeded `agenda`
Q&A entries verbatim — both may be redesigned or replaced where that
produces a cleaner implementation.

A second clarification round the same day (§5 items 6-7) refined this
further, splitting what had been one combined "resolver ensures its own
data" behavior into two separate, more precise pieces:

- the **customer-facing query path is now purely read-only** — it never
  writes a row, under any circumstance (revised AA-2);
- the **D+1/D+7 windowing rule is reinstated, but only as a separate,
  explicit, idempotent operator action** — a button on the operator
  workspace that ensures exactly 1 available slot on D+1 and 3 on D+7
  exist, creating them within business hours (08:00-18:00) only when
  needed (new AA-9). This is the *only* write path in this feature; the
  query path (AA-2) never triggers it as a side effect.

A third clarification round (§5 items 8-9) deferred a full scheduling CRUD
to future work and identified a real content gap: no existing specialty
covers a customer who doesn't yet know what's wrong.

A fourth clarification round (§5 item 10) corrected how that gap should be
closed: "no specialty named" means the customer needs a **generalist**
professional (AA-3a) — a new seeded specialty of its own — not an
unfiltered search across the 3 diagnosis-specific specialties. This is the
one place this feature adds new reference data (via a small migration, not
a schema change) rather than only reading what already existed.

## 2. What already exists (verified against the real schema/code, not assumed)

- `content.qa_entries.dynamic_resolver` is an ORM-mapped, DB-seeded `text`
  column. It is currently **write-only** in the codebase — `knowledge/ingest.py`
  persists it from the seed/CRUD payload, but nothing in `ai/router.py`'s
  resolution path (`dynamic_pattern_result()`) ever reads it. Resolution
  today is entirely driven by `qa.dynamic_data_required` plus a
  `qa_dynamic_bindings` row (V2's generic table/filter/output-columns
  mechanism, `knowledge/dynamic_binding.py`). No `qa_dynamic_bindings` row
  exists for any `agenda` entry, so they all abstain
  (`DYNAMIC_DATA_UNAVAILABLE`) today — correctly, per D-028.
- The `scheduling` schema is real and seeded: `units`, `specialties`,
  `professionals`, `professional_specialties` (carries
  `fixed_price_cents`/`appointment_duration_minutes` per
  professional×specialty), `holidays`, `schedule_slots` (real
  `starts_at`/`ends_at timestamptz`, already `America/Sao_Paulo`-aware, with
  a `status` — `available`/etc.), and `scheduling.next_business_day(date)`
  (a real, reusable Saturday-is-a-business-day / Sunday-and-holiday-aware
  function). This feature's resolver builds on these directly.
- `scheduling.slot_offers`/`scheduling.available_offers`/
  `scheduling.ensure_demo_availability()` are the *existing* D+1/D+7-window
  materialization machinery — kept in the schema (harmless, unused) but this
  feature's query path does not depend on them (§5 resolution 2): they are
  only ever seeded once at container-init time and go stale. This feature's
  own D+1/D+7 seeding action (AA-9) reimplements the same windowing
  *concept* in Python as an explicit, idempotent, operator-triggered
  action — it does not call `ensure_demo_availability()` or write to
  `slot_offers` (those stay exactly as unused/dormant as before); it writes
  directly to `schedule_slots`, the same table the query path reads.
- `scheduling.appointments`/`appointment_events`, `identity.patients`/
  `consent_records`, and `billing.payments` also already exist (D-024,
  dormant) but are **out of scope** for this cycle (§6) — this feature never
  reads or writes any of those tables.

## 3. Confirmed outcomes

### AA-1 — Resolver allowlist, not a generic table binding

`dynamic_resolver = 'appointment_availability'` is resolved by a
server-side-allowlisted, named resolver — distinct from V2's generic
`qa_dynamic_bindings` table/filter/output-columns mechanism, which has no way
to express "compute the next available business day" or apply the
Saturday/Sunday/holiday rule. Only `appointment_availability` is implemented
by this cycle; every other `dynamic_resolver` value already present in seed
data (`price_lookup`, `payment_simulator`, `insurance_lookup`) remains
unresolved/abstaining, exactly as today — this cycle does not authorize them.

### AA-2 — Purely read-only query path

The resolver only ever `SELECT`s `scheduling.schedule_slots` (joined to
`specialties`/`professionals`/`professional_specialties`/`units`) for slots
with `starts_at` in the future relative to the real query time and
`status = 'available'`, computed fresh on every resolution — never a
pre-materialized, date-stamped `slot_offers` row that can go stale. **This
path never writes anything, under any circumstance** (revised 2026-08-18,
§5 item 6): no row in `schedule_slots`, `scheduling.appointments`,
`identity.*`, or `billing.*` is ever created, updated, or deleted by a
customer/operator query. If too few (or zero) future slots exist to answer,
the resolver aborts to the existing manual-fallback path (AA-8) — it never
generates data itself. Keeping the seed data populated is entirely AA-9's
job, a separate, explicit, operator-triggered action.

### AA-3 — Deterministic parameter extraction from the customer's message

The customer's own message text (the same text already selected as this
generation's context) is parsed by a small, non-LLM, deterministic keyword
matcher for: a specialty (matched against `scheduling.specialties.slug`/
`display_name`, the same vocabulary the knowledge base already uses), a
date/day phrase ("amanhã", "semana que vem", a weekday name), and a period
("manhã"/"tarde"). Date/period are optional — an unmatched one is simply not
filtered on. **Specialty is not optional in that same sense** (revised
2026-08-18, §5 item 10): "no specialty named" does not mean "search
unfiltered across every specialty" — it means the customer needs a
**generalist** (a non-specialized professional for an initial/triage
consultation), which is itself a distinct, seeded specialty (AA-3a). Every
resolution therefore always has exactly one specialty in effect — either an
explicitly matched one, or the generalist default. This is a new, small,
purpose-built component — V2's proven static-per-entry-filter alternative
was considered and rejected because the existing Q&A wording is generic,
not per-specialty (§5 resolution 1).

### AA-3a — A seeded generalist specialty, not an unfiltered fallback (added 2026-08-18)

A new `scheduling.specialties` row represents a non-specialized, generalist
professional for an initial/triage consultation — for a customer who
suspects cancer but doesn't yet know which specialty applies. Since all
data here is synthetic (Constitution Article VI), this is added the same
way the original 3 specialties were: seed rows, not a schema change. Needs:

- one new `scheduling.specialties` row (slug, display name, description);
- a small number of new `scheduling.professionals` rows tied to it via
  `professional_specialties` (mirroring the existing 3-professionals-per-
  specialty pattern), with their own price/duration — a "simple"
  consultation, priced and timed shorter than the specialist consultations;
- inserted via a new, additive, forward-only migration (not by editing
  `db/init/*.sql`, which stays frozen per V1 `plan.md` §1) — this is the
  one schema-adjacent change this feature makes; everything else about the
  `scheduling` schema's shape is still unchanged (`plan.md` §3).

`extract_parameters()` (AA-3) defaults to this specialty's slug whenever no
other specialty keyword matches — not to "no filter." The two "primeira
consulta" Q&A entries (`spec.md` §5 item 9) now correctly route here, for a
real reason (a real generalist professional exists to see them), not as a
side effect of an unfiltered query.

### AA-4 — Structured, timezone-aware evidence

The resolver's output carries enough structure (specialty, professional,
unit, start/end time in `America/Sao_Paulo`, price) for both the
customer-facing rendered text and the operator's evidence view — matching
the `retrieval_hit_id`-anchored evidence shape every other draft already
uses, not a bespoke parallel format.

### AA-5 — Deterministic template rendering, never LLM-composed

Matches D-028's existing precedent exactly for every other
`dynamic_data_required=true` case (§5 resolution 4): the final customer-
facing text is a fixed template with the resolved slots' fields substituted
in — never an LLM rewrite, paraphrase, or "made to sound more natural" pass.

### AA-6 — Explicit operator send is the only customer-visible outbound action

Unchanged V1 invariant (Constitution Article III). This resolver produces an
internal draft exactly like every other trigger; nothing about "real-looking"
availability data changes who is allowed to send it to a customer.

### AA-7 — Append-only audit with safe provenance

Every resolution (success or failure) is audited, following the existing
V2-6 pattern (`ai.dynamic_pattern_resolved` / `ai.dynamic_pattern_fallback`)
rather than inventing a parallel event shape — extended only as needed to
carry which specialty/date/period was matched, never a query string or
table/column name in a customer-facing field. AA-9's seed action gets its
own new event (it is not a resolution, so it does not reuse
`ai.dynamic_pattern_resolved`) — `scheduling.availability_seeded`, carrying
the operator id, `d1`/`d7` dates, and how many slots were created on each.

### AA-8 — Manual fallback for unavailable, empty, or failed data

Matches D-028's existing safety correction exactly: zero matching slots or a
resolution error must produce the *existing* `ABSTAIN`/
`DYNAMIC_DATA_UNAVAILABLE` path — never a fabricated slot, never an exposed
cause string, never a partial answer.

### AA-9 — Explicit, idempotent, operator-triggered D+1/D+7 seeding action (added 2026-08-18)

A button on the operator workspace ("aba operator" — the operator's own
page, not tied to any single conversation) triggers one idempotent backend
action:

1. Compute `d1 = scheduling.next_business_day(today + 1 day)` and
   `d7 = scheduling.next_business_day(today + 7 days)` — reusing the
   existing, already-correct SQL function (same single source of truth
   `plan.md` originally chose for the query path, before AA-2 was
   narrowed to read-only; this is the one place in the feature that still
   calls it, and only from this explicit action).
2. Count `schedule_slots` rows with `status = 'available'` and
   `starts_at`'s date equal to `d1` (call it `count_d1`), and likewise for
   `d7` (`count_d7`) — a flat count, not scoped to any one
   specialty/professional.
3. **If `count_d1 >= 1` and `count_d7 >= 3`: do nothing and report
   "já tem 4 vagas disponíveis"** (the exact idempotent no-op case the
   human specified).
4. **Otherwise, create just enough new slots** — `max(0, 1 - count_d1)` on
   `d1`, `max(0, 3 - count_d7)` on `d7` — to reach exactly that target,
   each within business hours **08:00-18:00** `America/Sao_Paulo`, each a
   real `schedule_slots` row tied to a real seeded professional/specialty
   (reusing `professional_specialties.appointment_duration_minutes` for
   that professional, so `ends_at` is always correct), and report how many
   were created.
5. This was originally the *only* write path in this feature; AA-10 below
   (added in a later round the same day) adds a second, materially
   different one. The query path (AA-2) still never writes under any
   circumstance. This action is reachable only by an authenticated,
   assignment-independent operator action (not conversation-scoped — this
   button is not about any one customer), audited like every other
   operator action (AA-7).

### AA-10 — Simulated identity/payment-confirmation script (added 2026-08-18, Constitution Amendment 1.1.0)

A fixed, deterministic, scripted conversation flow that plays out after a
customer expresses intent to book one of the real slots AA-1..AA-9 showed
them. **This is the one place in this entire codebase where a
customer-visible message is sent without a per-message operator click** —
narrowly authorized by Constitution Amendment 1.1.0 (`DECISIONS.md`
D-031), strictly bounded to the fixed template messages below, never
LLM-composed, never LLM-rewritten. See §5 item 11 for the full
clarification record and the tradeoff the human was shown before choosing
this over the one-click-per-message alternative.

**Exact script** (human-specified verbatim; every "Operador:" line below
is sent automatically, no operator click — every "Cliente:" line is real
customer input the script reacts to):

```
Operador: "Agendamento realizado"
Operador: "Informe seu CPF - é uma simulação, informe qualquer número de 11 dígitos"
Cliente:  "Ah 123456a8910"                          [10 digits after stripping non-digits -> invalid]
Operador: "CPF inválido. Informe um número válido de 11 dígitos"
Cliente:  "tabom 123.456..789.10"                    [11 digits after stripping non-digits -> valid]
Operador: "CPF 123.456.789-10 confirmado"
Operador: "O valor da consulta é {valor real da especialidade discutida}"
Operador: "O valor foi pago? Responda sim ou não"
Cliente:  "Então, não paguei"                         [not "sim" -> re-ask, unlimited retries]
Operador: "O valor foi pago? Responda sim ou não"
Cliente:  "tabom simm paguei"                         ["sim" detected -> proceed]
Operador: "Verificando pagamento"
Operador: "Pagamento verificado"
Operador: "Agendamento realizado com sucesso. Há algo mais que posso ajudar?"
[flow ends]
```

Sub-mechanics:

- **CPF parsing** (Pydantic-validated): strip every non-digit character
  from the customer's message; valid iff exactly 11 digits remain —
  **never the real Brazilian CPF check-digit algorithm**, any 11-digit
  sequence passes, matching the human's explicit "é uma simulação"
  framing. Formats as `###.###.###-##` for the confirmation message.
- **Payment confirmation parsing**: case-insensitive regex for "sim"
  variants (`sim`, `Sim`, `SIM`, `simm`, ...) versus "não" variants
  (`não`, `nao`, `Não`, ...), word-boundary-aware so it works embedded in
  a full sentence ("Então, não paguei", "tabom simm paguei"). Only an
  affirmative match advances the flow; anything else (negative, unclear,
  no match, or an ambiguous message matching both) re-asks the identical
  question, with no retry limit.
- **Trigger**: deterministic keyword detection of booking intent in a
  customer message (e.g. "quero marcar", "pode agendar"), only considered
  while no script is already in progress for that conversation.
- **Price**: the real `professional_specialties.fixed_price_cents` for
  whichever specialty the customer's most recent resolved
  `appointment_availability` generation (AA-1..AA-9) was about — reuses
  data this feature already reads, no new price source.
- **No real reservation, payment, or identity persistence**: the CPF and
  the payment yes/no answer are used only to decide the next scripted
  message and are never written to any table — not `identity.patients`,
  not a new table, nowhere (Constitution Article VI). No
  `scheduling.appointments`/`schedule_slots.status` row is created or
  changed either — "reserva" (actually holding a slot) is explicitly
  **not** handled by this script (still deferred, `spec.md` §6) — this is
  a conversational simulation only, not a functional booking system.
- **Transient flow-position state**: which step a conversation is on
  *is* persisted server-side (so an operator's page reload mid-flow
  doesn't lose it) but as ordinary mutable relational state, not an
  audited durable fact — see `data-model.md` §7.

## 4. Acceptance outcomes to develop into executable tests

1. A customer/operator query the resolver can serve produces real slots from
   `scheduling.schedule_slots`, rendered deterministically (no LLM rewrite)
   with `America/Sao_Paulo` times, price, and a "(simulação)" marker.
2. A query naming a real specialty only returns slots for that specialty; a
   query naming no specialty (or explicitly asking for a generalist)
   returns only the seeded generalist specialty's slots — never a mix
   across the 3 diagnosis-specific specialties, and never zero results
   just because nothing specific was named.
3. A query for a day that resolves to Sunday or a holiday is silently
   redirected to the correct next business day by the existing
   `scheduling.next_business_day()` — the customer-facing text reflects the
   actual resolved date, never a raw "Sunday" slot.
4. The query path (AA-2) never writes to `schedule_slots` or any other
   table under any circumstance — including when it finds zero matching
   slots — proven by a negative test, not just by absence of a write in the
   demo's happy path.
5. The seed action (AA-9): starting from zero seeded slots on `d1`/`d7`,
   one call creates exactly 1 slot on `d1` and 3 on `d7`, all within
   08:00-18:00 `America/Sao_Paulo`. A second immediate call makes zero
   further writes and reports "já tem 4 vagas disponíveis" (idempotency).
   A partial state (e.g. `d1` already has 1, `d7` has only 1 of 3) results
   in creating exactly the 2 missing `d7` slots and none on `d1`.
6. Zero matching slots (e.g., a specialty with no seeded professional, or a
   date filter that matches nothing) aborts to the existing `ABSTAIN`/
   `DYNAMIC_DATA_UNAVAILABLE` path with no internal cause exposed, mirroring
   D-028's existing negative test.
7. No `scheduling.appointments`/`identity.*`/`billing.*` row is ever
   created, updated, or read by this feature — a negative test proves this
   structurally (no import/call path exists), not just "the demo happens not
   to trigger it."
8. `price_lookup`/`payment_simulator`/`insurance_lookup` (and any other
   `dynamic_resolver` value this cycle does not implement) continue to
   abstain exactly as they do today — a regression test proves this cycle
   did not accidentally widen the allowlist.
9. The seed button/endpoint (AA-9) requires the same authenticated-operator
   check every other operator action already requires; no anonymous or
   customer-token credential can reach it. It never creates a slot outside
   08:00-18:00, and never creates more than the exact number needed to
   reach 1×`d1`/3×`d7` — a negative test proves it cannot be made to
   over-create by calling it repeatedly or concurrently.
10. The booking script (AA-10): the exact scripted sequence in AA-10's
    example plays out verbatim, including both retry branches (invalid
    CPF once, then valid; "não" once, then "sim") — the happy path is the
    expectation, but both retry branches must also work correctly, per
    the human's own framing ("a expectativa é o fluxo de sucesso, com
    capacidade de lidar com as variações citadas").
11. The booking script's CPF check accepts any exactly-11-digit sequence
    extracted from the customer's message (ignoring punctuation/letters
    mixed in) and rejects anything else — never the real CPF check-digit
    algorithm.
12. The booking script's payment question is re-asked, unchanged, for any
    reply that isn't recognized as an affirmative "sim" variant — including
    an explicit "não", gibberish, or a reply matching neither — with no
    retry limit, never advancing on anything but a clear "sim".
13. Neither the CPF nor the payment yes/no answer is ever persisted to any
    table — a negative test proves this structurally (no column/table
    exists to hold either raw value) — only the current script *step*
    (an enum-like marker, not the customer's actual input) is persisted.
14. **The autonomous-send mechanism this script uses is provably scoped to
    only this one flow** — a negative test proves no other message path in
    the system can be triggered without an authenticated operator action
    (re-confirming Article III holds everywhere else, Constitution
    Amendment 1.1.0's own bound). Every autonomously-sent message is
    audited with a distinct event type that a reviewer can use to tell it
    apart from an operator-sent one at a glance.
15. All V1/V2/V3 acceptance outcomes this spec's baseline lists as
    preserved still pass unmodified (spot-check, not a full rerun).

## 5. Decisions resolved with the human (2026-08-18)

1. **Parameter derivation: deterministic keyword extraction from the
   customer's message** (not V2's static-per-entry-filter pattern, not an
   unfiltered "show everything" fallback). Chosen because the existing Q&A
   wording is generic (no specialty named per entry); a small non-LLM parser
   over a known, limited vocabulary (specialty names, a handful of date/
   period phrases) stays deterministic and testable without inventing an NLU
   dependency. See AA-3.
2. **No freshness machinery tied to the *query* path — the existing
   `slot_offers`/`available_offers`/`ensure_demo_availability()`
   D+1/D+7-window materialization stays unused.** The query path only ever
   reads whatever is actually in `schedule_slots` (§5 item 6 below narrows
   this further: it never writes at all). See AA-2, AA-8.
3. **Scope of the existing 14 `agenda` Q&A entries: logic over preserving
   exact chunks.** The human explicitly authorized evaluating each entry
   against the new resolver's actual logic and keeping only what is
   necessary — entries may be edited, deleted, or newly created; the
   original QA-011..QA-024 identifiers/wording are not a constraint.
   `plan.md`/`tasks.md` will record the final entry set and, for each one
   removed or added, why. Booking/hold/identity/payment-confirmation content
   (matching what was QA-016/021/022/023/024) remains out of this feature's
   scope regardless of exact final numbering (§6).
4. **Deterministic, template-rendered response — confirmed, no LLM
   rewrite**, matching D-028's existing precedent for every
   `dynamic_data_required=true` case. See AA-5.
5. **Feature/folder naming confirmed as-is**: `004-dynamic-appointment-
   availability`, following the existing sequential `00N-` numbering,
   deliberately not `004-v4-...` since `ROADMAP.md`'s own "V4" already names
   a different, unrelated feature (N3 governed autonomy).

**Second round (2026-08-18, same day):**

6. **The query path must be purely read-only — no on-demand slot
   generation as a side effect of a customer/operator query, at all.**
   Supersedes item 2 above's original framing (which still allowed the
   resolver itself to top up data). See revised AA-2.
7. **A new, explicit, idempotent operator action reinstates the D+1/D+7
   rule** — exactly 1 available slot on D+1 and 3 on D+7, created within
   08:00-18:00 only when short of that target, reporting "já tem 4 vagas
   disponíveis" when already sufficient. This is a genuinely new outcome
   (AA-9), not a revision of an existing one — the first clarification
   round's item 2 had disregarded D+1/D+7 windowing *entirely*; this round
   reinstates it, but scoped to one explicit, auditable, operator-only
   action rather than automatic behavior on the query path.

**Third round (2026-08-18, same day):**

8. **A full operator-facing CRUD screen for the `scheduling` schema was
   considered as an alternative to AA-9's single button** (create/edit/
   deactivate specialties, professionals, and individual slots, mirroring
   `/operator/knowledge`'s existing pattern) and **deliberately deferred as
   separate future work** (`ROADMAP.md`) — the button already covers this
   cycle's actual need; a full CRUD is real additional scope, not a small
   extension, and edges toward schedule-administration territory adjacent
   to the still-deferred booking feature.
9. **A real content gap: no existing Q&A entry covers a customer who
   suspects cancer but doesn't yet know which specialty applies.** All 3
   seeded specialties assume the customer already knows which one they
   need. Resolved with 2 new `agenda` Q&A entries (`plan.md` §8, authored
   verbatim) that deliberately name no specialty.

**Fourth round (2026-08-18, same day) — correction:**

10. **"No specialty named" means the customer needs a generalist, not an
    unfiltered search.** Superseding item 9's original framing (which
    routed an unmatched query across all 3 diagnosis-specific specialties
    indiscriminately): a customer who doesn't know what's wrong should see
    a non-specialized professional for an initial/triage consultation —
    which itself needed to be a real seeded specialty (AA-3a), not a
    behavior of the query. Since all data here is synthetic anyway
    (Constitution Article VI), the human explicitly authorized adding this
    as new seed data via a small migration — the one schema-adjacent
    change in this otherwise read/seed-existing-data-only feature.

**Fifth round (2026-08-18, same day) — a new, materially different
outcome:**

11. **A static, scripted simulation of the identity/payment/booking-
    confirmation flow was requested** — explicitly *not* real reservation
    (`spec.md` §6 still excludes actually holding/booking a slot), but a
    conversational simulation that asks for a CPF (format-only validated),
    shows the real price, and asks for payment confirmation, following an
    exact scripted sequence the human specified verbatim (AA-10).
12. **Whether each scripted message still requires an explicit operator
    click was raised as a first-class question**, because the human's
    first answer ("rodar automaticamente, sem clique por mensagem") would
    have been a direct conflict with Constitution Article III — the one
    invariant that has never had an exception across V1, V2, V3, or any
    N3/N4 autonomy discussion. The alternative (one-click-per-message via
    the existing quick-approve action, nearly as fast operationally, zero
    constitutional impact) was explained in full before asking again.
13. **The human, now informed of exactly what Article III protects and
    that no prior exception exists anywhere in this project, explicitly
    chose to authorize a narrow constitutional exception** rather than the
    zero-impact alternative — **Constitution Amendment 1.1.0**
    (`.specify/memory/constitution.md`, `DECISIONS.md` D-031). The
    exception is bound as tightly as the human's own request allows: only
    this one script's fixed templates, never LLM-composed, no real
    persistence of the booking/payment/identity data involved.
14. **Trigger, price source, and packaging were confirmed**: the script
    starts on deterministic detection of booking intent in a customer
    message (not an operator action); the displayed price reuses this
    feature's own already-seeded `professional_specialties` data for
    whichever specialty was being discussed; this outcome is added to the
    existing `004-dynamic-appointment-availability` package as an
    extension (not a new package), per the human's explicit choice.

## 6. Explicitly out of scope unless newly approved

- holding, reserving, confirming, rescheduling, or cancelling appointments
  — actually marking a `schedule_slots`/`scheduling.appointments` row as
  held/booked (`scheduling.appointments`/`appointment_events` writes) —
  unchanged from `ROADMAP.md`'s existing deferral; AA-10's script *talks
  about* a booking having happened, it never creates one;
- CPF, customer identity/profile *persistence*, consent capture
  (`identity.*` writes) — AA-10 *asks for and format-validates* a CPF but
  never stores it anywhere, which is a materially different, much
  narrower thing than this exclusion, still fully intact;
- payment *processing* (`billing.*`, the `payment_simulator` resolver,
  any real payment integration) — AA-10 *asks whether payment happened*
  and reacts to the answer, but never processes, verifies, or records a
  real payment; "Verificando pagamento"/"Pagamento verificado" are fixed
  strings, not a real check against anything;
- price lookup (`price_lookup` resolver) and insurance lookup
  (`insurance_lookup` resolver) — structurally similar read-only patterns,
  but not authorized by this cycle; each would need its own explicit
  authorization the same way this feature just received one for AA-1..AA-9
  (AA-10's own price display reuses already-authorized seeded data, not
  the `price_lookup` resolver);
- any booking/hold/identity/payment-confirmation Q&A content describing
  behavior beyond AA-10's exact script (§5 item 3) — e.g. losing a
  protocol number, booking for a minor, booking for someone else, remain
  unimplemented and untouched;
- the seed action (AA-9) creating/counting slots for any specialty other
  than "however many happen to exist" — it is a flat, specialty-agnostic
  count, not a per-specialty guarantee (that distinction is deliberate, not
  an oversight — see `plan.md`);
- autonomous AI-to-customer send **outside AA-10's one narrowly-authorized
  script** — Constitution Amendment 1.1.0 is explicit that it does not
  extend to any other outbound message in the system; every other
  send path keeps the unmodified Article III rule;
- N3 governed autonomy/policy enforcement — unchanged V4 exclusion, and
  Amendment 1.1.0 explicitly does not set precedent for this;
- the specialist-escalation workflow — unchanged V5 exclusion;
- real patient data — unchanged Constitution Article VI exclusion.

## 7. Required next artifacts

- `plan.md` with the resolver's exact architecture (dispatch mechanism, the
  deterministic keyword-extraction vocabulary, audit event shape), the seed
  action's exact algorithm (AA-9), the new endpoint and operator-workspace
  button, the booking script's exact state machine and autonomous-send
  mechanism (AA-10), security, and testing decisions;
- `data-model.md` documenting **two** new migrations — AA-3a's data-only
  one (the seeded generalist specialty/professionals/professional_specialties
  rows) and AA-10's schema one (a transient flow-position column plus a
  marker distinguishing an autonomously-sent message from an
  operator-sent one) — and confirming no other change to the dormant
  `scheduling`/`identity`/`billing` tables' shape beyond the query path's
  ordinary reads and the two write paths' (AA-9, AA-10) documented inserts;
- a `contracts/openapi.yaml` delta for the new
  `POST /operator/scheduling/ensure-availability` endpoint (AA-9) — the
  query path itself and AA-10's script still need no contract change
  (AA-10 has no new endpoint of its own — it reacts to the existing
  customer-message endpoint — matching V2-6's no-new-route precedent);
- `tasks.md`, `acceptance.md`, and a cross-artifact `analysis.md` before any
  implementation, per `AGENTS.md`'s required SDD flow — `analysis.md`
  especially must re-verify AA-10's autonomous-send mechanism cannot leak
  into any other message path, given how exceptional it is.
