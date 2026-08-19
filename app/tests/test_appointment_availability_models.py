"""T011: proves scheduling/models.py's ORM mappings are correct against the
real database created by the two Phase 1 migrations (T008's schema
creation, T009's generalist specialty) before anything else is built on
top of them. Real-database integration test, matching this package's
established convention for DB-touching acceptance evidence
(specs/004-dynamic-appointment-availability/tasks.md Phase 1 gate)."""

from sqlalchemy import select

from customer_care.infrastructure.database import get_session_factory
from customer_care.scheduling.models import Professional, ProfessionalSpecialty, ScheduleSlot, Specialty, Unit

EXPECTED_SLUGS = {"mastologia-oncologica", "cirurgia-colorretal", "segunda-opiniao", "oncologia-geral"}


def test_all_four_specialties_round_trip() -> None:
    with get_session_factory()() as db:
        specialties = db.scalars(select(Specialty)).all()

    assert {s.slug for s in specialties} == EXPECTED_SLUGS
    assert len(specialties) == 4


def test_all_twelve_professionals_round_trip_and_join_through_professional_specialties() -> None:
    with get_session_factory()() as db:
        professionals = db.scalars(select(Professional)).all()
        links = db.scalars(select(ProfessionalSpecialty)).all()

        assert len(professionals) == 12
        assert len(links) == 12
        for link in links:
            assert db.get(Professional, link.professional_id) is not None
            assert db.get(Specialty, link.specialty_id) is not None


def test_generalist_specialty_priced_cheaper_and_shorter_than_diagnosis_specific_ones() -> None:
    with get_session_factory()() as db:
        generalist = db.scalar(select(Specialty).where(Specialty.slug == "oncologia-geral"))
        assert generalist is not None
        link = db.scalar(select(ProfessionalSpecialty).where(ProfessionalSpecialty.specialty_id == generalist.specialty_id))

    assert link is not None
    assert link.fixed_price_cents == 60000
    assert link.appointment_duration_minutes == 45
    # Diagnosis-specific specialties are 60-90min / R$980-1450 (data-model.md §6) —
    # the generalist triage consultation must stay cheaper and shorter than every one of them.
    assert link.fixed_price_cents < 98000
    assert link.appointment_duration_minutes < 60


def test_unit_round_trips() -> None:
    with get_session_factory()() as db:
        unit = db.scalar(select(Unit))

    assert unit is not None
    assert unit.timezone == "America/Sao_Paulo"


def test_schedule_slots_are_queryable_and_fk_joins_resolve() -> None:
    with get_session_factory()() as db:
        slots = db.scalars(select(ScheduleSlot)).all()
        for slot in slots:
            assert db.get(Unit, slot.unit_id) is not None
            assert db.get(Specialty, slot.specialty_id) is not None
            assert db.get(Professional, slot.professional_id) is not None
