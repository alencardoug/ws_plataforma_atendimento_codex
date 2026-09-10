"""012, tasks.md T15: real-database integration tests for Availability
Continuity (AC). specs/012-appointment-availability-continuity-and-booking-action/
spec.md §5, plan.md §2-3, acceptance.md #1-#5.

AC keeps the simulated generalist agenda populated WITHOUT any
customer/operator query ever creating a slot — bootstrap fill (AC-1) and
a low-water-mark top-up on the operator queue poll (AC-2).

Discipline for this shared dev database: every test here perturbs only
the AA-9 D+1 / D+7 generalist business days and restores exactly those
two days (rows snapshotted, deleted, re-inserted). The full-volume
`ensure_wide_availability()` part of `run_bootstrap_seed()` is stubbed —
its true behaviour is smoke-suite territory (see
`test_appointment_wide_seeding.py`'s own note).
"""

import threading
from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import AuditEvent, SystemSettings
from customer_care.scheduling import seeding
from customer_care.scheduling.availability import resolve_appointment_availability
from customer_care.scheduling.models import ScheduleSlot
from customer_care.scheduling.seeding import (
    AC_FLOOR_MIN,
    AC_FLOOR_TARGET,
    SeedWideResult,
    ensure_generalist_floor,
    next_business_day_sql,
    run_bootstrap_seed,
)

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
GENERALIST_SPECIALTY_ID = UUID("20000000-0000-0000-0000-000000000004")


def _day_bounds(target_date: date) -> tuple[datetime, datetime]:
    start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=SAO_PAULO)
    return start, start + timedelta(days=1)


def _future_generalist_count(db, target_date: date) -> int:
    start, end = _day_bounds(target_date)
    return db.scalar(
        select(func.count())
        .select_from(ScheduleSlot)
        .where(
            ScheduleSlot.status == "available",
            ScheduleSlot.specialty_id == GENERALIST_SPECIALTY_ID,
            ScheduleSlot.starts_at >= start,
            ScheduleSlot.starts_at < end,
            ScheduleSlot.starts_at >= datetime.now(UTC),
        )
    ) or 0


def _target_dates() -> tuple[date, date]:
    with get_session_factory()() as db:
        today = datetime.now(SAO_PAULO).date()
        return (
            next_business_day_sql(db, today + timedelta(days=1)),
            next_business_day_sql(db, today + timedelta(days=7)),
        )


def _snapshot(db, *dates: date) -> list[dict]:
    lo = min(_day_bounds(d)[0] for d in dates)
    hi = max(_day_bounds(d)[1] for d in dates)
    return [
        {"unit_id": s.unit_id, "specialty_id": s.specialty_id, "professional_id": s.professional_id, "starts_at": s.starts_at, "ends_at": s.ends_at, "status": s.status}
        for s in db.scalars(
            select(ScheduleSlot).where(
                ScheduleSlot.specialty_id == GENERALIST_SPECIALTY_ID,
                ScheduleSlot.starts_at >= lo,
                ScheduleSlot.starts_at < hi,
            )
        )
    ]


def _clear_generalist_slots_on(*dates: date) -> None:
    with get_session_factory()() as db:
        for target_date in dates:
            start, end = _day_bounds(target_date)
            db.execute(
                delete(ScheduleSlot).where(
                    ScheduleSlot.specialty_id == GENERALIST_SPECIALTY_ID,
                    ScheduleSlot.starts_at >= start,
                    ScheduleSlot.starts_at < end,
                )
            )
        db.commit()


def _restore(rows: list[dict], *dates: date) -> None:
    _clear_generalist_slots_on(*dates)
    if not rows:
        return
    with get_session_factory()() as db:
        db.execute(pg_insert(ScheduleSlot).values(rows).on_conflict_do_nothing(index_elements=["professional_id", "starts_at"]))
        db.commit()


def _reset_floor_checkpoint() -> None:
    with get_session_factory()() as db:
        db.get(SystemSettings, True).availability_floor_checked_at = None
        db.commit()


def _events_since(event_type: str, since: datetime) -> list[AuditEvent]:
    with get_session_factory()() as db:
        return list(db.scalars(select(AuditEvent).where(AuditEvent.event_type == event_type, AuditEvent.occurred_at >= since).order_by(AuditEvent.occurred_at)))


@pytest.fixture
def agenda_days():
    """Yield (d1, d7); snapshot those two generalist business days and
    restore them exactly afterward, then clear the AC-2 debounce."""
    d1, d7 = _target_dates()
    with get_session_factory()() as db:
        snap = _snapshot(db, d1, d7)
    yield d1, d7
    _restore(snap, d1, d7)
    _reset_floor_checkpoint()


@pytest.fixture
def stub_wide_seed(monkeypatch):
    """Replace the full-volume wide fill with a fast stub — this test file
    only cares about the generalist D+1/D+7 guarantee and the audit event
    shape."""
    monkeypatch.setattr(seeding, "ensure_wide_availability", lambda _session: SeedWideResult(specialty_count=8, business_day_count=0, slots_created=0))


# --------------------------------------------------------------------------- #
# AC-1 bootstrap                                                               #
# --------------------------------------------------------------------------- #


def test_startup_hook_is_a_noop_without_the_env_flag(monkeypatch) -> None:
    from customer_care.scheduling import bootstrap_seed

    called = {"n": 0}
    monkeypatch.setattr(bootstrap_seed, "run_bootstrap_seed", lambda _s: called.__setitem__("n", called["n"] + 1))
    monkeypatch.delenv("RUN_BOOTSTRAP_SEED", raising=False)
    bootstrap_seed.maybe_run_bootstrap_seed_on_startup()
    assert called["n"] == 0
    monkeypatch.setenv("RUN_BOOTSTRAP_SEED", "true")
    assert bootstrap_seed._flag_enabled() is True


def test_bootstrap_guarantees_generalist_minimum_and_is_idempotent(agenda_days, stub_wide_seed) -> None:
    d1, d7 = agenda_days
    _clear_generalist_slots_on(d1, d7)
    since = datetime.now(UTC)

    with get_session_factory()() as db:
        run_bootstrap_seed(db)

    with get_session_factory()() as db:
        assert _future_generalist_count(db, d1) >= 1
        assert _future_generalist_count(db, d7) >= 3
    first = _events_since("scheduling.availability_bootstrap_seeded", since)
    assert len(first) == 1
    assert first[0].payload_json["generalist_d1_created"] >= 1

    since2 = datetime.now(UTC)
    with get_session_factory()() as db:
        run_bootstrap_seed(db)
    ev = _events_since("scheduling.availability_bootstrap_seeded", since2)
    assert len(ev) == 1
    assert ev[0].payload_json["generalist_d1_created"] == 0
    assert ev[0].payload_json["generalist_d7_created"] == 0
    assert ev[0].payload_json["wide_slots_created"] == 0


# --------------------------------------------------------------------------- #
# AC-2 low-water-mark top-up                                                   #
# --------------------------------------------------------------------------- #


def test_floor_tops_up_when_at_or_below_min(agenda_days) -> None:
    d1, _d7 = agenda_days
    _clear_generalist_slots_on(d1)  # 0 future slots -> below AC_FLOOR_MIN
    _reset_floor_checkpoint()
    since = datetime.now(UTC)

    with get_session_factory()() as db:
        ensure_generalist_floor(db)

    with get_session_factory()() as db:
        assert _future_generalist_count(db, d1) == AC_FLOOR_TARGET
        assert db.get(SystemSettings, True).availability_floor_checked_at is not None
    events = _events_since("scheduling.availability_floor_topped_up", since)
    assert len(events) == 1
    assert events[0].payload_json["created"] >= AC_FLOOR_TARGET - AC_FLOOR_MIN


def test_floor_is_a_noop_when_inventory_is_healthy(agenda_days) -> None:
    d1, d7 = agenda_days
    with get_session_factory()() as db:
        seeding.create_slots_on(db, d1, AC_FLOOR_TARGET + 4, GENERALIST_SPECIALTY_ID)
        seeding.create_slots_on(db, d7, AC_FLOOR_TARGET + 4, GENERALIST_SPECIALTY_ID)
        db.commit()
        before_d1 = _future_generalist_count(db, d1)
    _reset_floor_checkpoint()
    since = datetime.now(UTC)

    with get_session_factory()() as db:
        ensure_generalist_floor(db)

    with get_session_factory()() as db:
        assert _future_generalist_count(db, d1) == before_d1
    assert _events_since("scheduling.availability_floor_topped_up", since) == []


def test_floor_check_is_debounced(monkeypatch, agenda_days) -> None:
    _reset_floor_checkpoint()
    calls = {"n": 0}
    real = seeding._count_available_future_on

    def _counting(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(seeding, "_count_available_future_on", _counting)

    with get_session_factory()() as db:
        ensure_generalist_floor(db)
    first = calls["n"]
    assert first >= 1

    with get_session_factory()() as db:
        ensure_generalist_floor(db)  # immediate re-call: time-gated, no count
    assert calls["n"] == first


def test_concurrent_floor_calls_never_exceed_target(agenda_days) -> None:
    d1, _d7 = agenda_days
    _clear_generalist_slots_on(d1)
    _reset_floor_checkpoint()

    def _run() -> None:
        with get_session_factory()() as db:
            ensure_generalist_floor(db)

    threads = [threading.Thread(target=_run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with get_session_factory()() as db:
        assert _future_generalist_count(db, d1) == AC_FLOOR_TARGET


# --------------------------------------------------------------------------- #
# AC-3 the query path itself never self-heals                                  #
# --------------------------------------------------------------------------- #


def test_resolver_stays_read_only_on_success_and_abstain(agenda_days) -> None:
    """specs/004 clarification item 6, re-proven: resolving availability —
    whether it returns offers or abstains — never creates a slot."""
    with get_session_factory()() as db:
        before = db.scalar(select(func.count()).select_from(ScheduleSlot))
        resolution, rows = resolve_appointment_availability(db, "quero agendar uma consulta")
        assert resolution.pattern_text and rows
        assert db.scalar(select(func.count()).select_from(ScheduleSlot)) == before

    with get_session_factory()() as db:
        before = db.scalar(select(func.count()).select_from(ScheduleSlot))
        # "domingo" -> next Sunday, a day the simulated agenda never opens
        # (QA-020) -> DynamicResolutionError, non-destructively.
        with pytest.raises(Exception):
            resolve_appointment_availability(db, "tem consulta no domingo?")
        assert db.scalar(select(func.count()).select_from(ScheduleSlot)) == before
