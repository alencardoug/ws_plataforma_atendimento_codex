"""V5: widen ai_generations' trigger CHECK to allow the two new guided-
booking generation kinds (GB-2/GB-4).

Revision ID: 20260819_0006
Revises: 20260819_0005

Adds 'GUIDED_SLOT_SELECTION' and 'GUIDED_CONFIRMATION' to the trigger
CHECK constraint 20260814_0001 originally created. Reuses the trigger
column's existing purpose (what kind of thing produced this generation)
rather than adding a new marker column — see
specs/005-dynamic-pricing-and-guided-booking/data-model.md §3.
"""

from alembic import op

revision = "20260819_0006"
down_revision = "20260819_0005"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.ai_generations DROP CONSTRAINT ai_generations_trigger_check;
ALTER TABLE customer_service.ai_generations ADD CONSTRAINT ai_generations_trigger_check CHECK (
    trigger IN ('AUTOMATIC', 'MANUAL_DRAFT', 'MANUAL_EVIDENCE', 'GUIDED_SLOT_SELECTION', 'GUIDED_CONFIRMATION')
);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V5 migrations are forward-only, consistent with the V1-V4 baseline")
