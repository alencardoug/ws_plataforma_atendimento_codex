# Data Model: Completed Booking Visibility

## 1. New table: `scheduling.appointment_bookings` (BS-1)

```sql
CREATE TABLE scheduling.appointment_bookings (
    booking_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL REFERENCES customer_service.conversations(id),
    source text NOT NULL CHECK (source IN ('guided_booking','booking_script')),
    specialty_id uuid NOT NULL REFERENCES scheduling.specialties(specialty_id),
    professional_id uuid REFERENCES scheduling.professionals(professional_id),
    unit_id uuid REFERENCES scheduling.units(unit_id),
    slot_starts_at timestamptz,
    recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON scheduling.appointment_bookings (conversation_id);
```

Matches spec.md BS-1 verbatim. `professional_id`/`unit_id`/`slot_starts_at`
nullable by design (spec.md §6, "the honesty limit") — `NULL` for every
`source='booking_script'` row. Never mutated after insert. No `CPF`/
payment field exists on this table at all (spec.md §5/BS-1's explicit
exclusion) — not nullable-and-unused, structurally absent.

ORM: `AppointmentBooking` in `scheduling/models.py` (plan.md §3), matching
that file's existing `scheduling`-schema model style.

## 2. New column: `customer_service.conversations.guided_booking_selected_offer_id`

```sql
ALTER TABLE customer_service.conversations
    ADD COLUMN IF NOT EXISTS guided_booking_selected_offer_id uuid
        REFERENCES customer_service.appointment_offer_presentations(id);
```

A plan.md-level elaboration (plan.md §2), not itself named in spec.md —
required to carry "which specific offer GB-2 identified" forward from the
slot-choice step to the later, separate payment-confirmation message BS-2
fires on. Transient: set by `interpret_slot_choice()`, read and cleared by
`interpret_payment_reply()`. Nullable; no FK cascade behavior beyond the
default (matches `guided_booking_pending_text`/`_trigger`'s own
un-cascaded nullable-column precedent — this column is cleared by
application code, not by a DB-level ON DELETE rule).

## 3. No other schema change

`scheduling.schedule_slots`, `scheduling.holidays`,
`AppointmentOfferPresentation`, and `conversation.booking_script_step` are
all unchanged (spec.md §7, reconfirmed). `customer_projection()`'s own
shared shape is unchanged — both new read-side fields
(`booking_summary` operator-side, `booking_summary_line` customer-side)
are composed by their respective routers on top of it, matching
`automatic_draft_fields()`'s existing precedent.

## 4. New audit event

`scheduling.booking_recorded` (BS-4) — payload
`{conversation_id, source, specialty_slug, has_slot_detail: bool}`. Never
the completion message's own body text. Documented in
`docs/architecture/EVENT_CATALOG.md`.
