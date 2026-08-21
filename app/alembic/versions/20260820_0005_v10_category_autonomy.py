"""V10 (010/GA-1): add content.categories.autonomy_enabled.

Revision ID: 20260820_0005
Revises: 20260820_0004

Constitution Amendment 1.2.0 governed-autonomy exception. Default false —
autonomy is opt-in at every level (system_settings' own kill switch also
defaults off). See specs/010-governed-autonomous-response/data-model.md §1.
"""

from alembic import op

revision = "20260820_0005"
down_revision = "20260820_0004"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE content.categories
    ADD COLUMN IF NOT EXISTS autonomy_enabled boolean NOT NULL DEFAULT false;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V10 migrations are forward-only, consistent with the V1-V9 baseline")
