"""V11 (011): pending_autonomous_sends.category becomes nullable.

Revision ID: 20260821_0002
Revises: 20260821_0001

An N5-opened row (Constitution Amendment 1.3.0) has no matched category by
construction (generation.category_slug is always None for an ungoverned
generation) — this widens what a future row may contain, never narrows an
existing one. See
specs/011-ungoverned-fictional-demo-autonomy-n5/data-model.md §2.
"""

from alembic import op

revision = "20260821_0002"
down_revision = "20260821_0001"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.pending_autonomous_sends
    ALTER COLUMN category DROP NOT NULL;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V11 migrations are forward-only, consistent with the V1-V10 baseline")
