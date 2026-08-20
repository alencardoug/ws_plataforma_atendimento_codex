"""AA-9: explicit, idempotent, operator-triggered D+1/D+7 seed action —
the only place `schedule_slots` is written to, reachable only through the
one gated endpoint in `scheduling/router.py`, never automatically and
never as a side effect of a query. See plan.md §4b.

Correction (2026-08-19, human decision: "faça este botão ir para a
oncologia geral"): scoped to the generalist specialty specifically — the
original flat count/creation across all 4 specialties meant this button
would essentially always seed `mastologia-oncologica` only (its
professionals' UUIDs sort lowest in `active_professional_specialty_pairs()`),
never the generalist specialty most customer queries actually fall back
to (AA-3a's default)."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from customer_care.scheduling.availability import GENERALIST_SLUG
from customer_care.scheduling.models import Professional, ProfessionalSpecialty, ScheduleSlot, Specialty

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
DEFAULT_UNIT_ID = "10000000-0000-0000-0000-000000000001"
SEED_HOUR_START, SEED_HOUR_END = 8, 18  # business hours, exclusive of 18:00 itself
TARGET_D1, TARGET_D7 = 1, 3


@dataclass(frozen=True)
class SeedResult:
    created_d1: int
    created_d7: int
    already_sufficient: bool


def _today_sao_paulo() -> date:
    return datetime.now(SAO_PAULO).date()


def next_business_day_sql(session: Session, candidate: date) -> date:
    return session.execute(text("SELECT scheduling.next_business_day(:d)"), {"d": candidate}).scalar_one()


def count_available_on(session: Session, target_date: date, specialty_id: UUID) -> int:
    """Counts by an explicit São Paulo day boundary, not Postgres `date()`
    (whose result depends on the session's `TimeZone` setting, which is
    not guaranteed to be `America/Sao_Paulo`) — avoids a latent
    off-by-one-day bug near midnight regardless of connection defaults.
    Scoped to `specialty_id` (correction, 2026-08-19) — always the
    generalist specialty in practice, since `ensure_seed_availability()`
    is this function's only caller."""
    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=SAO_PAULO)
    day_end = day_start + timedelta(days=1)
    return (
        session.scalar(
            select(func.count())
            .select_from(ScheduleSlot)
            .where(
                ScheduleSlot.status == "available",
                ScheduleSlot.specialty_id == specialty_id,
                ScheduleSlot.starts_at >= day_start,
                ScheduleSlot.starts_at < day_end,
            )
        )
        or 0
    )


def combine_sao_paulo(target_date: date, hour: int) -> datetime:
    return datetime(target_date.year, target_date.month, target_date.day, hour, 0, tzinfo=SAO_PAULO)


def _generalist_specialty_id(session: Session) -> UUID:
    specialty_id = session.scalar(select(Specialty.specialty_id).where(Specialty.slug == GENERALIST_SLUG))
    if specialty_id is None:
        raise RuntimeError(f"generalist specialty '{GENERALIST_SLUG}' not seeded — T008/T009 migrations must run first")
    return specialty_id


def active_professional_specialty_pairs(session: Session, specialty_id: UUID) -> list[tuple[UUID, UUID, int]]:
    """Scoped to `specialty_id` (correction, 2026-08-19) — always the
    generalist specialty in practice; previously unscoped, which meant
    this list was always exhausted by `mastologia-oncologica`'s
    professionals (lowest UUIDs) before any other specialty was tried."""
    rows = session.execute(
        select(ProfessionalSpecialty.professional_id, ProfessionalSpecialty.specialty_id, ProfessionalSpecialty.appointment_duration_minutes)
        .join(Professional, Professional.professional_id == ProfessionalSpecialty.professional_id)
        .where(Professional.active.is_(True), ProfessionalSpecialty.specialty_id == specialty_id)
        .order_by(ProfessionalSpecialty.professional_id)
    ).all()
    return [(row[0], row[1], row[2]) for row in rows]


def create_slots_on(session: Session, target_date: date, needed: int, specialty_id: UUID) -> int:
    """Tries (hour, professional) combinations in order —
    SEED_HOUR_START..SEED_HOUR_END-1, professionals round-robin within each
    hour, all within `specialty_id` (correction, 2026-08-19) — inserting
    with ON CONFLICT DO NOTHING and counting only actual inserts. Stops as
    soon as `needed` real inserts have happened."""
    if needed <= 0:
        return 0
    created = 0
    pairs = active_professional_specialty_pairs(session, specialty_id)
    for hour in range(SEED_HOUR_START, SEED_HOUR_END):
        for professional_id, specialty_id, duration in pairs:
            if created >= needed:
                return created
            starts_at = combine_sao_paulo(target_date, hour)
            result = session.execute(
                pg_insert(ScheduleSlot)
                .values(
                    unit_id=DEFAULT_UNIT_ID,
                    specialty_id=specialty_id,
                    professional_id=professional_id,
                    starts_at=starts_at,
                    ends_at=starts_at + timedelta(minutes=duration),
                    status="available",
                )
                .on_conflict_do_nothing(index_elements=["professional_id", "starts_at"])
                .returning(ScheduleSlot.slot_id)
            )
            if result.first() is not None:
                created += 1
    return created


_SEED_LOCK_KEY = 725017001  # arbitrary, fixed — this operation's own pg_advisory_xact_lock scope


WIDE_SEED_END_DATE = date(2026, 12, 30)
WIDE_SEED_SLOT_MINUTES = 45
_WIDE_SEED_LOCK_KEY = 725017002  # 006/SV-3: distinct from _SEED_LOCK_KEY, so this action and AA-9's D+1/D+7 button never block each other unnecessarily


@dataclass(frozen=True)
class SeedWideResult:
    specialty_count: int
    business_day_count: int
    slots_created: int


def _wide_seed_business_days(session: Session, today: date) -> list[date]:
    """Every business day from tomorrow through WIDE_SEED_END_DATE
    inclusive — reuses `next_business_day()` (already skips Sundays/
    `scheduling.holidays` non-business-day rows, already seeded through
    all of 2027) rather than duplicating that logic in Python."""
    days: list[date] = []
    candidate = today + timedelta(days=1)
    while True:
        business_day = next_business_day_sql(session, candidate)
        if business_day > WIDE_SEED_END_DATE:
            break
        days.append(business_day)
        candidate = business_day + timedelta(days=1)
    return days


def create_wide_slots_on(session: Session, target_date: date, specialty_id: UUID) -> int:
    """006/SV-2: every missing 45-minute slot for every active
    professional in this specialty, 08:00 up to (not including) 18:00 —
    14 slots/day/professional (08:00, 08:45, ..., 17:45; confirmed by
    direct computation, not hand arithmetic — (18:00-08:00)/45min = 13.33,
    so 14 start times fit strictly before 18:00). Unlike `create_slots_on()`
    (a fixed-count, round-robin-across-professionals target), this fills
    the whole grid: every professional gets a slot at every interval.
    `ON CONFLICT DO NOTHING` makes re-running safe by construction — no
    `already_sufficient` short-circuit needed (SV-3).

    Note: spec.md's own illustrative "13 slots/day/professional (08:00,
    08:45, ..., 17:15)" example does not reconcile with its own stated
    45-minute-spacing/18:00-exclusive rule under any reading — the actual
    count is 14, ending at 17:45, not 13 ending at 17:15 (nor 13 ending at
    17:00, an earlier miscount in this same file's own history — see git
    blame). This implements the operative numeric rule (45-minute spacing,
    08:00 start, 18:00-exclusive end), verified by both a direct Python
    computation and a real-database test
    (`test_appointment_wide_seeding.py`), not by hand arithmetic alone."""
    created = 0
    pairs = active_professional_specialty_pairs(session, specialty_id)
    current = combine_sao_paulo(target_date, SEED_HOUR_START)
    end = combine_sao_paulo(target_date, SEED_HOUR_END)
    while current < end:
        for professional_id, professional_specialty_id, duration in pairs:
            result = session.execute(
                pg_insert(ScheduleSlot)
                .values(
                    unit_id=DEFAULT_UNIT_ID,
                    specialty_id=professional_specialty_id,
                    professional_id=professional_id,
                    starts_at=current,
                    ends_at=current + timedelta(minutes=duration),
                    status="available",
                )
                .on_conflict_do_nothing(index_elements=["professional_id", "starts_at"])
                .returning(ScheduleSlot.slot_id)
            )
            if result.first() is not None:
                created += 1
        current += timedelta(minutes=WIDE_SEED_SLOT_MINUTES)
    return created


def ensure_wide_availability(session: Session) -> SeedWideResult:
    """006/SV-1..SV-4: a new, separate, one-time bulk-fill action — AA-9's
    own D+1/D+7 generalist-only button is untouched (it was deliberately
    narrowed to single-specialty scope by a 2026-08-19 correction that
    this action does not reopen). Every specialty is read live from
    `scheduling.specialties` (SV-2's own "automatically covers any
    specialty that exists by the time it runs" requirement) — never a
    hardcoded list."""
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _WIDE_SEED_LOCK_KEY})
    today = _today_sao_paulo()
    specialty_ids = session.scalars(select(Specialty.specialty_id)).all()
    business_days = _wide_seed_business_days(session, today)
    total_created = 0
    for target_date in business_days:
        for specialty_id in specialty_ids:
            total_created += create_wide_slots_on(session, target_date, specialty_id)
    return SeedWideResult(specialty_count=len(specialty_ids), business_day_count=len(business_days), slots_created=total_created)


def ensure_seed_availability(session: Session) -> SeedResult:
    """Holds a transaction-scoped Postgres advisory lock for the duration
    of this call (released automatically at commit/rollback) so two
    concurrent operator clicks can never both compute a stale "missing"
    count and each create slots beyond the 1×D+1/3×D+7 target — the second
    caller blocks until the first's transaction commits, then correctly
    re-counts and reports `already_sufficient=True` where appropriate.
    Uses an existing Postgres primitive, not new infrastructure
    (Article VIII)."""
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _SEED_LOCK_KEY})
    specialty_id = _generalist_specialty_id(session)
    today = _today_sao_paulo()
    d1 = next_business_day_sql(session, today + timedelta(days=1))
    d7 = next_business_day_sql(session, today + timedelta(days=7))
    count_d1 = count_available_on(session, d1, specialty_id)
    count_d7 = count_available_on(session, d7, specialty_id)
    if count_d1 >= TARGET_D1 and count_d7 >= TARGET_D7:
        return SeedResult(created_d1=0, created_d7=0, already_sufficient=True)
    created_d1 = create_slots_on(session, d1, TARGET_D1 - count_d1, specialty_id) if count_d1 < TARGET_D1 else 0
    created_d7 = create_slots_on(session, d7, TARGET_D7 - count_d7, specialty_id) if count_d7 < TARGET_D7 else 0
    return SeedResult(created_d1=created_d1, created_d7=created_d7, already_sufficient=False)
