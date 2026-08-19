"""V4: seed the oncologia-geral generalist specialty (AA-3a).

Revision ID: 20260819_0002
Revises: 20260819_0001

See specs/004-dynamic-appointment-availability/{spec,plan,data-model}.md
§5 resolution/§8b, data-model.md §6. Data-only — 3 professionals mirroring
the existing 3-per-specialty pattern, priced/timed as a shorter, cheaper
"consulta simples" triage consultation than the 3 diagnosis-specific
specialties.
"""

from alembic import op

revision = "20260819_0002"
down_revision = "20260819_0001"
branch_labels = None
depends_on = None


DDL = r"""
INSERT INTO scheduling.specialties (specialty_id, slug, display_name, description) VALUES
('20000000-0000-0000-0000-000000000004', 'oncologia-geral', 'Oncologia geral (triagem)',
 'Primeira consulta com profissional generalista para investigação inicial de suspeita oncológica, sem especialidade definida (simulação)');

INSERT INTO scheduling.professionals (professional_id, display_name, registration_display) VALUES
('30000000-0000-0000-0000-000000000010', 'Dr. Eduardo Vasconcelos (simulação)', 'CRM-SP 000010 (simulação)'),
('30000000-0000-0000-0000-000000000011', 'Dra. Renata Silveira (simulação)', 'CRM-SP 000011 (simulação)'),
('30000000-0000-0000-0000-000000000012', 'Dr. Thiago Barros (simulação)', 'CRM-SP 000012 (simulação)');

INSERT INTO scheduling.professional_specialties (professional_id, specialty_id, fixed_price_cents, appointment_duration_minutes) VALUES
('30000000-0000-0000-0000-000000000010', '20000000-0000-0000-0000-000000000004', 60000, 45),
('30000000-0000-0000-0000-000000000011', '20000000-0000-0000-0000-000000000004', 60000, 45),
('30000000-0000-0000-0000-000000000012', '20000000-0000-0000-0000-000000000004', 60000, 45);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V4 migrations are forward-only, consistent with the V1/V2/V3 baseline")
