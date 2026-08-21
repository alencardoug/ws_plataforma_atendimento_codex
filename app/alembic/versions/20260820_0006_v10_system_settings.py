"""V10 (010): create customer_service.system_settings, single-row.

Revision ID: 20260820_0006
Revises: 20260820_0005

Global operator-configurable settings for governed autonomy: the veto
window duration (seconds, 0 = immediate send) and the kill switch. The
`id boolean PRIMARY KEY DEFAULT true` + `CHECK (id)` pattern guarantees
exactly one row can ever exist. Kill switch and window default keep
autonomy conservative until an operator explicitly changes them. See
specs/010-governed-autonomous-response/data-model.md §2.
"""

from alembic import op

revision = "20260820_0006"
down_revision = "20260820_0005"
branch_labels = None
depends_on = None


DDL = r"""
CREATE TABLE IF NOT EXISTS customer_service.system_settings (
    id boolean PRIMARY KEY DEFAULT true,
    CONSTRAINT system_settings_singleton CHECK (id),
    autonomy_window_seconds integer NOT NULL DEFAULT 30,
    autonomy_kill_switch_enabled boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by_operator_id uuid REFERENCES customer_service.operator_users(id)
);
INSERT INTO customer_service.system_settings (id) VALUES (true)
    ON CONFLICT (id) DO NOTHING;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V10 migrations are forward-only, consistent with the V1-V9 baseline")
