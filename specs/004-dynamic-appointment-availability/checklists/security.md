# Security Checklist — Dynamic Appointment Availability

Extends `specs/003-v3-measured-n2/checklists/security.md` (itself extending
V1/V2's), which remains in force unchanged. New items only. Finalized
against the implemented state on 2026-08-19; every checked item has both
code and executable evidence. Revised 2026-08-18 three times: for `plan.md`'s split
into a read-only query path and a separate operator-triggered seed action;
for the generalist specialty (AA-3a); for the booking script (AA-10) — the
one item group below (marked ⚠) verifies the project's first-ever
exception to Constitution Article III, and gets correspondingly more
scrutiny than every other item here. Revised again 2026-08-19 for T008 (the
`scheduling`-schema-creation migration found necessary during the post-V3
production sync — `spec.md` §2 correction).

- [x] The query path (`scheduling/availability.py`) is reachable only
  through the existing authenticated-operator, assignment-gated,
  effective-N2 draft/evidence-selection paths — no new authorization
  surface, no new route. `tasks.md` T050.
- [x] **The query path can never write, under any circumstance** — no
  `insert(`/`update(`/`delete(`/`pg_insert(` construct anywhere in
  `scheduling/availability.py`, verified structurally, and it never
  imports `scheduling/seeding.py`. `tasks.md` T030/T031,
  `acceptance.md` §C.
- [x] No raw/dynamic SQL is built from user, customer, or LLM-provided
  strings anywhere in `scheduling/availability.py` or
  `scheduling/seeding.py` — every query is hardcoded Python/SQLAlchemy;
  only *values* (a matched specialty id, a computed date) are
  parameterized. `tasks.md` T020/T031/T040.
- [x] The seed endpoint (`POST /operator/scheduling/ensure-availability`)
  requires `CurrentOperator` authentication; an anonymous or
  customer-token credential gets `401`. It is deliberately not
  conversation/assignment-scoped — any authenticated operator may call it.
  `tasks.md` T042, `acceptance.md` §I.
- [x] `scheduling/seeding.py`'s `create_slots_on()` can only `INSERT ...
  ON CONFLICT DO NOTHING` — it cannot update an existing slot's `status`
  or delete a row, and is reachable only through the one gated endpoint,
  never directly from a customer-originated request, never automatically.
  `tasks.md` T040/T042.
- [x] The seed action can never create more than the exact number needed
  to reach `1×D+1`/`3×D+7`, and never outside 08:00-18:00 — verified by a
  test that calls it repeatedly and concurrently and asserts the final
  count never exceeds target. `tasks.md` T041, `acceptance.md` §D.4/§I.3.
- [x] No import of `scheduling.appointments`/`appointment_events`,
  `identity.*`, or `billing.*` anywhere in `scheduling/models.py`,
  `scheduling/availability.py`, or `scheduling/seeding.py` — verified
  structurally (module introspection), not just behaviorally.
  `tasks.md` T010, `acceptance.md` §G.
- [x] The resolved answer's `model` is always `"not-applicable"` — no LLM
  call, no LLM rewrite, for a resolved `appointment_availability` result
  (matches D-028's existing guarantee for every `dynamic_data_required=true`
  case). `tasks.md` T031, `acceptance.md` §A.2.
- [x] A Q&A entry with `dynamic_resolver` set to a name this cycle does not
  implement (`price_lookup`/`payment_simulator`/`insurance_lookup`) cannot
  resolve through this feature's dispatch table — it falls through to the
  existing generic path, which safely aborts (no `qa_dynamic_bindings` row
  exists for them). `tasks.md` T052, `acceptance.md` §H.
- [x] The failure-path `cause` string (audit-only, never customer-facing)
  never contains a raw SQL fragment or full query — only structured,
  bounded diagnostic values (matched/unmatched parameters), matching
  D-028's existing precedent. `tasks.md` T030/T031.
- [x] The schema-creation migration (T008, correction) creates only the
  `scheduling` schema and only the tables/enum/function this feature
  actually uses — no `identity.*`/`billing.*`/`governance.*`/
  `appointments`/`appointment_events`/`slot_offers`/`available_offers`
  object, verified structurally by inspecting the migration's DDL, not
  just by absence of a call elsewhere. `tasks.md` T008, `acceptance.md` §0.
- [x] The new generalist-specialty migration (AA-3a) is purely additive
  `INSERT`s into the tables T008's migration just created, with hardcoded,
  fixed values — no user/request input reaches it, it runs once via
  Alembic (not a runtime code path an attacker could re-trigger), and it
  does not modify or delete any existing row. `tasks.md` T009,
  `acceptance.md` §0.

**⚠ AA-10 — the Constitution Article III exception (Amendment 1.1.0,
`DECISIONS.md` D-031). Every item below exists to keep this exception
exactly as narrow as the amendment states, no wider.**

- [x] `send_scripted_message()` is the *only* function in the codebase
  reachable without an authenticated-operator dependency that can create a
  customer-visible `Message`. A structural test enumerates every other
  `Message(author_type="OPERATOR", ...)` construction site and confirms
  each is gated by `CurrentOperator` or equivalent.
  `tasks.md` T096, `acceptance.md` §O.1-2.
- [x] `send_scripted_message()` is called only from
  `advance_booking_script()`, which is called only from
  `send_customer_message()` — not the typing-heartbeat endpoint, not any
  GET/poll path, not any operator-authenticated endpoint.
  `tasks.md` T093/T094, `acceptance.md` §O.4.
- [x] Every message body `send_scripted_message()` sends is a literal
  string from `spec.md` AA-10's fixed script, interpolated only with this
  feature's own data (formatted CPF, seeded price) — never raw customer
  text, never LLM output (no LLM/embedding provider is imported anywhere
  in `booking_script/`). `tasks.md` T093, `acceptance.md` §L.4.
- [x] `extract_cpf()` never implements the real Brazilian CPF check-digit
  algorithm — digit-count-only, matching the human's explicit "é uma
  simulação" instruction; a CPF that would fail real validation but has
  exactly 11 digits still passes here. `tasks.md` T091/T092,
  `acceptance.md` §M.1.
- [x] The raw CPF and the raw/parsed payment answer are never persisted
  as submitted: `persisted_customer_body()` replaces each sensitive
  customer `Message.body` with a fixed disclosure marker before insertion,
  and no audit payload/new table receives the raw value. The formatted CPF
  appears only in AA-10's required fixed confirmation output. Only
  `booking_script_step` (an enum-like position marker, `CHECK`-constrained
  at the database level to its two legal values) persists as flow state.
  Verified through the real HTTP smoke and direct DB assertions after a
  convergence finding exposed the old false-green test. `tasks.md`
  T095/T097/T082, `acceptance.md` §N.
- [x] No `scheduling.appointments`/`schedule_slots.status`/`identity.*`/
  `billing.*` write occurs anywhere in `booking_script/` — "Agendamento
  realizado" is a sentence, never a real state transition. Structurally
  reinforced further than planned: those tables don't even exist in this
  database (T008's schema-creation correction, `spec.md` §2), so a write
  is not just absent but impossible. `tasks.md` T093/T095,
  `acceptance.md` §N.3.
- [x] The script never starts for a conversation with no prior resolved
  `appointment_availability` generation — the trigger cannot fire out of
  context. `tasks.md` T093/T095, `acceptance.md` §O.5.
- [x] Every autonomously-sent message carries both
  `Message.autonomous_source = "booking_script"` and a
  `booking_script.autonomous_message_sent` audit event (payload excludes
  the message body, the raw CPF, and the raw payment reply) — either alone
  is a complete, queryable list of every message ever sent without an
  operator click. `tasks.md` T093/T097, `acceptance.md` §O.3.
- [x] **New item, found during implementation (`analysis.md` §16 finding
  1):** the pre-existing `messages_check` CHECK constraint required every
  `OPERATOR` message to carry a non-null `operator_id` — widened by
  migration `20260819_0004` with exactly one additional disjunct, gated
  on `autonomous_source='booking_script'`. A `NULL` `operator_id` on an
  `OPERATOR` message is therefore impossible at the database level for
  any other reason — this is a second, independent structural enforcement
  of the amendment's scope, not just the `autonomous_source` column
  itself. `data-model.md` §8, `tasks.md` T093.
