"""V4: booking-script columns (AA-10, Constitution Amendment 1.1.0) —
Conversation.booking_script_step and Message.autonomous_source.

Revision ID: 20260819_0003
Revises: 20260819_0002

See specs/004-dynamic-appointment-availability/{spec,plan,data-model}.md
§8b/§8. Both columns additive and nullable, CHECK-constrained at the
database level to their only legal values — a third, unauthorized step
value or autonomous-source value can never be written even by a future
bug. Neither column ever holds the customer's raw CPF or payment answer
— only a position marker in the script and a provenance tag.
"""

from alembic import op

revision = "20260819_0003"
down_revision = "20260819_0002"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.conversations
  ADD COLUMN IF NOT EXISTS booking_script_step text NULL
  CHECK (booking_script_step IS NULL OR booking_script_step IN ('AWAITING_CPF', 'AWAITING_PAYMENT'));

ALTER TABLE customer_service.messages
  ADD COLUMN IF NOT EXISTS autonomous_source text NULL
  CHECK (autonomous_source IS NULL OR autonomous_source IN ('booking_script'));
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V4 migrations are forward-only, consistent with the V1/V2/V3 baseline")
