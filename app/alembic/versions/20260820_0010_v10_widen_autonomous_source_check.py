"""V10 (010): widen messages.autonomous_source CHECK for 'governed_autonomy'.

Revision ID: 20260820_0010
Revises: 20260820_0009

Found during implementation: messages_autonomous_source_check restricted
this column to NULL or 'booking_script' only — spec.md/data-model.md §5's
original "No schema change" claim for this column was wrong (a real
CHECK constraint existed, not visible without inspecting the live schema
directly; ORM-level `Mapped[str | None]` gives no hint of a DB-level
CHECK). See specs/010-governed-autonomous-response/data-model.md §5.
"""

from alembic import op

revision = "20260820_0010"
down_revision = "20260820_0009"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.messages DROP CONSTRAINT messages_autonomous_source_check;
ALTER TABLE customer_service.messages ADD CONSTRAINT messages_autonomous_source_check
    CHECK (autonomous_source IS NULL OR autonomous_source IN ('booking_script', 'governed_autonomy'));
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V10 migrations are forward-only, consistent with the V1-V9 baseline")
