"""V11 (011): widen messages_autonomous_source_check for 'ungoverned_n5'.

Revision ID: 20260821_0004
Revises: 20260821_0003

Same constraint feature 010 widened for 'governed_autonomy'. See
specs/011-ungoverned-fictional-demo-autonomy-n5/data-model.md §3.
"""

from alembic import op

revision = "20260821_0004"
down_revision = "20260821_0003"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.messages DROP CONSTRAINT messages_autonomous_source_check;
ALTER TABLE customer_service.messages ADD CONSTRAINT messages_autonomous_source_check
    CHECK (autonomous_source IS NULL OR autonomous_source IN ('booking_script', 'governed_autonomy', 'ungoverned_n5'));
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V11 migrations are forward-only, consistent with the V1-V10 baseline")
