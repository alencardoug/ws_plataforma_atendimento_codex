"""V10 (010): widen messages_check for governed_autonomy's own
NULL-operator_id OPERATOR message.

Revision ID: 20260820_0011
Revises: 20260820_0010

Found during implementation: `messages_check` is a second, DB-level
enforcement of the same containment invariant
test_booking_script_containment.py checks at the Python/AST level —
defense in depth this project already had for Amendment 1.1.0's own
exception, previously only allowing `author_type='OPERATOR' AND
operator_id IS NULL` when `autonomous_source='booking_script'`. Widened
to also allow `autonomous_source='governed_autonomy'` (Amendment 1.2.0).
See specs/010-governed-autonomous-response/data-model.md §5.
"""

from alembic import op

revision = "20260820_0011"
down_revision = "20260820_0010"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.messages DROP CONSTRAINT messages_check;
ALTER TABLE customer_service.messages ADD CONSTRAINT messages_check CHECK (
    (author_type = 'CUSTOMER' AND operator_id IS NULL)
    OR (author_type = 'OPERATOR' AND operator_id IS NOT NULL)
    OR (author_type = 'OPERATOR' AND operator_id IS NULL AND autonomous_source IN ('booking_script', 'governed_autonomy'))
);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V10 migrations are forward-only, consistent with the V1-V9 baseline")
