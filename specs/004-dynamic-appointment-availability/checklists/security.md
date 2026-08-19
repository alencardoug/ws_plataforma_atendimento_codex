# Security Checklist — Dynamic Appointment Availability

Extends `specs/003-v3-measured-n2/checklists/security.md` (itself extending
V1/V2's), which remains in force unchanged. New items only. Not yet
implemented — each item states the design requirement and where it will be
evidenced (`tasks.md` task IDs); check off only once the cited task lands
and its test passes. Revised 2026-08-18 alongside `plan.md`'s split into a
read-only query path and a separate operator-triggered seed action.

- [ ] The query path (`scheduling/availability.py`) is reachable only
  through the existing authenticated-operator, assignment-gated,
  effective-N2 draft/evidence-selection paths — no new authorization
  surface, no new route. `tasks.md` T050.
- [ ] **The query path can never write, under any circumstance** — no
  `insert(`/`update(`/`delete(`/`pg_insert(` construct anywhere in
  `scheduling/availability.py`, verified structurally, and it never
  imports `scheduling/seeding.py`. `tasks.md` T030/T031,
  `acceptance.md` §C.
- [ ] No raw/dynamic SQL is built from user, customer, or LLM-provided
  strings anywhere in `scheduling/availability.py` or
  `scheduling/seeding.py` — every query is hardcoded Python/SQLAlchemy;
  only *values* (a matched specialty id, a computed date) are
  parameterized. `tasks.md` T020/T031/T040.
- [ ] The seed endpoint (`POST /operator/scheduling/ensure-availability`)
  requires `CurrentOperator` authentication; an anonymous or
  customer-token credential gets `401`. It is deliberately not
  conversation/assignment-scoped — any authenticated operator may call it.
  `tasks.md` T042, `acceptance.md` §I.
- [ ] `scheduling/seeding.py`'s `create_slots_on()` can only `INSERT ...
  ON CONFLICT DO NOTHING` — it cannot update an existing slot's `status`
  or delete a row, and is reachable only through the one gated endpoint,
  never directly from a customer-originated request, never automatically.
  `tasks.md` T040/T042.
- [ ] The seed action can never create more than the exact number needed
  to reach `1×D+1`/`3×D+7`, and never outside 08:00-18:00 — verified by a
  test that calls it repeatedly and concurrently and asserts the final
  count never exceeds target. `tasks.md` T041, `acceptance.md` §D.4/§I.3.
- [ ] No import of `scheduling.appointments`/`appointment_events`,
  `identity.*`, or `billing.*` anywhere in `scheduling/models.py`,
  `scheduling/availability.py`, or `scheduling/seeding.py` — verified
  structurally (module introspection), not just behaviorally.
  `tasks.md` T010, `acceptance.md` §G.
- [ ] The resolved answer's `model` is always `"not-applicable"` — no LLM
  call, no LLM rewrite, for a resolved `appointment_availability` result
  (matches D-028's existing guarantee for every `dynamic_data_required=true`
  case). `tasks.md` T031, `acceptance.md` §A.2.
- [ ] A Q&A entry with `dynamic_resolver` set to a name this cycle does not
  implement (`price_lookup`/`payment_simulator`/`insurance_lookup`) cannot
  resolve through this feature's dispatch table — it falls through to the
  existing generic path, which safely aborts (no `qa_dynamic_bindings` row
  exists for them). `tasks.md` T052, `acceptance.md` §H.
- [ ] The failure-path `cause` string (audit-only, never customer-facing)
  never contains a raw SQL fragment or full query — only structured,
  bounded diagnostic values (matched/unmatched parameters), matching
  D-028's existing precedent. `tasks.md` T030/T031.
- [ ] The new generalist-specialty migration (AA-3a) is purely additive
  `INSERT`s into already-existing tables with hardcoded, fixed values —
  no user/request input reaches it, it runs once via Alembic (not a
  runtime code path an attacker could re-trigger), and it does not modify
  or delete any existing row. `tasks.md` T009, `acceptance.md` §0.
