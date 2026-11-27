"""D-046: complete the 2027 holiday calendar before the agenda horizon
reaches it.

Revision ID: 20261127_0002
Revises: 20261127_0001

2027 had 9 of the 12 holiday kinds 2026 carries. Adds the missing three,
mirroring their 2026 rows exactly: Aniversário de São Paulo (25/01,
municipal), Paixão de Cristo (26/03/2027 — Easter is 28/03/2027), and
Revolução Constitucionalista (09/07, state SP). Idempotent.
"""

from alembic import op

revision = "20261127_0002"
down_revision = "20261127_0001"
branch_labels = None
depends_on = None


DDL = r"""
INSERT INTO scheduling.holidays (holiday_date, name, scope, state_code, city_code, is_business_day, simulated)
SELECT v.holiday_date, v.name, v.scope, v.state_code, v.city_code, false, false
FROM (VALUES
    (DATE '2027-01-25', 'Aniversário de São Paulo', 'municipal', 'SP', 'SAO_PAULO'),
    (DATE '2027-03-26', 'Paixão de Cristo', 'national', NULL, NULL),
    (DATE '2027-07-09', 'Revolução Constitucionalista', 'state', 'SP', NULL)
) AS v(holiday_date, name, scope, state_code, city_code)
WHERE NOT EXISTS (SELECT 1 FROM scheduling.holidays h WHERE h.holiday_date = v.holiday_date);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("Forward-only, consistent with the V1-V12 baseline")
