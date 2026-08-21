"""V11 (011): widen messages_check for 'ungoverned_n5'.

Revision ID: 20260821_0005
Revises: 20260821_0004

Same second, independent CHECK constraint feature 010 widened for
'governed_autonomy'. See
specs/011-ungoverned-fictional-demo-autonomy-n5/data-model.md §3.
"""

from alembic import op

revision = "20260821_0005"
down_revision = "20260821_0004"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.messages DROP CONSTRAINT messages_check;
ALTER TABLE customer_service.messages ADD CONSTRAINT messages_check CHECK (
    (author_type = 'CUSTOMER' AND operator_id IS NULL)
    OR (author_type = 'OPERATOR' AND operator_id IS NOT NULL)
    OR (author_type = 'OPERATOR' AND operator_id IS NULL AND autonomous_source IN ('booking_script', 'governed_autonomy', 'ungoverned_n5'))
);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V11 migrations are forward-only, consistent with the V1-V10 baseline")
