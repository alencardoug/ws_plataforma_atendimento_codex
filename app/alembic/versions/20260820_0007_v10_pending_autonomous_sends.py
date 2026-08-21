"""V10 (010/GA-3): create customer_service.pending_autonomous_sends.

Revision ID: 20260820_0007
Revises: 20260820_0006

One row per eligible generation opened for governed autonomous send.
`window_seconds`/`resolves_at` are captured at insert time — a later
change to system_settings never retroactively changes an already-open
window. The partial unique index on (generation_id) WHERE status='PENDING'
is the double-resolution guard plan.md §7 describes. See
specs/010-governed-autonomous-response/data-model.md §3.
"""

from alembic import op

revision = "20260820_0007"
down_revision = "20260820_0006"
branch_labels = None
depends_on = None


DDL = r"""
CREATE TABLE IF NOT EXISTS customer_service.pending_autonomous_sends (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    generation_id uuid NOT NULL REFERENCES customer_service.ai_generations(id),
    conversation_id uuid NOT NULL REFERENCES customer_service.conversations(id),
    category text NOT NULL REFERENCES content.categories(slug),
    window_seconds integer NOT NULL,
    opens_at timestamptz NOT NULL DEFAULT now(),
    resolves_at timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'SENT', 'PAUSED', 'EDITED', 'TAKEN_OVER')),
    resolved_at timestamptz,
    resolved_by_operator_id uuid REFERENCES customer_service.operator_users(id),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS pending_autonomous_sends_one_pending_per_generation
    ON customer_service.pending_autonomous_sends (generation_id)
    WHERE status = 'PENDING';
CREATE INDEX IF NOT EXISTS pending_autonomous_sends_resolvable
    ON customer_service.pending_autonomous_sends (resolves_at)
    WHERE status = 'PENDING';
CREATE INDEX IF NOT EXISTS pending_autonomous_sends_conversation_id_idx
    ON customer_service.pending_autonomous_sends (conversation_id);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V10 migrations are forward-only, consistent with the V1-V9 baseline")
