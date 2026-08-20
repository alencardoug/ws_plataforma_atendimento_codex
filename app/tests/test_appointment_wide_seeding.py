"""006/SV: real-database integration tests for ensure_wide_availability().
`create_wide_slots_on()` and `_wide_seed_business_days()` (the building
blocks) are exercised directly rather than the top-level
`ensure_wide_availability()` function, which — against the real
2026-12-30 end date and all 8 specialties — would write tens of thousands
of rows on every test run; that full-volume verification belongs to the
credential-backed smoke suite (spec.md §8 outcome 3's own "verified by
direct query" framing), not a fast repeatable unit test.
specs/006-specialty-scheduling-breadth/plan.md §4, data-model.md."""

from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select

from customer_care.infrastructure.database import get_session_factory
from customer_care.scheduling.models import ScheduleSlot
from customer_care.scheduling.seeding import (
    WIDE_SEED_END_DATE,
    WIDE_SEED_SLOT_MINUTES,
    _wide_seed_business_days,
    create_wide_slots_on,
)

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
# psico-oncologia (006/SS, data-model.md §3) — a specialty this feature's
# own migration adds, distinct from AA-9's own generalist-only scope.
PSICO_ONCOLOGIA_SPECIALTY_ID = UUID("20000000-0000-0000-0000-000000000005")


def _day_bounds(target_date: date) -> tuple[datetime, datetime]:
    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=SAO_PAULO)
    return start, start + timedelta(days=1)


def _slots_on(session, target_date: date, specialty_id: UUID) -> list[ScheduleSlot]:
    start, end = _day_bounds(target_date)
    return list(session.scalars(select(ScheduleSlot).where(ScheduleSlot.starts_at >= start, ScheduleSlot.starts_at < end, ScheduleSlot.specialty_id == specialty_id)))


class TestWideSeedBusinessDays:
    def test_every_returned_day_is_at_most_the_end_date_and_never_a_sunday(self) -> None:
        with get_session_factory()() as db:
            today = datetime.now(SAO_PAULO).date()
            days = _wide_seed_business_days(db, today)
        assert days, "expected at least one business day between tomorrow and 2026-12-30"
        assert all(day <= WIDE_SEED_END_DATE for day in days)
        assert all(day.isoweekday() != 7 for day in days)  # Sunday excluded
        assert days == sorted(days), "must be strictly increasing"
        assert len(set(days)) == len(days), "no duplicate day"

    def test_returns_an_empty_list_once_past_the_end_date(self) -> None:
        with get_session_factory()() as db:
            days = _wide_seed_business_days(db, WIDE_SEED_END_DATE + timedelta(days=1))
        assert days == []


class TestCreateWideSlotsOn:
    def test_creates_fourteen_slots_per_active_professional_forty_five_minutes_apart(self) -> None:
        target_date = date(2027, 3, 15)  # a Monday, far outside any real seed window this test's own cleanup can't reach
        session_factory = get_session_factory()
        try:
            with session_factory() as db:
                created = create_wide_slots_on(db, target_date, PSICO_ONCOLOGIA_SPECIALTY_ID)
                db.commit()
            assert created == 14 * 3  # 14 intervals/day (08:00..17:45) × 3 seeded professionals — confirmed against a real database, not hand arithmetic
            with session_factory() as db:
                slots = sorted(_slots_on(db, target_date, PSICO_ONCOLOGIA_SPECIALTY_ID), key=lambda row: (row.starts_at, row.professional_id))
            assert len(slots) == 42
            starts = sorted({slot.starts_at for slot in slots})
            assert len(starts) == 14
            for earlier, later in zip(starts, starts[1:]):  # deliberately offset by one — strict=True would always raise here
                assert (later - earlier) == timedelta(minutes=WIDE_SEED_SLOT_MINUTES)
            assert starts[0].astimezone(SAO_PAULO).hour == 8 and starts[0].astimezone(SAO_PAULO).minute == 0
            # 08:00 + 13×45min = 17:45 — the 14th and last interval, strictly
            # before 18:00. spec.md's own illustrative "13 slots (08:00, ...,
            # 17:15)" example does not reconcile with its own stated
            # 45-minute-spacing/18:00-exclusive rule under any reading — this
            # implements the operative rule, verified here against a real
            # database (seeding.py's own docstring has the full note).
            assert starts[-1].astimezone(SAO_PAULO).hour == 17 and starts[-1].astimezone(SAO_PAULO).minute == 45
        finally:
            with session_factory() as db:
                start, end = _day_bounds(target_date)
                db.execute(delete(ScheduleSlot).where(ScheduleSlot.starts_at >= start, ScheduleSlot.starts_at < end, ScheduleSlot.specialty_id == PSICO_ONCOLOGIA_SPECIALTY_ID))
                db.commit()

    def test_second_call_on_the_same_day_creates_nothing_idempotent(self) -> None:
        target_date = date(2027, 3, 16)  # a Tuesday
        session_factory = get_session_factory()
        try:
            with session_factory() as db:
                create_wide_slots_on(db, target_date, PSICO_ONCOLOGIA_SPECIALTY_ID)
                db.commit()
            with session_factory() as db:
                second_call_created = create_wide_slots_on(db, target_date, PSICO_ONCOLOGIA_SPECIALTY_ID)
                db.commit()
            assert second_call_created == 0
        finally:
            with session_factory() as db:
                start, end = _day_bounds(target_date)
                db.execute(delete(ScheduleSlot).where(ScheduleSlot.starts_at >= start, ScheduleSlot.starts_at < end, ScheduleSlot.specialty_id == PSICO_ONCOLOGIA_SPECIALTY_ID))
                db.commit()
