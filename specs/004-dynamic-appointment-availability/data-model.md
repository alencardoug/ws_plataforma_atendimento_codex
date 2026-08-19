# Data Model: Dynamic Appointment Availability

**Correction (2026-08-19):** an earlier version of this document claimed
the `scheduling` schema's tables "already exist" (`db/init/001_schema.sql`,
"applied before Alembic history began"). Verified false against both the
local Docker Compose database and Neon production — neither file is
mounted as `initdb.d` content, referenced by any script, or ported into an
Alembic migration; `scheduling.specialties` exists in neither database.
`spec.md` §2 and `plan.md` §3 now record this correctly. **Four new
migrations were delivered**, from three design rounds plus one
implementation finding: §5's schema one
(creating the `scheduling` schema itself, scoped to what this feature
uses, plus the original 3 specialties' seed data — new, this correction),
§6's data-only one (seeding the new generalist specialty, AA-3a — the same
kind of reference data `db/init/002_seed_and_schedule.sql` already defines
for the original 3 specialties, just applied the correct way since that
file is wired into nothing), and §8's real schema one (two additive,
nullable columns supporting AA-10's booking script), and §8's narrow
`messages_check` correction discovered during Phase 9. This document
records the new SQLAlchemy ORM mappings this feature adds, all four
migrations, and confirms nothing else about the schema's shape changes.

## 1. New ORM mappings (`app/customer_care/scheduling/models.py`)

All map to columns §5's new migration creates; none of these classes
trigger a migration of their own.

| Class | Table | Columns mapped | Notes |
|---|---|---|---|
| `Specialty` | `scheduling.specialties` | `specialty_id`, `slug`, `display_name`, `description` | `slug` is the vocabulary `SPECIALTY_KEYWORDS` (`plan.md` §5) keys off |
| `Professional` | `scheduling.professionals` | `professional_id`, `display_name`, `active` | `registration_display`/`simulated` not mapped — unused by this feature |
| `ProfessionalSpecialty` | `scheduling.professional_specialties` | `professional_id`, `specialty_id`, `fixed_price_cents`, `appointment_duration_minutes` | composite PK, both FKs |
| `Unit` | `scheduling.units` | `unit_id`, `name`, `timezone` | `simulated` not mapped |
| `ScheduleSlot` | `scheduling.schedule_slots` | `slot_id`, `unit_id`, `specialty_id`, `professional_id`, `starts_at`, `ends_at`, `status` | the only `scheduling` table this feature writes to (insert-only), and only from `scheduling/seeding.py` — never from `scheduling/availability.py` (`plan.md` §4/§4b) |

`scheduling.holidays` is **not** ORM-mapped — no Python code needs a
`Holiday` row directly; only `scheduling.next_business_day()`'s already-
correct output is used, and only by `scheduling/seeding.py` (`plan.md`
§4b) — the query path (`availability.py`) no longer calls it at all, since
it no longer computes D+1/D+7 (revised 2026-08-18, `spec.md` §5 item 6).

`scheduling.slot_offers`, `scheduling.available_offers`,
`scheduling.appointments`, `scheduling.appointment_events`,
`identity.patients`, `identity.consent_records`, and `billing.payments` are
**not** mapped by this feature and remain exactly as dormant as before
(D-024) — no import path in `scheduling/models.py`, `scheduling/availability.py`,
or `scheduling/seeding.py` references any of them (acceptance outcome 7,
verified by a structural test, not just by absence of a call in the demo
path).

## 2. `ScheduleSlot` write path

The only write this feature performs in the `scheduling` schema, and the
only one anywhere in `scheduling/seeding.py` (never in
`scheduling/availability.py`, the query path — revised 2026-08-18,
`spec.md` §5 items 6-7):

```sql
INSERT INTO scheduling.schedule_slots (unit_id, specialty_id, professional_id, starts_at, ends_at, status)
VALUES (...)
ON CONFLICT (professional_id, starts_at) DO NOTHING
```

Reachable only via `POST /operator/scheduling/ensure-availability`
(operator-authenticated, `plan.md` §4b) — never automatically, never as a
side effect of a customer/operator query. Bounded to at most 4 inserts per
call (`TARGET_D1=1` + `TARGET_D7=3`, minus whatever already exists on
those two dates). This reuses the `UNIQUE (professional_id, starts_at)`
constraint T008's schema migration creates (faithfully ported from
`001_schema.sql` line 164). `status` is always inserted as `'available'`;
this feature never transitions a slot to any other `scheduling.slot_status`
enum value (that enum's other states — held/booked/etc., referenced by
`appointments`, D-024 — remain reachable only by the still-unauthorized
booking feature).

## 3. `content.qa_entries` — no column change, data cleanup only

`dynamic_resolver` already exists (added before V1, confirmed
`app/customer_care/infrastructure/models.py:141`). No new column, no
migration. This feature's only `content.qa_entries` change is data-level:
soft-deactivating the 5 out-of-scope `agenda` entries (`plan.md` §8) through
the existing authenticated CRUD endpoint (`DELETE
/operator/knowledge/qa/{qa_id}` → `is_active = false`), and
creating/editing a handful of in-scope entries the same way. Both are
ordinary, already-audited (`knowledge.qa_created`/`knowledge.qa_updated`/
`knowledge.qa_deactivated`) operator actions — no new audit event type.

## 4. Integrity notes

- `ScheduleSlot.specialty_id`/`professional_id`/`unit_id` FKs are already
  enforced by the existing schema — this feature's insert can never create
  an orphaned slot.
- `ensure_seed_availability()` (`plan.md` §4b) is safe to call concurrently
  from two simultaneous button clicks. **Correction (found during Phase 4
  implementation, T040):** the original text here claimed `UNIQUE
  (professional_id, starts_at)` plus `ON CONFLICT DO NOTHING` alone made
  this safe under races. That is false for two calls that are genuinely
  concurrent (not merely sequential-but-close): if both read the same
  stale "missing" count before either commits, a collision on their first
  candidate slot only stops *that one* candidate from double-inserting —
  each caller's loop simply moves on to try the *next* candidate, and both
  can succeed on different slots, together exceeding the target. Fixed by
  a transaction-scoped `pg_advisory_xact_lock` at the start of
  `ensure_seed_availability()` (`scheduling/seeding.py`): the second
  concurrent caller now blocks until the first's whole transaction
  commits, then correctly re-counts against real post-commit state before
  deciding what (if anything) to create. Verified by
  `test_appointment_seeding.py`'s dedicated concurrency test (real
  threads, `threading.Barrier`-synchronized). No new infrastructure —
  advisory locks are a built-in Postgres primitive (Article VIII).
- No cascade behavior changes: this feature adds no FK pointing *at* any
  table another module owns, so no existing cascade-delete/deactivate path
  is affected.

## 5. New migration: create the `scheduling` schema (correction, prerequisite for AA-2/AA-3a/AA-9)

A real schema migration — not, as an earlier version of this document
claimed, something that "already exists." Ports `db/init/001_schema.sql`'s
shape for exactly the objects this feature uses, plus
`002_seed_and_schedule.sql`'s original seed data (units, the 3
diagnosis-specific specialties, 9 professionals, `professional_specialties`,
holidays) — both files verbatim for the parts this feature needs, neither
file wired into any automated init path (the correction, `spec.md` §2).
Deliberately excludes `slot_offers`, `available_offers`,
`ensure_demo_availability()`, `appointments`, `appointment_events`, and
every `identity.*`/`billing.*`/`governance.*` object — those stay exactly
as unactivated as before (D-024, `spec.md` §6); nothing in this feature
needs them to exist. Forward-only, `downgrade()` raises, matching this
codebase's convention. Uses `CREATE TABLE IF NOT EXISTS` (matching the V1
baseline migration's own defensive style) and bare `ON CONFLICT DO
NOTHING` on every seed `INSERT` (matching `002_seed_and_schedule.sql`'s
own style) so the migration is safe to design once and apply to any
environment, even though today neither local nor production actually has
any pre-existing row to conflict with.

```sql
CREATE SCHEMA IF NOT EXISTS scheduling;

CREATE TYPE scheduling.slot_status AS ENUM ('available', 'held', 'booked', 'blocked');

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
```

Idempotent by construction: `CREATE ... IF NOT EXISTS`/bare `ON CONFLICT DO
NOTHING` throughout, matching this codebase's established convention for a
migration that must apply cleanly regardless of environment history.
`pgcrypto` (for `gen_random_uuid()`) is already installed by the V1
baseline migration — no new extension needed.

## 6. New migration: the generalist specialty (AA-3a)

Data-only — no `CREATE TABLE`/`ALTER TABLE`, only `INSERT`s into the
tables §5's migration just created, following exactly the same shape
`002_seed_and_schedule.sql` already used for the original 3 specialties.
Depends on §5's migration having already run (chained `down_revision`).
Forward-only (matching every other migration in this codebase's
convention); `downgrade()` raises, same as V3's category migration.

```sql
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
```

3 professionals (mirroring the existing 3-per-specialty pattern), priced
and timed as a "simple" consultation — shorter and cheaper than the
diagnosis-specific specialties (`mastologia-oncologica`/
`cirurgia-colorretal` are 60min/R$980-1050; `segunda-opiniao` is 90min/
R$1450; this generalist triage consultation is 45min/R$600), matching the
human's own framing ("consulta simples"). All data synthetic (Constitution
Article VI), same `(simulação)` convention as every other seeded row.

Idempotent by construction for a migration (`INSERT` with fixed UUIDs, run
exactly once by Alembic's own bookkeeping — no `ON CONFLICT` needed here,
unlike the runtime seed action's repeatable insert in §2).

## 7. New audit event (AA-9)

`scheduling.availability_seeded` (`customer_service.audit_events`, no
schema change — the existing generic audit-event table, same as every
other event type). Payload: `created_d1`, `created_d7`,
`already_sufficient`; the operator identity is
stored in the audit row's standard `actor_id` column, not duplicated in
the JSON payload. Emitted by `scheduling/router.py`'s one endpoint, never
by the query path.

## 8. New migration: booking-script columns (AA-10)

A real schema change — additive columns on already-Alembic-tracked tables
(`customer_service.conversations`/`messages`, created by the V1 baseline
migration, unaffected by the §5/§6 correction above). Forward-only,
`downgrade()` raises, matching this codebase's convention.

```sql
ALTER TABLE customer_service.conversations
  ADD COLUMN booking_script_step text NULL
  CHECK (booking_script_step IS NULL OR booking_script_step IN ('AWAITING_CPF', 'AWAITING_PAYMENT'));

ALTER TABLE customer_service.messages
  ADD COLUMN autonomous_source text NULL
  CHECK (autonomous_source IS NULL OR autonomous_source IN ('booking_script'));
```

- **`conversations.booking_script_step`** — transient flow-position
  marker (`plan.md` §8b). `NULL` means "no script in progress" (either
  never started, or just completed and reset). A `CHECK` constraint
  enumerates the only two valid in-progress values at the database level,
  not just in application code — a third, unauthorized step value can
  never be written even by a future bug. **Never holds the customer's CPF
  or payment answer** — only which fixed prompt the conversation is
  waiting on. Mutable relational state (Constitution Article IX's
  "normal transactional state," not a fact requiring audit immutability),
  the same category as `Conversation.status`/`effective_mode` already are.
- **`messages.autonomous_source`** — `NULL` for every message in the
  system except the ones `booking_script/service.py`'s
  `send_scripted_message()` creates, which get `'booking_script'`. A
  `CHECK` constraint again enumerates the only legal value at the database
  level — this column existing at all, with exactly one legal non-null
  value, is itself part of how Constitution Amendment 1.1.0's narrow scope
  is enforced structurally, not just documented. This is the field the
  frontend's optional "automático" badge (`tasks.md`) would key off, and
  the field `acceptance.md`'s containment tests query directly.

**Correction, found during Phase 9 implementation (T093):** the V1
baseline's own `messages_check` constraint — `(author_type='CUSTOMER' AND
operator_id IS NULL) OR (author_type='OPERATOR' AND operator_id IS NOT
NULL)` — rejects `send_scripted_message()`'s insert outright, since that
call has no operator in context by design and therefore cannot supply
`operator_id`. A second migration (`20260819_0004`) narrowly widens this
constraint with exactly one more disjunct: `author_type='OPERATOR' AND
operator_id IS NULL AND autonomous_source='booking_script'`. This is
itself a structural enforcement of the amendment's narrow scope — an
`OPERATOR`-authored message can have a `NULL` `operator_id` for
*no other reason*, at the database level, not just in application code.

Both columns are additive and nullable — no backfill needed, no existing
row's meaning changes, unrelated to AA-3a's migration (kept as two
separate migrations, `plan.md` §12, since they address unrelated concerns
authorized in different clarification rounds).

No column is added for CPF or payment input. During AA-10's two sensitive
steps, `anonymous_access/router.py` passes the raw request body directly
to the parser but persists a fixed disclosure marker as the customer
`Message.body`. The formatted CPF is persisted only inside the exact,
fixed `"CPF ... confirmado"` autonomous output required by the script;
there is no identity/profile field or reusable structured value.

## 9. New audit event (AA-10)

`booking_script.autonomous_message_sent` (`customer_service.audit_events`,
no schema change). Payload: `conversation_id`, `message_id`, `step` (the
script step in effect when this message was sent). **Never the customer's
raw CPF or raw payment-question reply, and never the sent message's own
body** (redundant with `messages.body`, and keeping it out of the audit
payload removes any temptation to search audit logs for customer-adjacent
text here). This is the one event type in the entire catalog that exists
specifically so a reviewer can enumerate every customer-visible message
ever sent without an operator's click, in one query — see `plan.md` §8b.
