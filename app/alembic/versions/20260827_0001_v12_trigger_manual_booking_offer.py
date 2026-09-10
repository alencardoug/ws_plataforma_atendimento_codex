"""V12 (012): widen ai_generations_trigger_check for 'MANUAL_BOOKING_OFFER'.

Revision ID: 20260827_0001
Revises: 20260821_0005

The Operator Booking-Offer action (OB) persists its resolver-driven
availability draft as an ordinary AIGeneration with a distinct trigger
value, deliberately NOT 'AUTOMATIC' and NOT any 'GUIDED_*' value so it is
never eligible for autonomous send (Constitution Amendment 1.2.0 clause
(b)). There is exactly one CHECK constraint on this column (verified
against the live schema). See
specs/012-appointment-availability-continuity-and-booking-action/data-model.md §2.
"""

from alembic import op

revision = "20260827_0001"
down_revision = "20260821_0005"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.ai_generations DROP CONSTRAINT ai_generations_trigger_check;
ALTER TABLE customer_service.ai_generations ADD CONSTRAINT ai_generations_trigger_check CHECK (
    trigger IN (
        'AUTOMATIC', 'MANUAL_DRAFT', 'MANUAL_EVIDENCE',
        'GUIDED_SLOT_SELECTION', 'GUIDED_CONFIRMATION', 'GUIDED_CPF_CONFIRMED',
        'GUIDED_BOOKING_COMPLETE', 'GUIDED_SLOT_RESELECTION',
        'MANUAL_BOOKING_OFFER'
    )
);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V12 migrations are forward-only, consistent with the V1-V11 baseline")
