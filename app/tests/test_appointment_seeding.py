"""T041: real-database integration tests for ensure_seed_availability()
(AA-9). specs/004-dynamic-appointment-availability/plan.md §4b,
acceptance.md §D/§E."""

import threading
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import delete, select

from customer_care.infrastructure.database import get_session_factory
from customer_care.scheduling.models import Professional, ScheduleSlot
from customer_care.scheduling.seeding import (
    SEED_HOUR_END,
    SEED_HOUR_START,
    TARGET_D1,
    TARGET_D7,
    SeedResult,
    count_available_on,
    ensure_seed_availability,
    next_business_day_sql,
)

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
# oncologia-geral (data-model.md §6) — the seed action is scoped to this
# specialty specifically (correction, 2026-08-19: "faça este botão ir para
# a oncologia geral").
GENERALIST_SPECIALTY_ID = UUID("20000000-0000-0000-0000-000000000004")


def _day_bounds(target_date: date) -> tuple[datetime, datetime]:
    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=SAO_PAULO)
    return start, start + timedelta(days=1)


def _slots_on(session, target_date: date) -> list[ScheduleSlot]:
    start, end = _day_bounds(target_date)
    return list(session.scalars(select(ScheduleSlot).where(ScheduleSlot.starts_at >= start, ScheduleSlot.starts_at < end)))


def _target_dates() -> tuple[date, date]:
    with get_session_factory()() as db:
        today = datetime.now(SAO_PAULO).date()
        d1 = next_business_day_sql(db, today + timedelta(days=1))
        d7 = next_business_day_sql(db, today + timedelta(days=7))
    return d1, d7


def _clear_slots_on(*target_dates: date) -> None:
    session_factory = get_session_factory()
    with session_factory() as db:
        for target_date in target_dates:
            start, end = _day_bounds(target_date)
            db.execute(delete(ScheduleSlot).where(ScheduleSlot.starts_at >= start, ScheduleSlot.starts_at < end))
        db.commit()


@pytest.fixture
def clean_target_dates() -> tuple[date, date]:
    d1, d7 = _target_dates()
    _clear_slots_on(d1, d7)
    yield d1, d7
    _clear_slots_on(d1, d7)


def test_from_zero_creates_exactly_target_counts_within_business_hours(clean_target_dates: tuple[date, date]) -> None:
    d1, d7 = clean_target_dates
    session_factory = get_session_factory()

    with session_factory() as db:
        result = ensure_seed_availability(db)
        db.commit()

    assert result.created_d1 == TARGET_D1
    assert result.created_d7 == TARGET_D7
    assert result.already_sufficient is False

    with session_factory() as db:
        assert count_available_on(db, d1, GENERALIST_SPECIALTY_ID) == TARGET_D1
        assert count_available_on(db, d7, GENERALIST_SPECIALTY_ID) == TARGET_D7
        for target_date in (d1, d7):
            for slot in _slots_on(db, target_date):
                local_hour = slot.starts_at.astimezone(SAO_PAULO).hour
                assert SEED_HOUR_START <= local_hour < SEED_HOUR_END
                assert slot.specialty_id == GENERALIST_SPECIALTY_ID


def test_second_immediate_call_creates_nothing_and_reports_already_sufficient(clean_target_dates: tuple[date, date]) -> None:
    session_factory = get_session_factory()
    with session_factory() as db:
        ensure_seed_availability(db)
        db.commit()

    with session_factory() as db:
        result = ensure_seed_availability(db)
        db.commit()

    assert result == SeedResult(created_d1=0, created_d7=0, already_sufficient=True)


def test_partial_state_creates_exactly_what_is_missing(clean_target_dates: tuple[date, date]) -> None:
    d1, d7 = clean_target_dates
    session_factory = get_session_factory()

    with session_factory() as db:
        first = ensure_seed_availability(db)
        db.commit()
    assert first.created_d1 == TARGET_D1
    assert first.created_d7 == TARGET_D7

    # Remove 2 of the 3 d7 slots to simulate a partial state; d1 stays untouched (already at target).
    with session_factory() as db:
        d7_slots = _slots_on(db, d7)
        for slot in d7_slots[1:]:
            db.delete(slot)
        db.commit()

    with session_factory() as db:
        result = ensure_seed_availability(db)
        db.commit()

    assert result.created_d1 == 0
    assert result.created_d7 == 2
    assert result.already_sufficient is False


def test_deactivated_professional_never_receives_a_generated_slot(clean_target_dates: tuple[date, date]) -> None:
    d1, _d7 = clean_target_dates
    # One of the generalist specialty's own 3 professionals (data-model.md
    # §6) — deactivating a non-generalist professional would test nothing
    # now that the seed action is scoped to the generalist specialty only.
    deactivated_id = UUID("30000000-0000-0000-0000-000000000010")
    session_factory = get_session_factory()

    with session_factory() as db:
        professional = db.get(Professional, deactivated_id)
        assert professional is not None
        original_active = professional.active
        professional.active = False
        db.commit()

    try:
        with session_factory() as db:
            ensure_seed_availability(db)
            db.commit()

        with session_factory() as db:
            slots = _slots_on(db, d1)
            assert all(slot.professional_id != deactivated_id for slot in slots)
    finally:
        with session_factory() as db:
            professional = db.get(Professional, deactivated_id)
            assert professional is not None
            professional.active = original_active
            db.commit()


def test_next_business_day_skips_sunday() -> None:
    with get_session_factory()() as db:
        assert next_business_day_sql(db, date(2026, 8, 23)) == date(2026, 8, 24)  # Sunday -> Monday


def test_next_business_day_skips_national_holiday() -> None:
    with get_session_factory()() as db:
        # 2026-09-07 (Independência do Brasil) is a Monday and a seeded national holiday.
        assert next_business_day_sql(db, date(2026, 9, 7)) == date(2026, 9, 8)


def test_saturday_is_a_business_day() -> None:
    with get_session_factory()() as db:
        assert next_business_day_sql(db, date(2026, 8, 22)) == date(2026, 8, 22)  # Saturday stays Saturday


def test_concurrent_calls_never_exceed_target(clean_target_dates: tuple[date, date]) -> None:
    d1, d7 = clean_target_dates
    session_factory = get_session_factory()
    barrier = threading.Barrier(2)
    errors: list[Exception] = []

    def worker() -> None:
        try:
            with session_factory() as db:
                barrier.wait(timeout=5)
                ensure_seed_availability(db)
                db.commit()
        except Exception as exc:  # pragma: no cover - surfaced via `errors` assertion below
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    with session_factory() as db:
        assert count_available_on(db, d1, GENERALIST_SPECIALTY_ID) == TARGET_D1
        assert count_available_on(db, d7, GENERALIST_SPECIALTY_ID) == TARGET_D7
