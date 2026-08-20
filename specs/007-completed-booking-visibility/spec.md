# Feature Specification: Completed Booking Visibility

**Feature ID:** `007-completed-booking-visibility`
**Status:** Draft — authorized for specification 2026-08-20
**Authorized for specification:** 2026-08-20 (human, this conversation),
registered 2026-08-19 in `ROADMAP.md`, refined 2026-08-20 with a
customer-facing addendum (same `ROADMAP.md` section)
**Scope:** once a booking flow (GB or AA-10) reaches its own completion
point, record what is actually known about it in a small, non-identifying
durable table, and surface it in both the operator's conversation view and
the customer's own tab (the latter session-only, never persisted). See §6
for the honesty limit this spec deliberately keeps: AA-10-only completions
cannot report the same level of detail GB completions can, because AA-10
itself never tracks a specific chosen slot.

## 1. Purpose

Today, direct inspection of `app/customer_care/scheduling/guided_booking.py`
and `app/customer_care/booking_script/service.py` confirms neither writes
anything to `scheduling.schedule_slots` (whose `status` enum already has an
unused `"booked"` value) or any other queryable "this conversation's
booking" fact. Two different structured traces exist, at two different
levels of detail, and neither is currently read back for display purposes:

- **GB** persists the *offered* set (up to 4 rows) via `005-dynamic-
  pricing-and-guided-booking`'s `AppointmentOfferPresentation` model
  (`infrastructure/models.py`), linked to the resolving `AIGeneration`, but
  **never records which one was ultimately selected** — that fact exists
  only as unstructured text inside the `GUIDED_SLOT_SELECTION`-triggered
  generation's `draft_text`.
- **AA-10** tracks even less: `_resolved_specialty_slug()`
  (`booking_script/service.py`) recovers only the *specialty* from the
  `ai.dynamic_pattern_resolved` audit event's payload
  (`{ai_generation_id, specialty_slug, slot_count}`) — there is no code
  path in `booking_script/service.py` that reads `AppointmentOfferPresentation`
  or any other slot-level data at all. AA-10's own completion is detectable
  only by finding the `Message` with `autonomous_source='booking_script'`
  whose body is the literal string `"Agendamento realizado com sucesso. Há
  algo mais que posso ajudar?"` (`service.py:173`) — and
  `conversation.booking_script_step` resets to `None` on completion, the
  **same value** as "never started," so that column alone cannot
  distinguish the two.

This asymmetry is real, not an oversight to paper over: GB's own
ordinal/embedding slot-choice step (005/GB-2) is exactly the mechanism that
makes rich detail possible; AA-10's trigger (`detect_booking_intent()` on a
raw customer message) never asks the customer to choose among the offered
slots at all. §6 makes explicit how this spec handles that gap rather than
inventing precision AA-10 doesn't have.

## 2. Definitions

- **Booking summary** — the record this feature adds: specialty
  (display name), professional (display name), unit (name), and the
  chosen slot's local start time — **when known** — plus
  `conversation_id`. Never CPF, never payment confirmation status, never
  raw customer text.
- **Operator booking record** — BS-1's new durable table row, queryable by
  `conversation_id`, written once per completed booking flow.
- **Customer booking line** — BS-4's session-only, non-persisted rendering
  of the same summary in the customer's own tab.
- Existing terms (`GUIDED_BOOKING_COMPLETE`, `AppointmentOfferPresentation`,
  `booking_script_step`, `send_scripted_message`, N1/N2, explicit operator
  send) are unchanged from 004/005 and `.specify/memory/constitution.md`.

## 3. Functional requirements — durable operator-facing record (BS)

### BS-1 — New table, non-identifying fields only, forward-only migration

A new `scheduling.appointment_bookings` table (new forward-only Alembic
migration, matching `20260819_0005_v5_appointment_offer_presentations.py`'s
exact shape: raw SQL DDL via `op.execute()`, `downgrade()` raises
`RuntimeError`):

```sql
CREATE TABLE scheduling.appointment_bookings (
    booking_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL REFERENCES customer_service.conversations(id),
    source text NOT NULL CHECK (source IN ('guided_booking','booking_script')),
    specialty_id uuid NOT NULL REFERENCES scheduling.specialties(specialty_id),
    professional_id uuid REFERENCES scheduling.professionals(professional_id),  -- nullable, see §6
    unit_id uuid REFERENCES scheduling.units(unit_id),                          -- nullable, see §6
    slot_starts_at timestamptz,                                                  -- nullable, see §6
    recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON scheduling.appointment_bookings (conversation_id);
```

**Explicitly excludes CPF and payment-confirmation status** — human
decision, 2026-08-20 — matching the non-retention rule AA-10/GB already
apply to the raw CPF/payment reply itself (005/GB-4). One row per
completed flow; never mutated after insert (matching
`AppointmentOfferPresentation`'s own "durable, append-only... never
mutated" precedent, 005 §7).

### BS-2 — Write trigger: GB path (rich detail)

In `guided_booking.py`, at the point `GUIDED_BOOKING_COMPLETE` is set (the
same call site that produces AA-10's identical final-success wording,
`interpret_payment_reply`), insert one `appointment_bookings` row with
`source='guided_booking'` and all four of `specialty_id`/`professional_id`/
`unit_id`/`slot_starts_at` populated — sourced from the specific
`AppointmentOfferPresentation` row GB-2's ordinal/embedding match already
identified as the customer's selection (that row's `slot_id` FK resolves
professional/unit/specialty/time directly). This is a small, additive
change entirely inside `guided_booking.py` — no change to
`booking_script/*`, no new coupling (005/GB-5's containment boundary is
unaffected).

### BS-3 — Write trigger: AA-10 path (specialty-only, honestly scoped)

In `booking_script/service.py`, at the exact point the autonomous
completion message is sent (`service.py:173`, inside
`send_scripted_message`'s own call for the final step), insert one
`appointment_bookings` row with `source='booking_script'`,
`specialty_id` resolved via the existing `_resolved_specialty_slug()`
helper, and `professional_id`/`unit_id`/`slot_starts_at` left `NULL` —
**AA-10 has no structured record of which specific slot the customer
meant** (§1), so this row does not fabricate one. This is the one place
this feature modifies `booking_script/service.py` itself: a single
additive insert call at an already-existing, unchanged completion point —
it does not touch `send_scripted_message`'s own signature, does not add a
new autonomous-send trigger, and does not change what gets sent to the
customer or when (Constitution Amendment 1.1.0's boundary is unaffected;
this is a DB write that happens *after* the already-authorized message is
already queued, not a new send-authority decision).

### BS-4 — Audit event

Both write paths (BS-2/BS-3) emit one `scheduling.booking_recorded` audit
event (`record_event(...)`, matching the existing `scheduling.*` namespace
convention — `scheduling.availability_seeded` precedent), payload:
`{conversation_id, source, specialty_slug, has_slot_detail: bool}`. Never
includes the completion message's own body text (matching
`booking_script.autonomous_message_sent`'s existing documented rule in
`docs/architecture/EVENT_CATALOG.md`: "never the sent message's own
body").

### BS-5 — Operator-facing read: `customer_projection()`'s existing extension pattern

A new computed field (not stored redundantly — read fresh from
`appointment_bookings` each time, matching how `is_customer_typing`/
`automatic_draft_eligible` are already computed on the fly rather than
persisted) is added to the operator conversation detail response, via the
same "compose on top of `customer_projection()`" pattern
`automatic_draft_fields()` already establishes
(`operator_workspace/router.py`) — not by editing `customer_projection()`
itself, since that function is shared with the public/customer router
(§4/BS-6 handles the customer side separately, deliberately not through
this shared function, to keep the "session-only, never persisted"
customer-side promise structurally distinct from this durable,
operator-side field).

## 4. Functional requirements — customer-facing line (BS, cont'd)

### BS-6 — Customer-facing rendering: computed fresh, never persisted, never client-cached beyond the tab session

**Confirmed 2026-08-20 (human, this conversation).** `GET
/public/conversations/{id}}` gains the same kind of computed-only field as
BS-5, added directly in `anonymous_access/router.py` (not inside
`customer_projection()` itself, matching BS-5's own separation) — read
fresh from `appointment_bookings` by `conversation_id` on every poll (the
existing 2-second `CustomerPage` poll, `frontend/src/main.tsx`, already
refetches the full conversation — no new endpoint or poll needed, same
free-ride precedent already confirmed for `008-customer-facing-draft-
status`'s generic cue). **Nothing new is written to `sessionStorage` or any
other client-side store for this field** — it is derived purely from the
already-fetched response each render. This already satisfies "loses the
information when the session/conversation ends" for free: `submitSurvey`/
`skipSurvey` (`main.tsx`) already clear `conversation_id`/
`conversation_token` from `sessionStorage` at exactly that point, and a
closed tab has no `sessionStorage` at all — once the client can no longer
address the conversation, it can no longer render anything derived from
it, with no extra cleanup code required.

### BS-7 — Placement and rendering

Rendered in `CustomerPage`'s in-chat view, directly below the message
form's "Enviar" button and above the "Encerrar conversa" button/prompt
(exact JSX position: after the existing `<form>` block, before the
`confirmingClose`/`CloseConfirmPrompt` block) — matching the human's own
specified placement (2026-08-20). Rendering text: a single line,
Python-rendered server-side (not LLM-composed — matches AA-2/PL-3's
existing "fixed template, never LLM paraphrase" precedent), e.g.
`"Oncologia geral (triagem) — Dra. Renata Silveira (simulação), Unidade
Central (simulação), quinta-feira 27/08 às 08:00 (America/São_Paulo)"`
when full detail is available (BS-2/GB path), or a shorter specialty-only
line (e.g. `"Consulta de Oncologia geral (triagem) confirmada
(simulação)."`) when only BS-3/AA-10-path data exists — never a
placeholder implying a specific time that wasn't actually chosen.

## 5. What this cycle does **not** authorize

- Any extension of Constitution Amendment 1.1.0 — BS-3's one insert call
  happens after AA-10's existing authorized send, does not add a new
  autonomous-send trigger or condition, and does not change
  `send_scripted_message`'s own signature or call sites.
- Real booking, holds, or `ScheduleSlot.status` transitions —
  `appointment_bookings` is a separate, additive record; this cycle does
  **not** change any `schedule_slots.status` value (the unused `"booked"`
  enum value stays unused) — reusing that column would conflate "a booking
  was simulated" with "this slot is actually unavailable," which is out of
  scope and would need its own analysis of every existing
  `resolve_appointment_availability` query's `status = 'available'` filter.
- CPF or payment-confirmation persistence in any form — BS-1 explicitly
  excludes both fields; this does not relax AA-10/GB's existing
  non-retention rule anywhere else.
- Editing or backfilling `appointment_bookings` for conversations that
  completed a booking flow before this feature existed — no historical
  backfill, no read of old message text to reconstruct past bookings.
- Extending AA-10 itself to track a specific chosen slot — BS-3's
  specialty-only scoping is a deliberate honesty limit (§1), not a gap
  this cycle closes; doing so would mean changing AA-10's own
  conversation flow (adding a slot-choice step to the one
  constitutionally-exceptional autonomous-send script), which is
  explicitly out of scope without its own separate human decision.

## 6. The honesty limit (restated)

`appointment_bookings.professional_id`/`unit_id`/`slot_starts_at` are
nullable specifically because BS-3/AA-10-sourced rows cannot populate them
truthfully. Any future feature that wants every booking to carry full
slot-level detail must first give AA-10 (or a successor mechanism) an
actual slot-selection step — a materially larger, separately-authorized
change to a constitutionally-exceptional script, not something this
cycle's read-side visibility work does implicitly.

## 7. Data model impact (elaborated in `data-model.md`)

- One new table, `scheduling.appointment_bookings` (BS-1) — forward-only
  migration, four nullable-where-honest columns, one FK index.
- No change to `scheduling.schedule_slots`, `scheduling.holidays`,
  `AppointmentOfferPresentation`, or `conversation.booking_script_step`.
- No change to `customer_projection()`'s own shared shape — both new
  read-side fields (BS-5 operator, BS-6 customer) are composed by their
  respective routers on top of it, matching the existing
  `automatic_draft_fields()` precedent exactly.
- One new audit event, `scheduling.booking_recorded` (BS-4),
  documented in `docs/architecture/EVENT_CATALOG.md`.

## 8. Acceptance outcomes to develop into executable tests

1. After a GB flow reaches `GUIDED_BOOKING_COMPLETE`, one
   `appointment_bookings` row exists for that `conversation_id` with
   `source='guided_booking'` and all four detail fields populated,
   matching the specific offer GB-2 selected (not just any offered slot).
2. After AA-10's own autonomous script completes, one
   `appointment_bookings` row exists with `source='booking_script'`,
   `specialty_id` populated, and `professional_id`/`unit_id`/
   `slot_starts_at` all `NULL`.
3. The operator's conversation detail view shows the booking summary line
   (full or specialty-only, matching which row exists) without needing to
   scroll back through the chat transcript.
4. The customer's own tab shows the same summary line, in the specified
   position (below "Enviar", above "Encerrar conversa"), within the same
   poll cycle the operator's view would show it.
5. Closing the browser tab (clearing `sessionStorage`) and reopening
   `/customer` fresh shows the landing screen (no `conversation_id`) — the
   booking line is not recoverable outside the original tab session,
   confirmed by inspecting `sessionStorage`/network calls, not just visual
   absence.
6. `appointment_bookings` never contains a CPF digit string or any
   payment-confirmation boolean/text — verified by a direct schema/content
   check, not just absence from the ORM model.
7. `booking_script/service.py`'s diff for this feature is exactly one
   additive insert call at the existing completion point — no change to
   `send_scripted_message`'s signature, `booking_script_step` handling, or
   any other existing line — verified the same way 005's
   `test_005_booking_script_containment.py` verified D-033's own narrow,
   disclosed exception.
8. A conversation with no completed booking flow at all shows no booking
   summary anywhere (operator or customer) — no empty-state text implying
   one exists.
9. The full pre-existing `smoke_*` suite and `v1/v2/v3/v4/v5` Playwright
   suite continue passing unmodified.

## 9. Decisions resolved with the human (2026-08-20)

1. **A durable record, not a derived-from-messages view** — chosen over
   the cheaper alternative (recompute "what was booked" from message text
   on every read) because message text is unstructured and fragile to
   future wording changes (§1) — a durable table survives independent of
   exact draft-text phrasing.
2. **Explicitly excludes CPF and payment confirmation** — matching AA-10/
   GB's existing non-retention rule, extended here rather than relaxed.
3. **Customer-facing line is session-only, never persisted client-side or
   server-side beyond the existing `appointment_bookings` row itself** —
   computed fresh from the same durable record on every poll, with no new
   `sessionStorage` write; relies on the conversation becoming
   unreachable once the client's own session ends (§4/BS-6).
4. **AA-10-sourced bookings stay specialty-only** — the human accepted
   this asymmetry rather than authorizing a change to AA-10's own flow to
   close it (§6) — an explicit scope boundary, not an oversight.
