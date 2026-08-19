"""V5 (D-035 correction): widen ai_generations' trigger CHECK for GB's
step-back-to-slot-choice capability.

Revision ID: 20260819_0009
Revises: 20260819_0008

Adds 'GUIDED_SLOT_RESELECTION' — the customer typed "voltar"/"cancelar"/
"alterar horário" (or a variation) while GB's CPF question was pending;
the response re-presents the same original offer set and awaits a fresh
slot pick, instead of trying to parse the reply as a CPF. A genuinely new
value rather than reusing 'GUIDED_CONFIRMATION' (already unused since
D-033): that value's own migration explicitly framed it as retired, not
as a slot free for a new, different meaning.
"""

from alembic import op

revision = "20260819_0009"
down_revision = "20260819_0008"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.ai_generations DROP CONSTRAINT ai_generations_trigger_check;
ALTER TABLE customer_service.ai_generations ADD CONSTRAINT ai_generations_trigger_check CHECK (
    trigger IN ('AUTOMATIC', 'MANUAL_DRAFT', 'MANUAL_EVIDENCE', 'GUIDED_SLOT_SELECTION', 'GUIDED_CONFIRMATION', 'GUIDED_CPF_CONFIRMED', 'GUIDED_BOOKING_COMPLETE', 'GUIDED_SLOT_RESELECTION')
);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V5 migrations are forward-only, consistent with the V1-V4 baseline")
