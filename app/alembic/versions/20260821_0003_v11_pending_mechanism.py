"""V11 (011): pending_autonomous_sends gains mechanism.

Revision ID: 20260821_0003
Revises: 20260821_0002

Distinguishes which autonomy exception opened a given pending row —
Amendment 1.2.0's governed_autonomy or Amendment 1.3.0's ungoverned_n5 —
so resolve_elapsed_autonomous_sends() can stamp the correct
messages.autonomous_source value (plan.md §5) instead of the previously
hardcoded 'governed_autonomy'. Backfilled NOT NULL DEFAULT
'governed_autonomy' for every pre-existing row (all of which really were
opened by the 010 path, before N5 existed), then the default is dropped so
every future insert must state it explicitly. See
specs/011-ungoverned-fictional-demo-autonomy-n5/data-model.md §2.
"""

from alembic import op

revision = "20260821_0003"
down_revision = "20260821_0002"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.pending_autonomous_sends
    ADD COLUMN mechanism text NOT NULL DEFAULT 'governed_autonomy';
ALTER TABLE customer_service.pending_autonomous_sends
    ADD CONSTRAINT pending_autonomous_sends_mechanism_check
        CHECK (mechanism IN ('governed_autonomy', 'ungoverned_n5'));
ALTER TABLE customer_service.pending_autonomous_sends
    ALTER COLUMN mechanism DROP DEFAULT;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V11 migrations are forward-only, consistent with the V1-V10 baseline")
