# Analysis: Completed Booking Visibility

## Cross-artifact convergence review (2026-08-20)

- `spec.md` §7's data-model summary ("no change to `AppointmentOfferPresentation`
  or `conversation.booking_script_step`") was re-verified accurate — this
  package indeed changes neither. It did not, however, fully specify how
  BS-2's "source from the specific `AppointmentOfferPresentation` row"
  requirement could be met, since nothing durable tracked which offer was
  chosen between GB-2 (slot choice) and BS-2's own trigger (payment
  confirmation, several messages later). `plan.md` §2 identifies this gap
  by direct inspection (`interpret_slot_choice()`'s return value was never
  persisted anywhere) and resolves it with one new transient column,
  `conversations.guided_booking_selected_offer_id`, mirroring the existing
  `guided_booking_pending_text`/`_trigger` pattern exactly. This is the
  kind of plan.md-level elaboration `AGENTS.md`'s authority order expects
  (spec.md sets the requirement; plan.md/data-model.md work out the
  mechanics) — not a silent deviation from spec.md, and not a change to
  spec.md's own BS-1..BS-7 requirements.
- `plan.md` §4's `record_appointment_booking()` design (shared helper in
  `scheduling/availability.py`, chosen specifically to avoid
  `booking_script/service.py` importing from `guided_booking.py`) was
  implemented exactly as planned, and the existing
  `test_005_booking_script_containment.py` suite (unmodified, 6/6 still
  passing) independently confirms the containment boundary it was designed
  to preserve held.
- `tasks.md` T1-T11 (migrations, models, write triggers, read-side fields)
  are complete, matching plan.md's design. T12-T16 (backend tests) are
  complete: 2 new DB-dependent integration tests (written, not executed —
  see acceptance.md) plus 5 new DB-independent tests (executed, passing).
  T17-T19 (frontend) are complete and passing (24/24 Vitest). T20-T21
  (gates) are complete and passing. T22 (`v7.spec.ts`) is written, not
  executed. T23 (this document) is in progress, pending the deferred
  batch run.
- No spec/plan/tasks contradiction found beyond the gap plan.md §2 itself
  identified and resolved. No documentation drift requiring a repair to a
  higher-authority artifact was found.

## Regression risk assessment

The two write-trigger changes are each additive and narrowly scoped:
`interpret_slot_choice()` gains two one-line assignments (no changed
return value or control flow); `interpret_payment_reply()` gains one
`if`-guarded block before its existing `return`; `booking_script/service.py`
gains one `if`-guarded block before its existing final
`send_scripted_message` call. Neither existing function's signature,
return value, or externally-observable behavior (draft text, trigger
value, scripted message text) changes. The two new read-side fields are
purely additive compositions on top of already-shared projection
functions, matching `automatic_draft_fields()`'s own established pattern
— no existing field is removed, renamed, or reshaped.

The one genuinely new piece of state (`guided_booking_selected_offer_id`)
is scoped to a single flow's lifetime (set at slot-choice, cleared at
payment-confirmation) and only ever read at the one call site that
consumes and clears it — plan.md §7 documents why a stale value from an
earlier "voltar" cannot leak into a later booking record.

## Verdict

**CONDITIONAL GO** — implementation matches spec/plan with no unresolved
drift; the one necessary plan-level elaboration (plan.md §2) is documented
with its rationale, not silently invented. The credential-backed batch run
(2026-08-20, see `acceptance.md`) confirms every gate passes against a
real DB, real embeddings, and real LLM calls **except** `v7.spec.ts`'s own
full GB-completion scenario, which is proven correct in isolation but
still fails intermittently when run as part of the full Playwright suite
— see `acceptance.md`'s closure section for the full investigation (three
real test bugs found and fixed, a major environmental discovery about
`smoke_ingestion_changed.py` corrupting shared-DB embeddings, and one
remaining unexplained case). This package is **not yet DONE** (D-037) —
finalizing to GO requires either root-causing and fixing the remaining
intermittency, or a human decision to accept the isolated-run evidence as
sufficient. 006/008/009 are unaffected and remain DONE — see their own
`acceptance.md`/`analysis.md`.
