"""005/PL, tasks.md T023: real-database integration tests for
resolve_price_lookup() — deterministic, read-only, single-specialty price
lookup reusing feature 004's professional_specialties data. Mirrors
tests/test_appointment_availability_resolver.py's real-DB pattern.
specs/005-dynamic-pricing-and-guided-booking/plan.md §4."""

import uuid

import pytest

from customer_care.infrastructure.database import get_session_factory
from customer_care.knowledge.dynamic_binding import DynamicResolutionError
from customer_care.scheduling.availability import GENERALIST_SLUG, format_price_brl, resolve_price_lookup


class TestPriceLookupPerSpecialty:
    @pytest.mark.parametrize(
        "query_text,expected_display_name_fragment",
        [
            ("Quanto custa uma consulta de mastologia?", "Mastologia"),
            ("Quanto custa uma consulta colorretal?", "colorretal"),
            ("Quanto custa uma segunda opinião?", "Segunda"),
        ],
    )
    def test_specific_specialty_resolves_with_a_real_price(self, query_text: str, expected_display_name_fragment: str) -> None:
        with get_session_factory()() as db:
            resolution = resolve_price_lookup(db, query_text)
        assert expected_display_name_fragment in resolution.pattern_text
        assert "(simulação)" in resolution.pattern_text
        assert "R$" in resolution.pattern_text
        assert "minutos" in resolution.pattern_text

    def test_no_specialty_named_prices_the_generalist_default(self) -> None:
        with get_session_factory()() as db:
            resolution = resolve_price_lookup(db, "Quanto custa uma consulta?")
        assert resolution.specialty_slug == GENERALIST_SLUG


class TestPriceLookupNeverFabricates:
    def test_price_matches_the_real_professional_specialties_row(self) -> None:
        from sqlalchemy import select

        from customer_care.scheduling.models import ProfessionalSpecialty, Specialty

        with get_session_factory()() as db:
            resolution = resolve_price_lookup(db, "Quanto custa uma consulta de mastologia?")
            row = db.execute(
                select(ProfessionalSpecialty.fixed_price_cents)
                .join(Specialty, Specialty.specialty_id == ProfessionalSpecialty.specialty_id)
                .where(Specialty.slug == "mastologia-oncologica")
                .limit(1)
            ).scalar_one()
        assert format_price_brl(row) in resolution.pattern_text


class TestPriceLookupFallback:
    def test_unmatchable_specialty_slug_would_raise_but_all_seeded_specialties_are_priced(self) -> None:
        """Every seeded specialty (including the AA-3a generalist default)
        has a professional_specialties row in this corpus, so
        DynamicResolutionError's fallback path is exercised only under a
        monkeypatched empty result — proven structurally here instead,
        matching AA-8's existing precedent of trusting the safe fallback
        code path rather than requiring a database state that shouldn't
        exist against seeded data."""
        with get_session_factory()() as db, pytest.raises(DynamicResolutionError):
            from unittest.mock import patch

            with patch("customer_care.scheduling.availability.extract_parameters") as mocked:
                from customer_care.scheduling.availability import ExtractedParameters

                mocked.return_value = ExtractedParameters(specialty_slug=f"nonexistent-{uuid.uuid4().hex}", target_date=None, period_hours=None)
                resolve_price_lookup(db, "irrelevant")
