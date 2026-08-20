"""V6 (006/SS): four new bookable support specialties — psico-oncologia,
nutrição oncológica, endocrinologia oncológica, fisioterapia oncológica.

Revision ID: 20260820_0004
Revises: 20260820_0003

Data-only, same shape as `20260819_0002_v4_generalist_specialty.py`.
`resolve_price_lookup`/`resolve_appointment_availability` need zero code
change (spec.md SS-3, confirmed by direct inspection — neither has any
specialty allowlist beyond `extract_parameters()`'s own
`SPECIALTY_KEYWORDS`, a Python-level dict extended separately). No
`scheduling.schedule_slots` rows here — slot creation is exclusively SV's
job (`ensure_wide_availability()`), matching AA-9's own "migrations seed
reference data, seeding actions seed slots" split. See
specs/006-specialty-scheduling-breadth/data-model.md §3.
"""

from alembic import op

revision = "20260820_0004"
down_revision = "20260820_0003"
branch_labels = None
depends_on = None


DDL = r"""
INSERT INTO scheduling.specialties (specialty_id, slug, display_name, description) VALUES
('20000000-0000-0000-0000-000000000005', 'psico-oncologia', 'Psico-oncologia',
 'Acompanhamento psicológico especializado em oncologia, para pacientes e familiares (simulação)'),
('20000000-0000-0000-0000-000000000006', 'nutricao-oncologica', 'Nutrição oncológica',
 'Orientação nutricional durante e após o tratamento oncológico (simulação)'),
('20000000-0000-0000-0000-000000000007', 'endocrinologia-oncologica', 'Endocrinologia oncológica',
 'Acompanhamento hormonal/endócrino relacionado ao tratamento oncológico (simulação)'),
('20000000-0000-0000-0000-000000000008', 'fisioterapia-oncologica', 'Fisioterapia oncológica',
 'Reabilitação física e manejo de linfedema durante e após o tratamento oncológico (simulação)');

INSERT INTO scheduling.professionals (professional_id, display_name, registration_display) VALUES
('30000000-0000-0000-0000-000000000013', 'Dra. Sofia Cardoso (simulação)', 'CRP-SP 000013 (simulação)'),
('30000000-0000-0000-0000-000000000014', 'Dr. Bruno Teixeira (simulação)', 'CRP-SP 000014 (simulação)'),
('30000000-0000-0000-0000-000000000015', 'Dra. Isabela Ramos (simulação)', 'CRP-SP 000015 (simulação)'),
('30000000-0000-0000-0000-000000000016', 'Dra. Cecília Duarte (simulação)', 'CRN-SP 000016 (simulação)'),
('30000000-0000-0000-0000-000000000017', 'Dr. Felipe Moraes (simulação)', 'CRN-SP 000017 (simulação)'),
('30000000-0000-0000-0000-000000000018', 'Dra. Larissa Pinto (simulação)', 'CRN-SP 000018 (simulação)'),
('30000000-0000-0000-0000-000000000019', 'Dr. Ricardo Nunes (simulação)', 'CRM-SP 000019 (simulação)'),
('30000000-0000-0000-0000-000000000020', 'Dra. Juliana Farias (simulação)', 'CRM-SP 000020 (simulação)'),
('30000000-0000-0000-0000-000000000021', 'Dr. Otávio Correia (simulação)', 'CRM-SP 000021 (simulação)'),
('30000000-0000-0000-0000-000000000022', 'Dra. Vitória Campos (simulação)', 'CREFITO-SP 000022 (simulação)'),
('30000000-0000-0000-0000-000000000023', 'Dr. Henrique Batista (simulação)', 'CREFITO-SP 000023 (simulação)'),
('30000000-0000-0000-0000-000000000024', 'Dra. Manuela Freitas (simulação)', 'CREFITO-SP 000024 (simulação)');

INSERT INTO scheduling.professional_specialties (professional_id, specialty_id, fixed_price_cents, appointment_duration_minutes) VALUES
('30000000-0000-0000-0000-000000000013', '20000000-0000-0000-0000-000000000005', 45000, 50),
('30000000-0000-0000-0000-000000000014', '20000000-0000-0000-0000-000000000005', 45000, 50),
('30000000-0000-0000-0000-000000000015', '20000000-0000-0000-0000-000000000005', 45000, 50),
('30000000-0000-0000-0000-000000000016', '20000000-0000-0000-0000-000000000006', 40000, 45),
('30000000-0000-0000-0000-000000000017', '20000000-0000-0000-0000-000000000006', 40000, 45),
('30000000-0000-0000-0000-000000000018', '20000000-0000-0000-0000-000000000006', 40000, 45),
('30000000-0000-0000-0000-000000000019', '20000000-0000-0000-0000-000000000007', 55000, 45),
('30000000-0000-0000-0000-000000000020', '20000000-0000-0000-0000-000000000007', 55000, 45),
('30000000-0000-0000-0000-000000000021', '20000000-0000-0000-0000-000000000007', 55000, 45),
('30000000-0000-0000-0000-000000000022', '20000000-0000-0000-0000-000000000008', 40000, 50),
('30000000-0000-0000-0000-000000000023', '20000000-0000-0000-0000-000000000008', 40000, 50),
('30000000-0000-0000-0000-000000000024', '20000000-0000-0000-0000-000000000008', 40000, 50);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V6 migrations are forward-only, consistent with the V1-V7 baseline")
