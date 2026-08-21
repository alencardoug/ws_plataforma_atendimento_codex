"""V11 (011): add system_settings.n5_kill_switch_enabled and
.automatic_trigger_idle_seconds.

Revision ID: 20260821_0001
Revises: 20260820_0011

Constitution Amendment 1.3.0's N5 exception has its own independent kill
switch (separate from Amendment 1.2.0's autonomy_kill_switch_enabled).
automatic_trigger_idle_seconds replaces the fixed AUTOMATIC_TRIGGER_IDLE_SECONDS
constant (8, confirmed by direct inspection of ai/router.py) — shared
infrastructure the automatic-trigger evaluation entry point uses for both
N3/N4 and N5. See specs/011-ungoverned-fictional-demo-autonomy-n5/data-model.md §1.
"""

from alembic import op

revision = "20260821_0001"
down_revision = "20260820_0011"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.system_settings
    ADD COLUMN n5_kill_switch_enabled boolean NOT NULL DEFAULT false,
    ADD COLUMN automatic_trigger_idle_seconds integer NOT NULL DEFAULT 8;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V11 migrations are forward-only, consistent with the V1-V10 baseline")
