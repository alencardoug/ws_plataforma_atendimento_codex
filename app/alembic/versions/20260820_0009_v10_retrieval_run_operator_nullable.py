"""V10 (010/GA-6): retrieval_runs.operator_id becomes nullable.

Revision ID: 20260820_0009
Revises: 20260820_0008

Found during implementation (not anticipated when spec.md/plan.md were
first written): generate_draft() calls rag.service.retrieve() before
constructing the AIGeneration row, and retrieve() independently persists
a RetrievalRun with the same operator_id — both FKs must accept NULL for
evaluate_unclaimed_autonomous_trigger()'s path to work. See
specs/010-governed-autonomous-response/data-model.md §4.
"""

from alembic import op

revision = "20260820_0009"
down_revision = "20260820_0008"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.retrieval_runs
    ALTER COLUMN operator_id DROP NOT NULL;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V10 migrations are forward-only, consistent with the V1-V9 baseline")
