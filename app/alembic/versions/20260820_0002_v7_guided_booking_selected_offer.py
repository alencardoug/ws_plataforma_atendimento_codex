"""V7 (007): transient staging column for GB's confirmed offer identity.

Revision ID: 20260820_0002
Revises: 20260820_0001

`interpret_slot_choice()` (GB-2) identifies the specific
`AppointmentOfferPresentation` a customer chose, but nothing durable
carried that identity forward to the later, separate payment-confirmation
message `interpret_payment_reply()` (BS-2) fires on — required so BS-2 can
source `professional_id`/`unit_id`/`slot_starts_at` from the correct offer.
Same "transient flow-position state, not an audited durable fact" framing
as `guided_booking_pending_text`/`_trigger` (005/D-033's own precedent) —
set at slot-choice time, read and cleared at payment-confirmation time.
See specs/007-completed-booking-visibility/plan.md §2.
"""

from alembic import op

revision = "20260820_0002"
down_revision = "20260820_0001"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.conversations
    ADD COLUMN IF NOT EXISTS guided_booking_selected_offer_id uuid
        REFERENCES customer_service.appointment_offer_presentations(id);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V7 migrations are forward-only, consistent with the V1-V6 baseline")
