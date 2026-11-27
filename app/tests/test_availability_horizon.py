"""D-046: next-business-day offer window (specs/004 §8) and the rolling
60-day availability horizon (specs/012 §11, RH-1..RH-4). Real database.

The horizon tests use a throwaway specialty + professional so they can
observe a specialty with *no* slots at all, without touching the shared
dev database's seeded agenda."""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text

from customer_care.bootstrap import create_app
from customer_care.infrastructure.database import get_session_factory
from customer_care.scheduling import seeding
from customer_care.scheduling.availability import earliest_offer_start, resolve_appointment_availability
from customer_care.scheduling.models import Professional, ProfessionalSpecialty, ScheduleSlot, Specialty

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
_UNIT_ID = "10000000-0000-0000-0000-000000000001"


def _next_business_day(db, day):
    return db.execute(text("SELECT scheduling.next_business_day(:d)"), {"d": day}).scalar_one()


class TestNextBusinessDayWindow:
    def test_earliest_offer_start_is_midnight_of_the_next_business_day(self) -> None:
        with get_session_factory()() as db:
            today = datetime.now(SAO_PAULO).date()
            expected_day = _next_business_day(db, today + timedelta(days=1))
            start = earliest_offer_start(db)
        assert start == datetime(expected_day.year, expected_day.month, expected_day.day, tzinfo=SAO_PAULO)
        assert start.date() > today
        assert start.isoweekday() != 7

    def test_a_slot_later_today_is_never_offered(self) -> None:
        """The reported bug: a generalist slot 30 minutes from now was the
        first offer."""
        factory = get_session_factory()
        soon = datetime.now(UTC).replace(microsecond=0) + timedelta(minutes=30)
        with factory() as db:
            pair = db.execute(
                select(ProfessionalSpecialty.professional_id, ProfessionalSpecialty.specialty_id)
                .join(Specialty, Specialty.specialty_id == ProfessionalSpecialty.specialty_id)
                .where(Specialty.slug == "oncologia-geral")
                .limit(1)
            ).first()
            assert pair is not None, "generalist specialty must have a professional"
            slot = ScheduleSlot(unit_id=_UNIT_ID, specialty_id=pair[1], professional_id=pair[0], starts_at=soon, ends_at=soon + timedelta(minutes=30), status="available")
            db.add(slot)
            db.commit()
            slot_id = slot.slot_id
        try:
            with factory() as db:
                start = earliest_offer_start(db)
                try:
                    _resolution, rows = resolve_appointment_availability(db, "quero agendar uma consulta")
                except Exception:  # an empty agenda is not this test's concern
                    rows = []
            for row in rows:
                assert row[0].slot_id != slot_id
                assert row[0].starts_at >= start
        finally:
            with factory() as db:
                db.execute(delete(ScheduleSlot).where(ScheduleSlot.slot_id == slot_id))
                db.commit()


@pytest.fixture
def empty_specialty():
    """A specialty with one active professional and zero slots."""
    factory = get_session_factory()
    suffix = uuid4().hex[:8]
    with factory() as db:
        specialty = Specialty(specialty_id=uuid4(), slug=f"t046-{suffix}", display_name=f"T046 {suffix}", description="D-046 test fixture")
        professional = Professional(professional_id=uuid4(), display_name=f"Dr. T046 {suffix}", active=True)
        db.add_all([specialty, professional])
        db.flush()
        db.add(ProfessionalSpecialty(professional_id=professional.professional_id, specialty_id=specialty.specialty_id, fixed_price_cents=10000, appointment_duration_minutes=45))
        db.commit()
        ids = (specialty.specialty_id, professional.professional_id)
    yield ids
    with factory() as db:
        db.execute(delete(ScheduleSlot).where(ScheduleSlot.professional_id == ids[1]))
        db.execute(delete(ProfessionalSpecialty).where(ProfessionalSpecialty.professional_id == ids[1]))
        db.execute(delete(Professional).where(Professional.professional_id == ids[1]))
        db.execute(delete(Specialty).where(Specialty.specialty_id == ids[0]))
        db.commit()


def _slots_for(db, professional_id) -> list[datetime]:
    return list(db.scalars(select(ScheduleSlot.starts_at).where(ScheduleSlot.professional_id == professional_id).order_by(ScheduleSlot.starts_at)))


class TestRollingHorizon:
    def test_horizon_end_is_never_before_the_end_of_2027(self) -> None:
        assert seeding.horizon_end(date(2026, 11, 27)) == date(2027, 12, 31)
        assert seeding.horizon_end(date(2027, 12, 1)) == date(2028, 1, 30)

    def test_every_missing_business_day_of_the_window_is_reported(self, empty_specialty) -> None:
        specialty_id, _professional_id = empty_specialty
        with get_session_factory()() as db:
            today = datetime.now(SAO_PAULO).date()
            days = [day for day, sid in seeding.missing_horizon_days(db, today) if sid == specialty_id]
            first = _next_business_day(db, today + timedelta(days=1))
        assert days, "a specialty with no slots must be missing every business day"
        assert days[0] == first
        assert days[-1] <= seeding.horizon_end(today)
        assert days[-1] >= date(2027, 12, 1), "the window reaches through 2027"
        holidays_2027 = {date(2027, 1, 25), date(2027, 3, 26), date(2027, 7, 9), date(2027, 12, 25)}
        assert not holidays_2027 & set(days), "non-business holidays are never filled"
        assert all(day.isoweekday() != 7 for day in days), "Sunday is never a business day"
        assert len(days) == len(set(days))

    def test_a_run_fills_the_earliest_days_with_the_standard_grid(self, empty_specialty) -> None:
        _specialty_id, professional_id = empty_specialty
        with get_session_factory()() as db:
            created = seeding.ensure_rolling_availability(db, force=True)
        with get_session_factory()() as db:
            slots = _slots_for(db, professional_id)
            today = datetime.now(SAO_PAULO).date()
            first = _next_business_day(db, today + timedelta(days=1))
        assert created >= len(slots) > 0
        local = [slot.astimezone(SAO_PAULO) for slot in slots]
        days = sorted({slot.date() for slot in local})
        assert days[0] == first
        assert len(days) == seeding.HORIZON_MAX_DAYS_PER_RUN, "bounded catch-up: at most 7 days per run"
        for day in days:
            times = [slot.strftime("%H:%M") for slot in local if slot.date() == day]
            assert times[0] == "08:00"
            assert times[-1] == "17:45"
            assert len(times) == 14
        assert all(slot.date() > today for slot in local), "never a slot for today"

    def test_repeated_runs_catch_up_and_are_idempotent(self, empty_specialty) -> None:
        specialty_id, professional_id = empty_specialty
        factory = get_session_factory()
        for _ in range(80):  # through 2027-12-31: ~340 business days at 7 per run
            with factory() as db:
                if seeding.ensure_rolling_availability(db, force=True) == 0:
                    break
        with factory() as db:
            today = datetime.now(SAO_PAULO).date()
            assert [pair for pair in seeding.missing_horizon_days(db, today) if pair[1] == specialty_id] == []
            count = db.scalar(select(func.count()).select_from(ScheduleSlot).where(ScheduleSlot.professional_id == professional_id))
        with factory() as db:
            assert seeding.ensure_rolling_availability(db, force=True) == 0
        with factory() as db:
            assert db.scalar(select(func.count()).select_from(ScheduleSlot).where(ScheduleSlot.professional_id == professional_id)) == count

    def test_a_fully_booked_day_is_not_refilled(self, empty_specialty) -> None:
        specialty_id, professional_id = empty_specialty
        factory = get_session_factory()
        with factory() as db:
            seeding.ensure_rolling_availability(db, force=True)
        with factory() as db:
            db.execute(ScheduleSlot.__table__.update().where(ScheduleSlot.professional_id == professional_id).values(status="booked"))
            db.commit()
        with factory() as db:
            today = datetime.now(SAO_PAULO).date()
            first = _next_business_day(db, today + timedelta(days=1))
            missing = {day for day, sid in seeding.missing_horizon_days(db, today) if sid == specialty_id}
        assert first not in missing

    def test_debounced_runs_do_nothing(self, empty_specialty, monkeypatch) -> None:
        _specialty_id, professional_id = empty_specialty
        monkeypatch.setattr(seeding, "_horizon_next_check_at", float("inf"))
        with get_session_factory()() as db:
            assert seeding.ensure_rolling_availability(db) == 0
            assert _slots_for(db, professional_id) == []

    def test_conversation_creation_triggers_the_top_up(self, empty_specialty, monkeypatch) -> None:
        """RH-3: a new customer conversation drives the refill — no operator
        needed — and the customer's response is unaffected."""
        _specialty_id, professional_id = empty_specialty
        monkeypatch.setattr(seeding, "_horizon_next_check_at", 0.0)
        response = TestClient(create_app()).post("/api/v1/public/conversations")
        assert response.status_code == 201, response.text
        assert response.json()["access_token"]
        with get_session_factory()() as db:
            assert _slots_for(db, professional_id), "conversation creation must top up the horizon"

    def test_a_failure_never_raises(self, monkeypatch) -> None:
        def boom(*_args, **_kwargs):
            raise RuntimeError("simulated")

        monkeypatch.setattr(seeding, "missing_horizon_days", boom)
        with get_session_factory()() as db:
            assert seeding.ensure_rolling_availability(db, force=True) == 0
