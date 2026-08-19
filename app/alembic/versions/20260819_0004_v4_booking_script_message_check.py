"""V4: narrowly widen customer_service.messages' pre-existing CHECK
constraint to allow AA-10's one authorized autonomous OPERATOR message.

Revision ID: 20260819_0004
Revises: 20260819_0003

Found during Phase 9 implementation: the V1-baseline `messages_check`
constraint — `(author_type='CUSTOMER' AND operator_id IS NULL) OR
(author_type='OPERATOR' AND operator_id IS NOT NULL)` — rejected
send_scripted_message()'s insert outright (author_type='OPERATOR',
operator_id=NULL), since there is no operator in that call's context by
design (plan.md §8b). This migration adds exactly one more disjunct,
allowed only when autonomous_source is explicitly 'booking_script' — the
one column messages_autonomous_source_check (20260819_0003) already
limits to that single legal non-null value. This is itself a structural
enforcement of Constitution Amendment 1.1.0's narrow scope: an
OPERATOR-authored message can never have a NULL operator_id for any
other reason, at the database level, not just in application code.
"""

from alembic import op

revision = "20260819_0004"
down_revision = "20260819_0003"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.messages DROP CONSTRAINT messages_check;
ALTER TABLE customer_service.messages ADD CONSTRAINT messages_check CHECK (
    (author_type = 'CUSTOMER' AND operator_id IS NULL)
    OR (author_type = 'OPERATOR' AND operator_id IS NOT NULL)
    OR (author_type = 'OPERATOR' AND operator_id IS NULL AND autonomous_source = 'booking_script')
);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V4 migrations are forward-only, consistent with the V1/V2/V3 baseline")
