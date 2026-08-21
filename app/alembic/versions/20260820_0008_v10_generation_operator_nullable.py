"""V10 (010/GA-6): ai_generations.operator_id becomes nullable.

Revision ID: 20260820_0008
Revises: 20260820_0007

GA-6's unclaimed-conversation autonomous-trigger path has no operator to
attribute a generation to. Exactly one new call site
(evaluate_unclaimed_autonomous_trigger()) ever produces operator_id IS
NULL — every existing caller is unaffected. See
specs/010-governed-autonomous-response/data-model.md §4,
specs/010-governed-autonomous-response/plan.md §2.
"""

from alembic import op

revision = "20260820_0008"
down_revision = "20260820_0007"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.ai_generations
    ALTER COLUMN operator_id DROP NOT NULL;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V10 migrations are forward-only, consistent with the V1-V9 baseline")
