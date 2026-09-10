"""V12 (012): add system_settings.availability_floor_checked_at.

Revision ID: 20260827_0002
Revises: 20260827_0001

Debounce bookkeeping for the AC-2 low-water-mark top-up
(ensure_generalist_floor()), evaluated lazily from the operator queue
poll. Nullable, no default: NULL means "never checked" -> run now. Written
only by ensure_generalist_floor() itself, never operator-settable. See
specs/012-appointment-availability-continuity-and-booking-action/data-model.md §1.
"""

from alembic import op

revision = "20260827_0002"
down_revision = "20260827_0001"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.system_settings
    ADD COLUMN availability_floor_checked_at timestamptz NULL;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V12 migrations are forward-only, consistent with the V1-V11 baseline")
