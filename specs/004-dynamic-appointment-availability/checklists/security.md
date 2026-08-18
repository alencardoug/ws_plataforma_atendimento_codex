# Security Checklist — Dynamic Appointment Availability

Extends `specs/003-v3-measured-n2/checklists/security.md` (itself extending
V1/V2's), which remains in force unchanged. New items only. Not yet
implemented — each item states the design requirement and where it will be
evidenced (`tasks.md` task IDs); check off only once the cited task lands
and its test passes.

- [ ] The resolver is reachable only through the existing authenticated-
  operator, assignment-gated, effective-N2 draft/evidence-selection paths —
  no new authorization surface, no new route. `tasks.md` T040.
- [ ] No raw/dynamic SQL is built from user, customer, or LLM-provided
  strings anywhere in `scheduling/availability.py` — every query is
  hardcoded Python/SQLAlchemy; only *values* (a matched specialty id, a
  computed date) are parameterized. `tasks.md` T020/T031.
- [ ] `ensure_near_future_slots()` can only `INSERT ... ON CONFLICT DO
  NOTHING` — it cannot update an existing slot's `status` or delete a row,
  and is reachable only as a side effect of an operator-triggered draft
  resolution, never directly from a customer-originated request.
  `tasks.md` T030.
- [ ] No import of `scheduling.appointments`/`appointment_events`,
  `identity.*`, or `billing.*` anywhere in the new module — verified
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
  exists for them). `tasks.md` T042, `acceptance.md` §H.
- [ ] The failure-path `cause` string (audit-only, never customer-facing)
  never contains a raw SQL fragment or full query — only structured,
  bounded diagnostic values (matched/unmatched parameters), matching
  D-028's existing precedent. `tasks.md` T031/T032.
