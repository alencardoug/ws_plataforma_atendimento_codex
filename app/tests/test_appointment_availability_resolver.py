"""T031: real-database integration tests for
resolve_appointment_availability() (AA-1/AA-2/AA-4/AA-5/AA-8) plus the
structural no-write proof (acceptance outcome 4).
specs/004-dynamic-appointment-availability/plan.md §4, acceptance.md §B/§C/§F."""

import inspect
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import delete

from customer_care.infrastructure.database import get_session_factory
from customer_care.knowledge.dynamic_binding import DynamicResolutionError
from customer_care.scheduling import availability
from customer_care.scheduling.availability import GENERALIST_SLUG, resolve_appointment_availability
from customer_care.scheduling.models import ScheduleSlot

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
UNIT_ID = "10000000-0000-0000-0000-000000000001"

# specialty slug -> (specialty_id, one of its seeded professional_ids)
SPECIALTY_PROFESSIONALS: dict[str, tuple[str, str]] = {
    "mastologia-oncologica": ("20000000-0000-0000-0000-000000000001", "30000000-0000-0000-0000-000000000001"),
    "cirurgia-colorretal": ("20000000-0000-0000-0000-000000000002", "30000000-0000-0000-0000-000000000004"),
    "segunda-opiniao": ("20000000-0000-0000-0000-000000000003", "30000000-0000-0000-0000-000000000007"),
    GENERALIST_SLUG: ("20000000-0000-0000-0000-000000000004", "30000000-0000-0000-0000-000000000010"),
}


@pytest.fixture
def seeded_slots() -> tuple[date, list[str]]:
    """One morning (09:00) and one afternoon (15:00) slot per seeded
    specialty, on a random far-future date (never D+1/D+7, so this never
    collides with Phase 4's real seed action). Cleaned up unconditionally."""
    base_date = date.today() + timedelta(days=300 + uuid.uuid4().int % 200)
    created_slugs: list[str] = []
    session_factory = get_session_factory()
    with session_factory() as db:
        for slug, (specialty_id, professional_id) in SPECIALTY_PROFESSIONALS.items():
            for hour in (9, 15):
                starts_at = datetime(base_date.year, base_date.month, base_date.day, hour, 0, tzinfo=SAO_PAULO)
                db.add(
                    ScheduleSlot(
                        unit_id=UNIT_ID,
                        specialty_id=specialty_id,
                        professional_id=professional_id,
                        starts_at=starts_at,
                        ends_at=starts_at + timedelta(minutes=60),
                        status="available",
                    )
                )
            created_slugs.append(slug)
        db.commit()
    yield base_date, created_slugs
    with session_factory() as db:
        for specialty_id, professional_id in SPECIALTY_PROFESSIONALS.values():
            db.execute(
                delete(ScheduleSlot).where(
                    ScheduleSlot.specialty_id == specialty_id,
                    ScheduleSlot.professional_id == professional_id,
                    ScheduleSlot.starts_at >= datetime(base_date.year, base_date.month, base_date.day, tzinfo=SAO_PAULO),
                    ScheduleSlot.starts_at < datetime(base_date.year, base_date.month, base_date.day, tzinfo=SAO_PAULO) + timedelta(days=1),
                )
            )
        db.commit()


class TestSpecialtyFiltering:
    def test_each_specialty_keyword_returns_only_that_specialtys_slots(self, seeded_slots: tuple[date, list[str]]) -> None:
        with get_session_factory()() as db:
            resolution, _rows = resolve_appointment_availability(db, "Tem vaga de mastologia?")
        assert "Mastologia" in resolution.pattern_text
        for other_name in ("Cirurgia colorretal", "Segunda opinião", "Oncologia geral"):
            assert other_name not in resolution.pattern_text

    def test_no_specialty_keyword_returns_only_generalist_slots_never_a_mix(self, seeded_slots: tuple[date, list[str]]) -> None:
        with get_session_factory()() as db:
            resolution, _rows = resolve_appointment_availability(db, "Será que tem vaga disponível?")
        assert "Oncologia geral" in resolution.pattern_text
        for other_name in ("Mastologia oncológica", "Cirurgia colorretal oncológica", "Segunda opinião oncológica"):
            assert other_name not in resolution.pattern_text


class TestPeriodFiltering:
    """006/SV correction (found live, 2026-08-20): once the wide-availability
    seed action has actually been exercised against a database (an
    operator action this feature adds — not a per-test fixture), it seeds
    dense same-specialty morning/afternoon slots starting tomorrow, every
    business day through 2026-12-30. `resolve_appointment_availability()`'s
    own `ORDER BY starts_at LIMIT 4` then always prefers those near-term
    real slots over this fixture's own far-future (300+ days out) ones, so
    asserting the *rendered text contains this fixture's own literal
    09:00/15:00* stopped holding — not because period filtering broke, but
    because the fixture's own slots are no longer guaranteed to be among
    the nearest 4. Asserts the actual filtering property instead (every
    *returned* row's local hour is in the requested half of the day),
    which holds regardless of how much other real data exists."""

    def test_morning_keyword_returns_only_morning_slots(self, seeded_slots: tuple[date, list[str]]) -> None:
        with get_session_factory()() as db:
            _resolution, rows = resolve_appointment_availability(db, "Tem vaga de mastologia de manhã?")
        assert rows
        assert all(row[0].starts_at.astimezone(SAO_PAULO).hour < 12 for row in rows)

    def test_afternoon_keyword_returns_only_afternoon_slots(self, seeded_slots: tuple[date, list[str]]) -> None:
        with get_session_factory()() as db:
            _resolution, rows = resolve_appointment_availability(db, "Tem vaga de mastologia à tarde?")
        assert rows
        assert all(row[0].starts_at.astimezone(SAO_PAULO).hour >= 12 for row in rows)


class TestZeroMatchAbstain:
    def test_zero_match_raises_with_diagnostic_never_customer_facing_cause(self) -> None:
        """006/SV correction (found live): the original query ("daqui a
        {random hex} dias") relied on there being no *other* mastologia
        slots anywhere in the system at all — true before this feature's
        own wide-seed action had ever been exercised, false afterward
        (every business day through 2026-12-30 is now seeded for every
        specialty). "domingo" is deterministic (DATE_KEYWORDS, no LLM
        involved) and reliably zero-match regardless of ambient seeded
        data: neither AA-9 nor SV ever seeds a Sunday."""
        with get_session_factory()() as db, pytest.raises(DynamicResolutionError) as exc_info:
            resolve_appointment_availability(db, "Tem vaga de mastologia domingo?")
        assert "no schedule_slots matched params=" in exc_info.value.cause


class TestRenderedTextShape:
    def test_rendered_text_contains_no_raw_table_or_column_name(self, seeded_slots: tuple[date, list[str]]) -> None:
        with get_session_factory()() as db:
            resolution, _rows = resolve_appointment_availability(db, "Tem vaga de mastologia?")
        for forbidden in ("schedule_slots", "specialty_id", "professional_id", "SELECT", "scheduling."):
            assert forbidden not in resolution.pattern_text

    def test_rendered_text_marks_every_price_as_simulation(self, seeded_slots: tuple[date, list[str]]) -> None:
        with get_session_factory()() as db:
            resolution, _rows = resolve_appointment_availability(db, "Tem vaga de mastologia?")
        assert "(simulação)" in resolution.pattern_text
        assert "R$" in resolution.pattern_text


class TestNoWriteStructurally:
    def test_module_source_contains_no_write_construct(self) -> None:
        source = inspect.getsource(availability)
        for forbidden in ("insert(", "update(", "delete(", "pg_insert("):
            assert forbidden not in source, f"found forbidden construct {forbidden!r} in scheduling/availability.py"

    def test_module_never_imports_seeding(self) -> None:
        import_lines = [line for line in inspect.getsource(availability).splitlines() if line.strip().startswith(("import ", "from "))]
        assert not any("seeding" in line for line in import_lines)
