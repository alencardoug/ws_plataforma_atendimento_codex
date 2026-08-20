"""006/ND: extract_parameters()'s LLM date-intent fallback. Pure,
no-database tests — `_resolve_date_intent()`'s five deterministic
arithmetic rules run with no provider at all; the opt-in gating tests use
a fake provider (matching `test_automatic_draft_status.py`'s established
fake-session/monkeypatch style), never a real LLM call.
specs/006-specialty-scheduling-breadth/plan.md §5, data-model.md §5."""

from datetime import date

import pytest

from customer_care.ai.providers import StructuredDateIntent
from customer_care.scheduling import availability
from customer_care.scheduling.availability import (
    GENERALIST_SLUG,
    _looks_like_a_date_expression,
    _resolve_date_intent,
    extract_parameters,
)

REFERENCE = date(2026, 8, 19)  # a Wednesday


def _intent(**overrides: object) -> StructuredDateIntent:
    base = {"relative_unit": None, "relative_count": None, "weekday": None, "nth_weekday_of_month": None, "month": None, "day": None, "time_range_start": None, "time_range_end": None}
    base.update(overrides)
    return StructuredDateIntent(**base)  # type: ignore[arg-type]


class TestResolveDateIntentRelative:
    def test_relative_days(self) -> None:
        target, _period = _resolve_date_intent(_intent(relative_unit="day", relative_count=3), REFERENCE)
        assert target == date(2026, 8, 22)

    def test_relative_weeks(self) -> None:
        target, _period = _resolve_date_intent(_intent(relative_unit="week", relative_count=2), REFERENCE)
        assert target == date(2026, 9, 2)

    def test_relative_months_clamps_day_of_month(self) -> None:
        # 2026-01-31 + 1 month -> Feb has 28 days in 2026 (not a leap year).
        target, _period = _resolve_date_intent(_intent(relative_unit="month", relative_count=1), date(2026, 1, 31))
        assert target == date(2026, 2, 28)


class TestResolveDateIntentWeekday:
    def test_weekday_alone_next_occurrence(self) -> None:
        # REFERENCE is a Wednesday (weekday=2); next Tuesday (weekday=1) is 2026-08-25.
        target, _period = _resolve_date_intent(_intent(weekday=1), REFERENCE)
        assert target == date(2026, 8, 25)

    def test_weekday_with_relative_count_two_means_second_occurrence(self) -> None:
        # "daqui a 2 terças-feira" — the second Tuesday from now, not the first.
        target, _period = _resolve_date_intent(_intent(weekday=1, relative_count=2), REFERENCE)
        assert target == date(2026, 9, 1)


class TestResolveDateIntentNthWeekdayOfMonth:
    def test_third_thursday_of_october(self) -> None:
        target, _period = _resolve_date_intent(_intent(nth_weekday_of_month=3, weekday=3, month=10), REFERENCE)
        assert target == date(2026, 10, 15)

    def test_defaults_to_reference_months_own_month_when_month_omitted(self) -> None:
        # REFERENCE is 2026-08-19; the 4th Wednesday of August 2026 is 2026-08-26.
        target, _period = _resolve_date_intent(_intent(nth_weekday_of_month=4, weekday=2), REFERENCE)
        assert target == date(2026, 8, 26)

    def test_already_past_this_month_rolls_forward_one_month_not_one_year(self) -> None:
        # The 1st Monday of August 2026 is 2026-08-03, already before REFERENCE
        # (2026-08-19) -> rolls to the 1st Monday of September, not August 2027.
        target, _period = _resolve_date_intent(_intent(nth_weekday_of_month=1, weekday=0, month=8), REFERENCE)
        assert target == date(2026, 9, 7)

    def test_out_of_range_occurrence_never_invents_a_past_or_wrong_date(self) -> None:
        # Neither August nor September 2026 has a 5th Thursday (weekday=3) —
        # confirmed by direct calendar computation, not assumed — so both
        # the initial attempt and the one-month roll-forward fail, expecting
        # a safe None rather than a fabricated date.
        target, _period = _resolve_date_intent(_intent(nth_weekday_of_month=5, weekday=3, month=8), REFERENCE)
        assert target is None


class TestResolveDateIntentExplicitDate:
    def test_future_date_this_year(self) -> None:
        target, _period = _resolve_date_intent(_intent(day=23, month=11), REFERENCE)
        assert target == date(2026, 11, 23)

    def test_already_passed_this_year_rolls_to_next_year(self) -> None:
        target, _period = _resolve_date_intent(_intent(day=1, month=1), REFERENCE)
        assert target == date(2027, 1, 1)

    def test_invalid_day_for_month_returns_none_never_fabricates(self) -> None:
        target, _period = _resolve_date_intent(_intent(day=31, month=4), REFERENCE)  # April has 30 days
        assert target is None


class TestResolveDateIntentTimeRange:
    def test_time_range_independent_of_date_resolution(self) -> None:
        target, period = _resolve_date_intent(_intent(time_range_start=10, time_range_end=14), REFERENCE)
        assert target is None
        assert period == (10, 14)


class TestLooksLikeADateExpression:
    def test_digit_date_pattern_detected(self) -> None:
        assert _looks_like_a_date_expression("tem vaga 23/11/2026?")

    def test_month_name_detected(self) -> None:
        assert _looks_like_a_date_expression("tem vaga em outubro?")

    def test_weekday_name_detected(self) -> None:
        assert _looks_like_a_date_expression("tem vaga na terça-feira?")

    def test_relative_word_detected(self) -> None:
        assert _looks_like_a_date_expression("tem vaga daqui a um mês?")

    def test_plain_specialty_question_not_detected(self) -> None:
        assert not _looks_like_a_date_expression("tem vaga de mastologia?")


class _FakeProvider:
    def __init__(self, intent: StructuredDateIntent | None) -> None:
        self._intent = intent
        self.calls: list[tuple[str, date]] = []

    def extract_date_intent(self, customer_text: str, reference_date: date) -> StructuredDateIntent | None:
        self.calls.append((customer_text, reference_date))
        return self._intent


class TestExtractParametersOptInGating:
    def test_default_never_calls_the_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _FakeProvider(_intent(relative_unit="day", relative_count=1))
        monkeypatch.setattr(availability, "configured_generation_provider", lambda: fake)
        result = extract_parameters("tem vaga daqui a um dia?", reference_date=REFERENCE)
        assert result.target_date is None
        assert fake.calls == []

    def test_opted_in_with_date_like_language_and_no_keyword_match_calls_the_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _FakeProvider(_intent(relative_unit="day", relative_count=3))
        monkeypatch.setattr(availability, "configured_generation_provider", lambda: fake)
        result = extract_parameters("tem vaga daqui a 3 dias?", reference_date=REFERENCE, allow_llm_date_fallback=True)
        assert result.target_date == date(2026, 8, 22)
        assert len(fake.calls) == 1

    def test_opted_in_but_a_keyword_already_matched_never_calls_the_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _FakeProvider(_intent(relative_unit="day", relative_count=99))
        monkeypatch.setattr(availability, "configured_generation_provider", lambda: fake)
        result = extract_parameters("tem vaga amanhã?", reference_date=REFERENCE, allow_llm_date_fallback=True)
        assert result.target_date == date(2026, 8, 20)  # DATE_KEYWORDS's own "amanhã" result, not the fake's
        assert fake.calls == []

    def test_opted_in_but_no_date_like_language_never_calls_the_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _FakeProvider(_intent(relative_unit="day", relative_count=1))
        monkeypatch.setattr(availability, "configured_generation_provider", lambda: fake)
        result = extract_parameters("tem vaga de mastologia?", reference_date=REFERENCE, allow_llm_date_fallback=True)
        assert result.specialty_slug == "mastologia-oncologica"
        assert result.target_date is None
        assert fake.calls == []

    def test_provider_returning_none_falls_through_to_no_target_date(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = _FakeProvider(None)
        monkeypatch.setattr(availability, "configured_generation_provider", lambda: fake)
        result = extract_parameters("tem vaga daqui a um mês?", reference_date=REFERENCE, allow_llm_date_fallback=True)
        assert result.target_date is None
        assert result.specialty_slug == GENERALIST_SLUG
