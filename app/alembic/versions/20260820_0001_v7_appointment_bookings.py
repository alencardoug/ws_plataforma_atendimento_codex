"""V7 (007): create scheduling.appointment_bookings.

Revision ID: 20260820_0001
Revises: 20260819_0009

One row per completed booking flow (GB or AA-10), never mutated after
insert. `professional_id`/`unit_id`/`slot_starts_at` are nullable because
an AA-10-sourced row cannot populate them truthfully — AA-10 never tracks
which specific slot the customer meant, only the specialty (spec.md §6,
"the honesty limit"). No CPF/payment field exists on this table at all
(spec.md §5/BS-1's explicit exclusion). See
specs/007-completed-booking-visibility/data-model.md §1.
"""

from alembic import op

revision = "20260820_0001"
down_revision = "20260819_0009"
branch_labels = None
depends_on = None


DDL = r"""
CREATE TABLE IF NOT EXISTS scheduling.appointment_bookings (
    booking_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL REFERENCES customer_service.conversations(id),
    source text NOT NULL CHECK (source IN ('guided_booking','booking_script')),
    specialty_id uuid NOT NULL REFERENCES scheduling.specialties(specialty_id),
    professional_id uuid REFERENCES scheduling.professionals(professional_id),
    unit_id uuid REFERENCES scheduling.units(unit_id),
    slot_starts_at timestamptz,
    recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS appointment_bookings_conversation_id_idx ON scheduling.appointment_bookings (conversation_id);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V7 migrations are forward-only, consistent with the V1-V6 baseline")
