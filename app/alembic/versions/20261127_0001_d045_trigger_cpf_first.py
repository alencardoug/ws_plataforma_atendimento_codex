"""D-045: widen ai_generations_trigger_check for GB's CPF-first order.

Revision ID: 20261127_0001
Revises: 20260827_0002

Adds 'GUIDED_CPF_REQUEST' (invalid-CPF retry while the CPF is still
pending) and 'GUIDED_BOOKING_CANCELLED' (terminal: "cancelar" at the CPF
step). See specs/005-dynamic-pricing-and-guided-booking/spec.md §13.
"""

from alembic import op

revision = "20261127_0001"
down_revision = "20260827_0002"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.ai_generations DROP CONSTRAINT ai_generations_trigger_check;
ALTER TABLE customer_service.ai_generations ADD CONSTRAINT ai_generations_trigger_check CHECK (
    trigger IN (
        'AUTOMATIC', 'MANUAL_DRAFT', 'MANUAL_EVIDENCE',
        'GUIDED_SLOT_SELECTION', 'GUIDED_CONFIRMATION', 'GUIDED_CPF_CONFIRMED',
        'GUIDED_BOOKING_COMPLETE', 'GUIDED_SLOT_RESELECTION',
        'MANUAL_BOOKING_OFFER',
        'GUIDED_CPF_REQUEST', 'GUIDED_BOOKING_CANCELLED'
    )
);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("Forward-only, consistent with the V1-V12 baseline")
