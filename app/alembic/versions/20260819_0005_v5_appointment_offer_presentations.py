"""V5: create customer_service.appointment_offer_presentations (GB-1).

Revision ID: 20260819_0005
Revises: 20260819_0004

One row per offer shown to a customer by a resolved
appointment_availability generation (up to 4, AA-2's existing LIMIT 4).
Append-only. See specs/005-dynamic-pricing-and-guided-booking/data-model.md
§1/§6.1.

Both FKs are ON DELETE CASCADE: production never deletes an AIGeneration
or a schedule_slots row (AA-2 only reads slots, AA-9 only inserts them),
so this has no production behavioral effect — added after this feature's
own tests uncovered that pre-existing 004 test fixtures
(test_appointment_seeding.py) legitimately create and delete schedule_slots
rows as part of isolated test cleanup, which a plain (non-cascading) FK
would then break as soon as any test in the same run causes a real
appointment_availability resolution against one of those rows.
"""

from alembic import op

revision = "20260819_0005"
down_revision = "20260819_0004"
branch_labels = None
depends_on = None


DDL = r"""
CREATE TABLE IF NOT EXISTS customer_service.appointment_offer_presentations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ai_generation_id uuid NOT NULL REFERENCES customer_service.ai_generations(id) ON DELETE CASCADE,
    slot_id uuid NOT NULL REFERENCES scheduling.schedule_slots(slot_id) ON DELETE CASCADE,
    display_order smallint NOT NULL CHECK (display_order BETWEEN 1 AND 4),
    description text NOT NULL,
    embedding vector(1536) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (ai_generation_id, display_order)
);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V5 migrations are forward-only, consistent with the V1-V4 baseline")
