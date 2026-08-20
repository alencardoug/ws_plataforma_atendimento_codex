# Implementation Plan: Completed Booking Visibility

Governing spec: `spec.md`. Constitution: `.specify/memory/constitution.md`
(unchanged — spec.md §5).

## 1. Technical summary

Two migrations, one new ORM model, two write-trigger call sites (one in
`guided_booking.py`, one in `booking_script/service.py`), one shared
insert-and-audit helper, two read-side composed fields (operator, customer),
two frontend rendering call sites.

## 2. A necessary elaboration spec.md leaves to this plan: tracking *which*
offer GB ultimately confirmed

Direct inspection of `scheduling/guided_booking.py` before writing this
plan found a real gap spec.md's §7 data-model summary does not fully
resolve: `interpret_slot_choice()` (GB-2) returns the specific
`AppointmentOfferPresentation` the customer chose, but nothing durable
records *which one* — the draft text alone says "Entendi que você
escolheu: {offer.description}", and no column carries that identity
forward to `interpret_payment_reply()` (called on a *later*, separate
customer message, after CPF has already been asked and confirmed). BS-2
explicitly requires sourcing `professional_id`/`unit_id`/`slot_starts_at`
"from the specific `AppointmentOfferPresentation` row GB-2's ordinal/
embedding match already identified as the customer's selection" — this is
not possible without adding exactly this tracking.

**Resolution:** one new nullable column,
`conversations.guided_booking_selected_offer_id` (FK to
`customer_service.appointment_offer_presentations.id`), mirroring
`guided_booking_pending_text`/`guided_booking_pending_trigger`'s own
existing transient-staging pattern (`infrastructure/models.py:45-51`,
005/D-033) — not a mutation to `AppointmentOfferPresentation` itself (that
table stays exactly as spec.md §7 says, append-only, unchanged) and not a
new field on `booking_script_step` (also unchanged, per spec.md §7). Set
in `interpret_slot_choice()` itself (both the ordinal-match and
embedding-match return paths) the moment a specific offer is identified;
read and cleared in `interpret_payment_reply()` at the point BS-2 fires.
This is squarely a `plan.md`/`data-model.md` elaboration of "how" spec.md's
"source from the specific offer" requirement is met — it does not change
spec.md's own BS-1..BS-7 requirements or add new product behavior.

## 3. Module boundaries

- **New migration** `20260820_0001_v7_appointment_bookings.py` —
  `CREATE TABLE scheduling.appointment_bookings` per spec.md BS-1's exact
  DDL.
- **New migration** `20260820_0002_v7_guided_booking_selected_offer.py` —
  `ALTER TABLE customer_service.conversations ADD COLUMN IF NOT EXISTS
  guided_booking_selected_offer_id uuid REFERENCES customer_service.
  appointment_offer_presentations(id)` (plan.md §2).
- `app/customer_care/scheduling/models.py` — new `AppointmentBooking` ORM
  class (schema `scheduling`, matching this file's existing `Specialty`/
  `Professional`/`ScheduleSlot` precedent — the table itself lives in the
  `scheduling` schema per spec.md's DDL, unlike 005's
  `AppointmentOfferPresentation`, which lives in `customer_service` and is
  modeled in `infrastructure/models.py`; this package's table stays with
  its schema's existing model file for consistency).
- `app/customer_care/infrastructure/models.py` — `Conversation` gains
  `guided_booking_selected_offer_id: Mapped[UUID | None]` (plan.md §2).
- `app/customer_care/scheduling/availability.py` — new shared helper
  `record_appointment_booking()` (plan.md §4). Chosen over putting it in
  `guided_booking.py` (which `booking_script/service.py` must never
  import from — 005's containment boundary, spec.md §5/BS-3 "no new
  coupling") — `availability.py` is already imported by both call sites
  (`guided_booking.py` for `format_price_brl`, `booking_script/service.py`
  for the same), so this adds no new import edge.
- `app/customer_care/scheduling/guided_booking.py` — `interpret_slot_choice()`
  sets the new column (plan.md §2); `interpret_payment_reply()` calls
  `record_appointment_booking()` at its `GUIDED_BOOKING_COMPLETE` return
  (BS-2).
- `app/customer_care/booking_script/service.py` — one additive call to
  `record_appointment_booking()` immediately before the line-173
  `send_scripted_message(..., "Agendamento realizado com sucesso...")`
  call (BS-3) — the only change to this file, matching spec.md §3/BS-3's
  own "single additive insert call" framing.
- `app/customer_care/operator_workspace/router.py` — new
  `booking_summary_fields()` (mirrors `automatic_draft_fields()` exactly),
  spread into the same 3 call sites `automatic_draft_fields()` already is
  (BS-5).
- `app/customer_care/anonymous_access/router.py` — new
  `customer_booking_summary_fields()`, composed into `read_conversation()`
  only, alongside 008's `customer_draft_status()` (BS-6). Deliberately a
  **separate** function from BS-5's operator-side one (spec.md's own
  stated reason: keep the "session-only, never persisted" customer-side
  promise structurally distinct) even though both read the same
  `appointment_bookings` row — the customer-side one additionally
  formats the shorter/no-detail fallback line (spec.md BS-7).
- `frontend/src/main.tsx` — one new field on each of
  `OperatorConversation`/`CustomerConversation`, one rendered line in each
  page (BS-7 placement).

## 4. `record_appointment_booking()` (shared helper, `scheduling/availability.py`)

```python
def record_appointment_booking(
    session: Session, conversation: Conversation, *, source: str, specialty_id: UUID,
    professional_id: UUID | None = None, unit_id: UUID | None = None, slot_starts_at: datetime | None = None,
) -> None:
    """spec.md BS-1..BS-4: one row per completed booking flow, never
    mutated after insert. `specialty_id` is required in both callers
    (GB: read directly off the chosen offer's `ScheduleSlot`; AA-10:
    resolved from `_resolved_specialty_slug()`'s slug via one lookup at
    the call site, matching lookup_recent_specialty_price()'s own
    join pattern) — this helper looks the slug back up once, for the
    audit payload only, so callers never have to pass both forms."""
    from customer_care.audit.service import record_event
    from customer_care.scheduling.models import AppointmentBooking, Specialty

    booking = AppointmentBooking(conversation_id=conversation.id, source=source, specialty_id=specialty_id, professional_id=professional_id, unit_id=unit_id, slot_starts_at=slot_starts_at)
    session.add(booking)
    specialty_slug = session.scalar(select(Specialty.slug).where(Specialty.specialty_id == specialty_id))
    record_event(session, "scheduling.booking_recorded", "SYSTEM", conversation_id=conversation.id, payload={"conversation_id": str(conversation.id), "source": source, "specialty_slug": specialty_slug, "has_slot_detail": professional_id is not None})
```

- GB call site (`interpret_payment_reply`, on `GUIDED_BOOKING_COMPLETE`):
  ```python
  if conversation.guided_booking_selected_offer_id is not None:
      offer = session.get(AppointmentOfferPresentation, conversation.guided_booking_selected_offer_id)
      slot = session.get(ScheduleSlot, offer.slot_id) if offer else None
      if slot is not None:
          record_appointment_booking(session, conversation, source="guided_booking", specialty_id=slot.specialty_id, professional_id=slot.professional_id, unit_id=slot.unit_id, slot_starts_at=slot.starts_at)
      conversation.guided_booking_selected_offer_id = None
  ```
  The `is not None`/`slot is not None` guards are defensive, not an
  expected-empty path in production (GB-2 always sets this column before
  GB-4 can reach `GUIDED_BOOKING_COMPLETE` — the state machine has no
  other route there), matching this codebase's existing style of guarding
  even logically-unreachable branches rather than asserting.
- AA-10 call site (`booking_script/service.py`, immediately before line
  173's `send_scripted_message`):
  ```python
  generation = _latest_dynamic_generation(session, conversation)
  specialty_slug = _resolved_specialty_slug(session, generation) if generation else None
  specialty_id = session.scalar(select(Specialty.specialty_id).where(Specialty.slug == specialty_slug)) if specialty_slug else None
  if specialty_id is not None:
      record_appointment_booking(session, conversation, source="booking_script", specialty_id=specialty_id)
  ```

## 5. BS-5/BS-6 read-side fields

```python
# operator_workspace/router.py
def booking_summary_fields(session: DbSession, conversation: Conversation) -> dict:
    booking = session.scalar(select(AppointmentBooking).where(AppointmentBooking.conversation_id == conversation.id).order_by(AppointmentBooking.recorded_at.desc()))
    return {"booking_summary": booking_summary_dict(session, booking) if booking else None}
```

```python
# anonymous_access/router.py
def customer_booking_summary_fields(session: DbSession, conversation: Conversation) -> dict:
    booking = session.scalar(select(AppointmentBooking).where(AppointmentBooking.conversation_id == conversation.id).order_by(AppointmentBooking.recorded_at.desc()))
    return {"booking_summary_line": render_booking_summary_line(session, booking) if booking else None}
```

`booking_summary_dict()`/`render_booking_summary_line()` (new, in
`scheduling/availability.py` — read-only presentation helpers, matching
this module's existing "reads only" framing) render spec.md BS-7's exact
text shape: full detail when `professional_id`/`unit_id`/`slot_starts_at`
are all present, the shorter specialty-only line otherwise. Both are
server-rendered fixed templates (never LLM-composed), reading specialty/
professional/unit display names fresh through the FKs (matching
`offer_price_text()`'s own "never denormalized" precedent) and formatting
`slot_starts_at` in the unit's own timezone (`Unit.timezone`, already a
column) via `zoneinfo`, matching AA-2's existing time-zone-aware
formatting.

## 6. Test plan

- Backend: `record_appointment_booking()` inserts the right row for both
  sources (outcomes 1, 2); `guided_booking_selected_offer_id` is set by
  `interpret_slot_choice()` and correctly consumed/cleared by
  `interpret_payment_reply()`; `booking_script/service.py`'s diff for this
  feature is exactly the one additive call (outcome 7, mirroring 005's own
  `test_005_booking_script_containment.py` verification style); a CPF/
  payment content check on the new table (outcome 6).
- Frontend: `OperatorConversation.booking_summary`/`CustomerConversation.
  booking_summary_line` render in the specified positions (outcomes 3, 4);
  no rendering when absent (outcome 8).
- Playwright (new `frontend/e2e/v7.spec.ts`, continuing the v4/v5/v8/v9
  package-number convention): full GB flow through completion shows the
  detailed line on both operator and customer sides within one poll cycle;
  `sessionStorage` inspection confirms the customer line isn't persisted
  beyond the tab session (outcome 5).

## 7. Risks

- **Risk:** a customer's "voltar" after `GUIDED_CPF_CONFIRMED` (D-035)
  re-presents the offer set but does not go through `interpret_slot_choice`
  again until the customer picks once more — `guided_booking_selected_offer_id`
  stays set to the *previous* choice in the meantime. **Mitigation:** this
  is harmless — it is only ever read at the `GUIDED_BOOKING_COMPLETE`
  transition, which cannot be reached without first passing through
  `interpret_slot_choice` again for the new choice (overwriting the
  column) followed by a fresh CPF/payment cycle; a stale value can never
  be the one actually read.
- **Risk:** `AppointmentOfferPresentation` rows are keyed by
  `ai_generation_id`, and `guided_booking_selected_offer_id` stores that
  row's own `id` (not `ai_generation_id`) — confirmed correct: BS-1 needs
  the specific *offer*, not the *set*, and `AppointmentOfferPresentation.id`
  is exactly that row's own primary key.
