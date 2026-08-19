"""T021: extract_parameters() is pure/deterministic — every case here runs
with no database. Covers every diagnosis-specific keyword, explicit
generalist keywords, the no-match-defaults-to-generalist case (AA-3a),
mixed case, realistic full customer sentences, and date/period extraction.
specs/004-dynamic-appointment-availability/plan.md §5."""

from datetime import date

from customer_care.scheduling.availability import GENERALIST_SLUG, extract_parameters

REFERENCE = date(2026, 8, 19)  # a Wednesday


def test_each_diagnosis_specific_keyword_resolves_its_own_specialty() -> None:
    assert extract_parameters("Tem vaga de mastologia?").specialty_slug == "mastologia-oncologica"
    assert extract_parameters("preciso de consulta sobre a mama").specialty_slug == "mastologia-oncologica"
    assert extract_parameters("dor no peito, é isso mesmo?").specialty_slug == "mastologia-oncologica"
    assert extract_parameters("suspeita colorretal").specialty_slug == "cirurgia-colorretal"
    assert extract_parameters("problema no intestino").specialty_slug == "cirurgia-colorretal"
    assert extract_parameters("exame de cólon").specialty_slug == "cirurgia-colorretal"
    assert extract_parameters("quero uma segunda opinião").specialty_slug == "segunda-opiniao"
    assert extract_parameters("quero uma segunda opiniao").specialty_slug == "segunda-opiniao"


def test_explicit_generalist_keywords_resolve_generalist_slug() -> None:
    assert extract_parameters("quero um clínico geral").specialty_slug == GENERALIST_SLUG
    assert extract_parameters("não sei qual especialidade preciso").specialty_slug == GENERALIST_SLUG
    assert extract_parameters("é uma triagem inicial").specialty_slug == GENERALIST_SLUG


def test_query_with_no_known_specialty_keyword_defaults_to_generalist() -> None:
    result = extract_parameters("Tem vaga amanhã de manhã?")
    assert result.specialty_slug == GENERALIST_SLUG


def test_matching_is_case_insensitive() -> None:
    assert extract_parameters("MASTOLOGIA amanhã").specialty_slug == "mastologia-oncologica"
    assert extract_parameters("Segunda Opinião").specialty_slug == "segunda-opiniao"


def test_realistic_full_sentences_per_specialty() -> None:
    assert extract_parameters("Tem vaga de mastologia amanhã de manhã?").specialty_slug == "mastologia-oncologica"
    assert extract_parameters("Quero marcar uma consulta colorretal para a semana que vem.").specialty_slug == "cirurgia-colorretal"
    assert extract_parameters("Gostaria de agendar uma segunda opinião oncológica.").specialty_slug == "segunda-opiniao"
    assert extract_parameters("Não sei com qual médico devo falar sobre isso.").specialty_slug == GENERALIST_SLUG


def test_no_date_keyword_leaves_target_date_none() -> None:
    result = extract_parameters("Tem vaga de mastologia?", reference_date=REFERENCE)
    assert result.target_date is None


def test_amanha_resolves_to_reference_plus_one_day() -> None:
    result = extract_parameters("tem vaga amanhã?", reference_date=REFERENCE)
    assert result.target_date == date(2026, 8, 20)

    result_no_accent = extract_parameters("tem vaga amanha?", reference_date=REFERENCE)
    assert result_no_accent.target_date == date(2026, 8, 20)


def test_semana_que_vem_resolves_to_reference_plus_seven_days() -> None:
    result = extract_parameters("tem vaga semana que vem?", reference_date=REFERENCE)
    assert result.target_date == date(2026, 8, 26)

    result_alt = extract_parameters("tem vaga na próxima semana?", reference_date=REFERENCE)
    assert result_alt.target_date == date(2026, 8, 26)


def test_weekday_keyword_resolves_to_next_occurrence_not_today() -> None:
    # REFERENCE is a Wednesday (2026-08-19); next Saturday is 2026-08-22, next Sunday 2026-08-23.
    assert extract_parameters("tem vaga sábado?", reference_date=REFERENCE).target_date == date(2026, 8, 22)
    assert extract_parameters("tem vaga sabado?", reference_date=REFERENCE).target_date == date(2026, 8, 22)
    assert extract_parameters("tem vaga domingo?", reference_date=REFERENCE).target_date == date(2026, 8, 23)


def test_weekday_keyword_on_the_day_itself_means_next_week_not_today() -> None:
    a_saturday = date(2026, 8, 22)
    result = extract_parameters("tem vaga sábado?", reference_date=a_saturday)
    assert result.target_date == date(2026, 8, 29)


def test_period_keywords_map_to_expected_hour_ranges() -> None:
    assert extract_parameters("tem vaga de manhã?").period_hours == (0, 12)
    assert extract_parameters("tem vaga de manha?").period_hours == (0, 12)
    assert extract_parameters("tem vaga à tarde?").period_hours == (12, 24)


def test_no_period_keyword_leaves_period_hours_none() -> None:
    assert extract_parameters("tem vaga de mastologia?").period_hours is None


def test_amanha_does_not_false_positive_match_the_manha_period_keyword() -> None:
    """Regression: found live during Phase 5 verification — "amanhã" ends
    with the literal characters "manhã", so a naive substring check
    incorrectly set period_hours=(0, 12) for any message containing
    "amanhã", silently narrowing results to morning-only slots."""
    result = extract_parameters("Existe consulta disponível amanhã?", reference_date=REFERENCE)
    assert result.target_date == date(2026, 8, 20)
    assert result.period_hours is None

    result_no_accent = extract_parameters("Existe consulta disponivel amanha?", reference_date=REFERENCE)
    assert result_no_accent.period_hours is None
