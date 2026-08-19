"""V5 (D-033 correction): widen ai_generations' trigger CHECK for GB's
direct-to-CPF/payment flow.

Revision ID: 20260819_0008
Revises: 20260819_0007

Adds 'GUIDED_CPF_CONFIRMED' (CPF accepted, payment question asked) and
'GUIDED_BOOKING_COMPLETE' (final success message, terminal — no further
customer reply is specially interpreted after it). 'GUIDED_CONFIRMATION'
(20260819_0006) is no longer produced by any code path after this
correction — left in the allowlist rather than removed, matching this
project's additive-only migration convention; a value simply going unused
is not a defect.
"""

from alembic import op

revision = "20260819_0008"
down_revision = "20260819_0007"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.ai_generations DROP CONSTRAINT ai_generations_trigger_check;
ALTER TABLE customer_service.ai_generations ADD CONSTRAINT ai_generations_trigger_check CHECK (
    trigger IN ('AUTOMATIC', 'MANUAL_DRAFT', 'MANUAL_EVIDENCE', 'GUIDED_SLOT_SELECTION', 'GUIDED_CONFIRMATION', 'GUIDED_CPF_CONFIRMED', 'GUIDED_BOOKING_COMPLETE')
);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V5 migrations are forward-only, consistent with the V1-V4 baseline")
