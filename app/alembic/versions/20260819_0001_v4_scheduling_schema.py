"""V4: create the scheduling schema (correction) — units, specialties,
professionals, professional_specialties, holidays, schedule_slots, the
slot_status enum, next_business_day(), plus the original 3 specialties'
seed data.

Revision ID: 20260819_0001
Revises: 20260818_0001

See specs/004-dynamic-appointment-availability/{spec,plan,data-model}.md §2/§3/§5.
Correction found 2026-08-19 during the post-V3 production sync: neither
db/init/001_schema.sql nor db/init/002_seed_and_schedule.sql is mounted as
Postgres initdb.d content or referenced by any script — the `scheduling`
schema does not exist in the local Docker Compose database or in
production. This migration ports only the objects this feature's query
path (AA-2/AA-3) and seed action (AA-9) actually use, scoped down from
001_schema.sql: no slot_offers, available_offers,
ensure_demo_availability(), appointments, appointment_events, or any
identity.*/billing.*/governance.* object — those stay exactly as
unactivated as before (D-024). Uses CREATE ... IF NOT EXISTS and bare
ON CONFLICT DO NOTHING throughout so this migration is safe to apply
regardless of environment history, even though today no environment has
any pre-existing row to conflict with.
"""

from alembic import op

revision = "20260819_0001"
down_revision = "20260818_0001"
branch_labels = None
depends_on = None


DDL = r"""
CREATE SCHEMA IF NOT EXISTS scheduling;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'slot_status' AND n.nspname = 'scheduling'
    ) THEN
        CREATE TYPE scheduling.slot_status AS ENUM ('available', 'held', 'booked', 'blocked');
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS scheduling.units (
    unit_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    timezone text NOT NULL DEFAULT 'America/Sao_Paulo',
    simulated boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS scheduling.specialties (
    specialty_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug text NOT NULL UNIQUE,
    display_name text NOT NULL,
    description text NOT NULL,
    simulated boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS scheduling.professionals (
    professional_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name text NOT NULL,
    registration_display text,
    simulated boolean NOT NULL DEFAULT true,
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS scheduling.professional_specialties (
    professional_id uuid NOT NULL REFERENCES scheduling.professionals(professional_id),
    specialty_id uuid NOT NULL REFERENCES scheduling.specialties(specialty_id),
    fixed_price_cents integer NOT NULL CHECK (fixed_price_cents >= 0),
    appointment_duration_minutes integer NOT NULL DEFAULT 60 CHECK (appointment_duration_minutes > 0),
    PRIMARY KEY (professional_id, specialty_id)
);

CREATE TABLE IF NOT EXISTS scheduling.holidays (
    holiday_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    holiday_date date NOT NULL,
    name text NOT NULL,
    scope text NOT NULL CHECK (scope IN ('national','state','municipal','institutional')),
    state_code char(2),
    city_code text,
    unit_id uuid REFERENCES scheduling.units(unit_id),
    is_business_day boolean NOT NULL DEFAULT false,
    simulated boolean NOT NULL DEFAULT false
);

CREATE UNIQUE INDEX IF NOT EXISTS holidays_natural_key_idx ON scheduling.holidays (
    holiday_date, scope, coalesce(state_code,''), coalesce(city_code,''), coalesce(unit_id::text,'')
);

CREATE TABLE IF NOT EXISTS scheduling.schedule_slots (
    slot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_id uuid NOT NULL REFERENCES scheduling.units(unit_id),
    specialty_id uuid NOT NULL REFERENCES scheduling.specialties(specialty_id),
    professional_id uuid NOT NULL REFERENCES scheduling.professionals(professional_id),
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL,
    status scheduling.slot_status NOT NULL DEFAULT 'available',
    simulated boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (ends_at > starts_at),
    UNIQUE (professional_id, starts_at)
);

CREATE OR REPLACE FUNCTION scheduling.next_business_day(p_date date)
RETURNS date
LANGUAGE plpgsql
STABLE
AS $func$
DECLARE
    v_date date := p_date;
BEGIN
    LOOP
        IF extract(isodow FROM v_date) <> 7
           AND NOT EXISTS (
               SELECT 1 FROM scheduling.holidays h
               WHERE h.holiday_date = v_date AND NOT h.is_business_day
           ) THEN
            RETURN v_date;
        END IF;
        v_date := v_date + 1;
    END LOOP;
END;
$func$;

INSERT INTO scheduling.units (unit_id, name)
VALUES ('10000000-0000-0000-0000-000000000001', 'Unidade Central (simulação)')
ON CONFLICT DO NOTHING;

INSERT INTO scheduling.specialties (specialty_id, slug, display_name, description) VALUES
('20000000-0000-0000-0000-000000000001', 'mastologia-oncologica', 'Mastologia oncológica', 'Primeira consulta para suspeita ou diagnóstico de câncer de mama (simulação)'),
('20000000-0000-0000-0000-000000000002', 'cirurgia-colorretal', 'Cirurgia colorretal oncológica', 'Primeira consulta para suspeita ou diagnóstico colorretal (simulação)'),
('20000000-0000-0000-0000-000000000003', 'segunda-opiniao', 'Segunda opinião oncológica', 'Revisão de diagnóstico, exames e proposta terapêutica (simulação)')
ON CONFLICT DO NOTHING;

INSERT INTO scheduling.professionals (professional_id, display_name, registration_display) VALUES
('30000000-0000-0000-0000-000000000001', 'Dra. Helena Martins (simulação)', 'CRM-SP 000001 (simulação)'),
('30000000-0000-0000-0000-000000000002', 'Dra. Marina Lopes (simulação)', 'CRM-SP 000002 (simulação)'),
('30000000-0000-0000-0000-000000000003', 'Dra. Beatriz Nogueira (simulação)', 'CRM-SP 000003 (simulação)'),
('30000000-0000-0000-0000-000000000004', 'Dr. Rafael Almeida (simulação)', 'CRM-SP 000004 (simulação)'),
('30000000-0000-0000-0000-000000000005', 'Dr. Gustavo Mendes (simulação)', 'CRM-SP 000005 (simulação)'),
('30000000-0000-0000-0000-000000000006', 'Dra. Lívia Rocha (simulação)', 'CRM-SP 000006 (simulação)'),
('30000000-0000-0000-0000-000000000007', 'Dra. Camila Torres (simulação)', 'CRM-SP 000007 (simulação)'),
('30000000-0000-0000-0000-000000000008', 'Dr. André Ferreira (simulação)', 'CRM-SP 000008 (simulação)'),
('30000000-0000-0000-0000-000000000009', 'Dra. Paula Azevedo (simulação)', 'CRM-SP 000009 (simulação)')
ON CONFLICT DO NOTHING;

INSERT INTO scheduling.professional_specialties
    (professional_id, specialty_id, fixed_price_cents, appointment_duration_minutes)
VALUES
('30000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001',98000,60),
('30000000-0000-0000-0000-000000000002','20000000-0000-0000-0000-000000000001',98000,60),
('30000000-0000-0000-0000-000000000003','20000000-0000-0000-0000-000000000001',98000,60),
('30000000-0000-0000-0000-000000000004','20000000-0000-0000-0000-000000000002',105000,60),
('30000000-0000-0000-0000-000000000005','20000000-0000-0000-0000-000000000002',105000,60),
('30000000-0000-0000-0000-000000000006','20000000-0000-0000-0000-000000000002',105000,60),
('30000000-0000-0000-0000-000000000007','20000000-0000-0000-0000-000000000003',145000,90),
('30000000-0000-0000-0000-000000000008','20000000-0000-0000-0000-000000000003',145000,90),
('30000000-0000-0000-0000-000000000009','20000000-0000-0000-0000-000000000003',145000,90)
ON CONFLICT DO NOTHING;

INSERT INTO scheduling.holidays (holiday_date, name, scope, state_code, city_code) VALUES
('2026-01-01','Confraternização Universal','national',NULL,NULL),
('2026-04-03','Paixão de Cristo','national',NULL,NULL),
('2026-04-21','Tiradentes','national',NULL,NULL),
('2026-05-01','Dia Mundial do Trabalho','national',NULL,NULL),
('2026-09-07','Independência do Brasil','national',NULL,NULL),
('2026-10-12','Nossa Senhora Aparecida','national',NULL,NULL),
('2026-11-02','Finados','national',NULL,NULL),
('2026-11-15','Proclamação da República','national',NULL,NULL),
('2026-11-20','Dia Nacional de Zumbi e da Consciência Negra','national',NULL,NULL),
('2026-12-25','Natal','national',NULL,NULL),
('2026-01-25','Aniversário de São Paulo','municipal','SP','SAO_PAULO'),
('2026-07-09','Revolução Constitucionalista','state','SP',NULL),
('2027-01-01','Confraternização Universal','national',NULL,NULL),
('2027-04-21','Tiradentes','national',NULL,NULL),
('2027-05-01','Dia Mundial do Trabalho','national',NULL,NULL),
('2027-09-07','Independência do Brasil','national',NULL,NULL),
('2027-10-12','Nossa Senhora Aparecida','national',NULL,NULL),
('2027-11-02','Finados','national',NULL,NULL),
('2027-11-15','Proclamação da República','national',NULL,NULL),
('2027-11-20','Dia Nacional de Zumbi e da Consciência Negra','national',NULL,NULL),
('2027-12-25','Natal','national',NULL,NULL)
ON CONFLICT DO NOTHING;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V4 migrations are forward-only, consistent with the V1/V2/V3 baseline")
