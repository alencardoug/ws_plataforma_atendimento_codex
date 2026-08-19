# Data Model: Dynamic Appointment Availability

No schema change (no new table/column/index/constraint) is required —
every table this feature reads or writes already exists
(`db/init/001_schema.sql`, applied before Alembic history began, preserved
as-is per V1 `plan.md` §1). **One data-only migration is still needed**
(§5, added 2026-08-18): seeding a new generalist specialty, the same kind
of reference data `db/init/002_seed_and_schedule.sql` already contains for
the original 3 specialties — it just can't go in that frozen file, so it
goes in a migration instead. This document records the new SQLAlchemy ORM
mappings this feature adds, that one migration, and confirms nothing else
about the existing schema's shape changes.

## 1. New ORM mappings (`app/customer_care/scheduling/models.py`)

All map to columns that already exist; none of these classes trigger a
migration.

| Class | Table | Columns mapped | Notes |
|---|---|---|---|
| `Specialty` | `scheduling.specialties` | `specialty_id`, `slug`, `display_name`, `description` | `slug` is the vocabulary `SPECIALTY_KEYWORDS` (`plan.md` §5) keys off |
| `Professional` | `scheduling.professionals` | `professional_id`, `display_name`, `active` | `registration_display`/`simulated` not mapped — unused by this feature |
| `ProfessionalSpecialty` | `scheduling.professional_specialties` | `professional_id`, `specialty_id`, `fixed_price_cents`, `appointment_duration_minutes` | composite PK, both FKs |
| `Unit` | `scheduling.units` | `unit_id`, `name`, `timezone` | `simulated` not mapped |
| `ScheduleSlot` | `scheduling.schedule_slots` | `slot_id`, `unit_id`, `specialty_id`, `professional_id`, `starts_at`, `ends_at`, `status` | the only table this feature writes to (insert-only), and only from `scheduling/seeding.py` — never from `scheduling/availability.py` (`plan.md` §4/§4b) |

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

The only write this feature performs, and the only one anywhere in
`scheduling/seeding.py` (never in `scheduling/availability.py`, the query
path — revised 2026-08-18, `spec.md` §5 items 6-7):

```sql
INSERT INTO scheduling.schedule_slots (unit_id, specialty_id, professional_id, starts_at, ends_at, status)
VALUES (...)
ON CONFLICT (professional_id, starts_at) DO NOTHING
```

Reachable only via `POST /operator/scheduling/ensure-availability`
(operator-authenticated, `plan.md` §4b) — never automatically, never as a
side effect of a customer/operator query. Bounded to at most 3 inserts per
call (`TARGET_D1=1` + `TARGET_D7=3`, minus whatever already exists on
those two dates). This reuses the `UNIQUE (professional_id, starts_at)`
constraint `001_schema.sql` already defines (line 164) — no new
constraint, no new index. `status` is always inserted as `'available'`;
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
  from two simultaneous button clicks: the `UNIQUE (professional_id,
  starts_at)` constraint plus `ON CONFLICT DO NOTHING` makes the operation
  naturally idempotent under races, not just under sequential
  re-invocation — worst case, two concurrent calls both see the same
  "missing" count and both attempt to insert the same candidate slots, but
  only one of each insert actually lands, and neither ever exceeds the
  1×D+1/3×D+7 target because both re-count from the database's actual
  post-commit state on their next call, not from an in-memory guess.
- No cascade behavior changes: this feature adds no FK pointing *at* any
  table another module owns, so no existing cascade-delete/deactivate path
  is affected.

## 5. New migration: the generalist specialty (AA-3a)

Data-only — no `CREATE TABLE`/`ALTER TABLE`, only `INSERT`s into tables
that already exist, following exactly the same shape
`002_seed_and_schedule.sql` already used for the original 3 specialties.
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

## 6. New audit event

`scheduling.availability_seeded` (`customer_service.audit_events`, no
schema change — the existing generic audit-event table, same as every
other event type). Payload: `operator_id`, `created_d1`, `created_d7`,
`already_sufficient`. Emitted by `scheduling/router.py`'s one endpoint,
never by the query path.
