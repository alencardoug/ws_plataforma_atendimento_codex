"""V5 (D-033 correction): transient staging columns for GB's own CPF/
payment interpretation.

Revision ID: 20260819_0007
Revises: 20260819_0006

The raw CPF/payment reply is parsed synchronously at message-creation time
(anonymous_access/router.py, mirroring AA-10's own request-local parsing
principle) since the durable Message body is redacted immediately
afterward and would no longer be available to a later, operator-click-
driven draft-generation call. The *result* of that interpretation (a safe,
already-computed message string — never the raw CPF/payment reply itself)
is staged here until the next draft-generation call consumes and clears
it. Same "transient flow-position state, not an audited durable fact"
framing as `conversations.booking_script_step` (004's own precedent,
data-model.md §8) — this is GB's own parallel field, never read or written
by booking_script/*.
"""

from alembic import op

revision = "20260819_0007"
down_revision = "20260819_0006"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.conversations
    ADD COLUMN IF NOT EXISTS guided_booking_pending_text text,
    ADD COLUMN IF NOT EXISTS guided_booking_pending_trigger text;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V5 migrations are forward-only, consistent with the V1-V4 baseline")
