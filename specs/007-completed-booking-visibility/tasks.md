# Tasks: Completed Booking Visibility

Governing: `spec.md`, `plan.md`, `data-model.md`.

## Phase 1 — Migrations and models

- **T1.** `20260820_0001_v7_appointment_bookings.py` — create
  `scheduling.appointment_bookings` (data-model.md §1).
- **T2.** `20260820_0002_v7_guided_booking_selected_offer.py` — add
  `conversations.guided_booking_selected_offer_id` (data-model.md §2).
- **T3.** `AppointmentBooking` ORM class in `scheduling/models.py`.
- **T4.** `Conversation.guided_booking_selected_offer_id` in
  `infrastructure/models.py`.

## Phase 2 — Write triggers

- **T5.** `record_appointment_booking()` in `scheduling/availability.py`
  (plan.md §4).
- **T6.** `interpret_slot_choice()` sets
  `conversation.guided_booking_selected_offer_id` on both the ordinal- and
  embedding-match return paths (plan.md §2).
- **T7.** `interpret_payment_reply()` calls `record_appointment_booking()`
  and clears the column at its `GUIDED_BOOKING_COMPLETE` return (BS-2,
  plan.md §4).
- **T8.** One additive call to `record_appointment_booking()` in
  `booking_script/service.py`, immediately before line 173's
  `send_scripted_message(..., "Agendamento realizado com sucesso...")`
  (BS-3, plan.md §4).

## Phase 3 — Read-side fields

- **T9.** `booking_summary_dict()`/`render_booking_summary_line()` in
  `scheduling/availability.py` (plan.md §5) — fixed-template rendering,
  full detail vs. specialty-only.
- **T10.** `booking_summary_fields()` in `operator_workspace/router.py`,
  spread into all 3 existing `automatic_draft_fields()` call sites (BS-5).
- **T11.** `customer_booking_summary_fields()` in
  `anonymous_access/router.py`, composed into `read_conversation()`
  alongside 008's `customer_draft_status()` (BS-6).

## Phase 4 — Backend tests

- **T12.** `record_appointment_booking()` inserts the correct row for both
  sources; audit payload shape (outcomes 1, 2).
- **T13.** `interpret_slot_choice()`/`interpret_payment_reply()` round-trip
  for `guided_booking_selected_offer_id` (set → consumed → cleared).
- **T14.** `booking_script/service.py` containment: diff is exactly the
  one additive call (outcome 7, mirroring
  `test_005_booking_script_containment.py`).
- **T15.** `appointment_bookings` never contains CPF/payment content
  (outcome 6) — schema-level check (no such column exists at all).
- **T16.** No-booking conversation shows no summary anywhere (outcome 8).

## Phase 5 — Frontend

- **T17.** `OperatorConversation` gains `booking_summary`; render in
  `OperatorPage`'s conversation detail (no scroll/placement constraint
  specified — near the conversation header/status, operator's choice of
  exact spot within that section).
- **T18.** `CustomerConversation` gains `booking_summary_line`; render in
  `CustomerPage` below "Enviar", above "Encerrar conversa" (spec.md BS-7
  exact position).
- **T19.** Frontend Vitest tests for both render points, including
  "absent when null" (outcome 8) and no `sessionStorage` write introduced
  by this feature (outcome 5, static-code-level: `booking_summary_line`
  is never passed to `sessionStorage.setItem`).

## Phase 6 — Gates and convergence

- **T20.** Backend `pytest`/`ruff`/`mypy`.
- **T21.** Frontend lint/typecheck/Vitest/build.
- **T22.** New `frontend/e2e/v7.spec.ts` (continuing the v4/v5/v8/v9
  package-number convention) — full GB flow to completion, both summary
  lines appear; requires a credential-backed Compose stack (deferred per
  the human's 2026-08-20 batching decision, same as 006/008/009).
- **T23.** Author `acceptance.md`/`analysis.md`; update
  `PROJECT_STATE.md`/`ROADMAP.md`/`DECISIONS.md` once the batch closes.
