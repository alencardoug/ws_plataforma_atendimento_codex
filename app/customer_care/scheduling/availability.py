"""Deterministic parameter extraction (AA-3/AA-3a) plus, from Phase 3
onward, the purely read-only query resolver (AA-1/AA-2/AA-4/AA-5/AA-8).
See specs/004-dynamic-appointment-availability/plan.md §5 (this phase) and
§4 (Phase 3)."""

import calendar
import hashlib
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Row, and_, extract, select
from sqlalchemy.orm import Session

from customer_care.ai.prompts import load_prompt
from customer_care.ai.providers import StructuredDateIntent, configured_generation_provider
from customer_care.audit.service import record_event
from customer_care.infrastructure.models import Conversation
from customer_care.knowledge.dynamic_binding import DynamicResolution, DynamicResolutionError
from customer_care.scheduling.models import AppointmentBooking, Professional, ProfessionalSpecialty, ScheduleSlot, Specialty, Unit

SAO_PAULO = ZoneInfo("America/Sao_Paulo")

GENERALIST_SLUG = "oncologia-geral"

SPECIALTY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "mastologia-oncologica": ("mastologia", "mama", "peito"),
    "cirurgia-colorretal": ("colorretal", "intestino", "cólon", "colon", "reto"),
    "segunda-opiniao": ("segunda opinião", "segunda opiniao"),
    # 006/SS-2: four new support specialties. Word-boundary-safe
    # (`_contains_keyword`) and checked for non-collision against every
    # existing keyword set above.
    "psico-oncologia": ("psico-oncologia", "psico oncologia", "apoio psicológico", "apoio psicologico", "psicólogo", "psicologo", "psicóloga", "psicologa"),
    "nutricao-oncologica": ("nutrição oncológica", "nutricao oncologica", "nutricionista", "orientação nutricional", "orientacao nutricional"),
    "endocrinologia-oncologica": ("endocrinologia", "endocrinologista", "hormonal", "hormonais", "hormônio", "hormonio", "hormônios", "hormonios", "tireoide", "tireóide"),
    "fisioterapia-oncologica": ("fisioterapia", "fisioterapeuta", "linfedema", "reabilitação física", "reabilitacao fisica"),
    GENERALIST_SLUG: ("generalista", "clínico geral", "clinico geral", "não sei qual", "nao sei qual", "triagem", "suspeita"),
}


def _next_weekday(reference: date, target_weekday: int) -> date:
    """First occurrence of `target_weekday` (Monday=0..Sunday=6) strictly
    after `reference` — "sábado" said today never means today itself."""
    days_ahead = (target_weekday - reference.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return reference + timedelta(days=days_ahead)


DATE_KEYWORDS: dict[str, Callable[[date], date]] = {
    "amanhã": lambda ref: ref + timedelta(days=1),
    "amanha": lambda ref: ref + timedelta(days=1),
    "semana que vem": lambda ref: ref + timedelta(days=7),
    "próxima semana": lambda ref: ref + timedelta(days=7),
    "proxima semana": lambda ref: ref + timedelta(days=7),
    "sábado": lambda ref: _next_weekday(ref, 5),
    "sabado": lambda ref: _next_weekday(ref, 5),
    "domingo": lambda ref: _next_weekday(ref, 6),
}

PERIOD_KEYWORDS: dict[str, tuple[int, int]] = {
    "manhã": (0, 12),
    "manha": (0, 12),
    "tarde": (12, 24),
}


@dataclass(frozen=True)
class ExtractedParameters:
    specialty_slug: str
    target_date: date | None
    period_hours: tuple[int, int] | None


def _today() -> date:
    return datetime.now(SAO_PAULO).date()


def _contains_keyword(text: str, keyword: str) -> bool:
    """Word-boundary match, not naive substring — "manhã" must not match
    inside "amanhã" (a real false-positive found via live verification:
    "amanhã" ends with the literal characters "manhã"). `\\w`/`\\b` are
    Unicode-aware by default for `str` patterns, so accented characters
    count as word characters and the boundary lands correctly."""
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def extract_parameters(query_text: str, reference_date: date | None = None, *, allow_llm_date_fallback: bool = False, session: Session | None = None) -> ExtractedParameters:
    """Deterministic keyword matching first, always — zero regression risk,
    matching every existing call/test's current behavior exactly.
    `specialty_slug` always resolves to a real seeded specialty — defaults
    to `GENERALIST_SLUG` when no diagnosis-specific keyword matches, never
    unfiltered (`spec.md` AA-3a). `target_date`/`period_hours` stay
    optional — an unmatched one is simply not filtered on downstream.

    006/ND-2: when `allow_llm_date_fallback=True` (only
    `resolve_appointment_availability()` passes this — `resolve_price_lookup()`
    discards `target_date`/`period_hours` entirely, so calling the LLM
    there would be pure waste) and no `DATE_KEYWORDS` matched but the
    message still looks like it names a date/time, one real LLM call
    (`GenerationProvider.extract_date_intent`) attempts a richer
    extraction, resolved by pure deterministic arithmetic
    (`_resolve_date_intent`) — never fabricates a date; any failure falls
    through to the existing insufficient-match behavior identically to
    today (ND-3). Default `False` keeps this function's behavior for
    every other/existing caller unchanged — no provider is even looked up
    unless explicitly opted in. `session`, when given alongside
    `allow_llm_date_fallback=True`, is used only to record the
    `ai.date_intent_extracted` audit event (ND-4) — omitted, that event is
    simply skipped (e.g. a unit test exercising the fallback with a fake
    provider and no live session)."""
    text = query_text.lower()
    today = reference_date if reference_date is not None else _today()

    specialty_slug = GENERALIST_SLUG
    for slug, keywords in SPECIALTY_KEYWORDS.items():
        if slug != GENERALIST_SLUG and any(_contains_keyword(text, kw) for kw in keywords):
            specialty_slug = slug
            break

    target_date: date | None = None
    for keyword, resolve in DATE_KEYWORDS.items():
        if _contains_keyword(text, keyword):
            target_date = resolve(today)
            break

    period_hours: tuple[int, int] | None = None
    for keyword, hours in PERIOD_KEYWORDS.items():
        if _contains_keyword(text, keyword):
            period_hours = hours
            break

    if target_date is None and allow_llm_date_fallback and _looks_like_a_date_expression(text):
        llm_date, llm_period = _resolve_via_llm(query_text, today, session)
        target_date = llm_date
        period_hours = llm_period if llm_period is not None else period_hours

    return ExtractedParameters(specialty_slug=specialty_slug, target_date=target_date, period_hours=period_hours)


# 006/ND-2: the cheap pre-filter — presence of a weekday name, month name,
# digit sequence resembling a date, or a relative-time word not already
# caught by DATE_KEYWORDS. A false positive only costs one extra LLM call
# that most likely returns an all-None intent (harmless, identical
# fallthrough to today); a false negative just means ND doesn't help for a
# phrasing outside this list.
_MONTH_NAMES_PT = ("janeiro", "fevereiro", "março", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")
_WEEKDAY_NAMES_PT = ("segunda-feira", "segunda feira", "terça-feira", "terca-feira", "terça feira", "terca feira", "quarta-feira", "quarta feira", "quinta-feira", "quinta feira", "sexta-feira", "sexta feira", "sábado", "sabado", "domingo")
_RELATIVE_WORDS_PT = ("daqui", "próxim", "proxim", "semana", "mês", "mes", "ano que vem")
_DATE_DIGIT_PATTERN = re.compile(r"\b\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?\b")


def _looks_like_a_date_expression(text: str) -> bool:
    if _DATE_DIGIT_PATTERN.search(text):
        return True
    if any(_contains_keyword(text, name) for name in _MONTH_NAMES_PT):
        return True
    if any(_contains_keyword(text, name) for name in _WEEKDAY_NAMES_PT):
        return True
    return any(word in text for word in _RELATIVE_WORDS_PT)


def _resolve_via_llm(query_text: str, today: date, session: Session | None) -> tuple[date | None, tuple[int, int] | None]:
    """006/ND-4: emits `ai.date_intent_extracted` (never the raw
    `query_text` — a hash only, Constitution Article VI) when a session
    is available. `intent_resolved` distinguishes "the model returned a
    usable date" from "returned nothing usable" — both fall through to
    the same safe path today, but stay distinguishable for a future
    measurement need."""
    provider = configured_generation_provider()
    intent = provider.extract_date_intent(query_text, today)
    if intent is None:
        resolved_date, resolved_period = None, None
    else:
        resolved_date, resolved_period = _resolve_date_intent(intent, today)
    if session is not None:
        prompt_version = load_prompt("date_intent.md").version
        digest = hashlib.sha256(query_text.strip().encode()).hexdigest()[:16]
        record_event(session, "ai.date_intent_extracted", "SYSTEM", payload={"query_text_hash": digest, "prompt_version": prompt_version, "intent_resolved": resolved_date is not None})
    return resolved_date, resolved_period


def _add_months(base: date, months: int) -> date:
    """Calendar-month addition — `date` has no native support. Clamps the
    day-of-month to the target month's last valid day (e.g. Jan 31 + 1
    month -> Feb 28/29, never an invalid Feb 31)."""
    total_month_index = base.month - 1 + months
    year = base.year + total_month_index // 12
    month = total_month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(base.day, last_day))


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date | None:
    """The Nth occurrence of `weekday` (0=Monday..6=Sunday) within
    (year, month), or `None` if it doesn't exist (e.g. a 5th Friday that
    isn't in that month) — never wraps into an adjacent month itself."""
    first_weekday = date(year, month, 1).weekday()
    offset = (weekday - first_weekday) % 7
    day = 1 + offset + (n - 1) * 7
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, day) if day <= last_day else None


def _resolve_date_intent(intent: StructuredDateIntent, today: date) -> tuple[date | None, tuple[int, int] | None]:
    """006/ND-2: the five deterministic arithmetic rules, tried in order
    of specificity. Never invents a past date — any rule that can't
    produce a valid, non-past date returns `None` for `target_date`,
    falling through to the existing insufficient-match behavior (ND-3)."""
    period_hours: tuple[int, int] | None = None
    if intent.time_range_start is not None and intent.time_range_end is not None:
        period_hours = (intent.time_range_start, intent.time_range_end)

    target_date: date | None = None
    if intent.relative_unit is not None and intent.relative_count is not None:
        if intent.relative_unit == "day":
            target_date = today + timedelta(days=intent.relative_count)
        elif intent.relative_unit == "week":
            target_date = today + timedelta(days=intent.relative_count * 7)
        elif intent.relative_unit == "month":
            target_date = _add_months(today, intent.relative_count)
    elif intent.nth_weekday_of_month is not None and intent.weekday is not None:
        month = intent.month if intent.month is not None else today.month
        year = today.year
        candidate = _nth_weekday_of_month(year, month, intent.weekday, intent.nth_weekday_of_month)
        if candidate is None or candidate <= today:
            next_month, next_year = (month + 1, year) if month < 12 else (1, year + 1)
            candidate = _nth_weekday_of_month(next_year, next_month, intent.weekday, intent.nth_weekday_of_month)
        target_date = candidate if candidate is not None and candidate > today else None
    elif intent.weekday is not None:
        count = intent.relative_count if intent.relative_count and intent.relative_count > 0 else 1
        candidate = today
        for _ in range(count):
            candidate = _next_weekday(candidate, intent.weekday)
        target_date = candidate
    elif intent.day is not None and intent.month is not None:
        candidate = None
        try:
            candidate = date(today.year, intent.month, intent.day)
        except ValueError:
            candidate = None
        if candidate is not None and candidate <= today:
            try:
                candidate = date(today.year + 1, intent.month, intent.day)
            except ValueError:
                candidate = None
        target_date = candidate

    return target_date, period_hours


_WEEKDAY_PT = {
    0: "segunda-feira",
    1: "terça-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sábado",
    6: "domingo",
}


def _now_sao_paulo() -> datetime:
    return datetime.now(SAO_PAULO)


def format_price_brl(cents: int) -> str:
    reais, centavos = divmod(cents, 100)
    reais_str = f"{reais:,}".replace(",", ".")
    return f"R$ {reais_str},{centavos:02d}"


_SlotRow = Row[tuple[ScheduleSlot, Specialty, Professional, ProfessionalSpecialty, Unit]]


def _render_offers(rows: Sequence[_SlotRow]) -> str:
    blocks = []
    for slot, specialty, professional, professional_specialty, unit in rows:
        local_start = slot.starts_at.astimezone(SAO_PAULO)
        weekday = _WEEKDAY_PT[local_start.weekday()]
        blocks.append(
            f"{specialty.display_name} — {professional.display_name}, {unit.name}\n"
            f"{weekday} {local_start:%d/%m} às {local_start:%H:%M} (America/São_Paulo) — "
            f"{format_price_brl(professional_specialty.fixed_price_cents)} (simulação)"
        )
    return "\n\n".join(blocks)


def resolve_appointment_availability(session: Session, query_text: str) -> tuple[DynamicResolution, Sequence[_SlotRow]]:
    """Reads only. Never writes. If `schedule_slots` has nothing to offer,
    raises `DynamicResolutionError` — it does not generate data itself
    (that is exclusively `scheduling/seeding.py`'s job, AA-9, triggered
    only by an explicit operator action, never as a side effect of a
    query). `plan.md` §4.

    Returns the offered rows alongside the rendered `DynamicResolution`
    (005/GB-1, `data-model.md` §4) so the caller can persist exactly what
    was shown to the customer — this function does not persist anything
    itself, staying purely read-only as AA-2 requires. 006/ND: the only
    caller that opts into the LLM date-intent fallback — `resolve_price_lookup()`
    below discards `target_date`/`period_hours` entirely, so it does not."""
    params = extract_parameters(query_text, allow_llm_date_fallback=True, session=session)
    query = (
        select(ScheduleSlot, Specialty, Professional, ProfessionalSpecialty, Unit)
        .join(Specialty, ScheduleSlot.specialty_id == Specialty.specialty_id)
        .join(Professional, ScheduleSlot.professional_id == Professional.professional_id)
        .join(
            ProfessionalSpecialty,
            and_(
                ProfessionalSpecialty.professional_id == ScheduleSlot.professional_id,
                ProfessionalSpecialty.specialty_id == ScheduleSlot.specialty_id,
            ),
        )
        .join(Unit, ScheduleSlot.unit_id == Unit.unit_id)
        .where(ScheduleSlot.status == "available", ScheduleSlot.starts_at >= _now_sao_paulo())
        .where(Specialty.slug == params.specialty_slug)  # always present — defaults to GENERALIST_SLUG, never unfiltered
    )
    if params.target_date is not None:
        day_start = datetime.combine(params.target_date, datetime.min.time(), tzinfo=SAO_PAULO)
        query = query.where(ScheduleSlot.starts_at >= day_start, ScheduleSlot.starts_at < day_start + timedelta(days=1))
    if params.period_hours is not None:
        start_hour, end_hour = params.period_hours
        query = query.where(extract("hour", ScheduleSlot.starts_at).between(start_hour, end_hour - 1))
    rows = session.execute(query.order_by(ScheduleSlot.starts_at).limit(4)).all()
    if not rows:
        raise DynamicResolutionError(cause=f"no schedule_slots matched params={params}")
    return DynamicResolution(_render_offers(rows), specialty_slug=params.specialty_slug, slot_count=len(rows)), rows


def resolve_price_lookup(session: Session, query_text: str) -> DynamicResolution:
    """005/PL: deterministic, read-only, single-specialty price lookup —
    reuses AA-3's specialty extraction (date/period are irrelevant here and
    ignored) and the same `professional_specialties.fixed_price_cents`
    source AA-10's own price line already reads
    (`booking_script/service.py::lookup_recent_specialty_price`). Never
    writes, never LLM-composed — matches AA-2/AA-5's precedent. `plan.md`
    §4."""
    params = extract_parameters(query_text)
    row = session.execute(
        select(Specialty.display_name, ProfessionalSpecialty.fixed_price_cents, ProfessionalSpecialty.appointment_duration_minutes)
        .join(ProfessionalSpecialty, ProfessionalSpecialty.specialty_id == Specialty.specialty_id)
        .where(Specialty.slug == params.specialty_slug)
        .order_by(ProfessionalSpecialty.professional_id)  # stable, deterministic first-row pick — price is identical across professionals within one specialty in the seeded data
        .limit(1)
    ).first()
    if row is None:
        raise DynamicResolutionError(cause=f"no professional_specialties row for specialty_slug={params.specialty_slug}")
    display_name, price_cents, duration_minutes = row
    text = f"O valor da consulta de {display_name} é {format_price_brl(price_cents)} (simulação). Duração aproximada: {duration_minutes} minutos."
    return DynamicResolution(text, specialty_slug=params.specialty_slug, slot_count=None)


def record_appointment_booking(
    session: Session,
    conversation: Conversation,
    *,
    source: str,
    specialty_id: UUID,
    professional_id: UUID | None = None,
    unit_id: UUID | None = None,
    slot_starts_at: datetime | None = None,
) -> None:
    """007/BS-1..BS-4: one row per completed booking flow, never mutated
    after insert. Shared by both write triggers (`guided_booking.py`'s
    `interpret_payment_reply`, `booking_script/service.py`'s completion
    step) — lives here, not in `guided_booking.py`, because
    `booking_script/service.py` must never import from `guided_booking.py`
    (005's containment boundary); both call sites already import this
    module. Looks `specialty_id` back up to its `slug` once, for the audit
    payload only, so callers only ever have to supply the id."""
    booking = AppointmentBooking(conversation_id=conversation.id, source=source, specialty_id=specialty_id, professional_id=professional_id, unit_id=unit_id, slot_starts_at=slot_starts_at)
    session.add(booking)
    specialty_slug = session.scalar(select(Specialty.slug).where(Specialty.specialty_id == specialty_id))
    record_event(
        session,
        "scheduling.booking_recorded",
        "SYSTEM",
        conversation_id=conversation.id,
        payload={"conversation_id": str(conversation.id), "source": source, "specialty_slug": specialty_slug, "has_slot_detail": professional_id is not None},
    )


def render_booking_summary_line(session: Session, booking: AppointmentBooking) -> str:
    """007/BS-7: fixed, server-rendered template — never LLM-composed,
    matching AA-2/PL-3's own precedent. Full detail when
    `professional_id`/`unit_id`/`slot_starts_at` are all present
    (`source='guided_booking'`); a shorter specialty-only line otherwise
    (`source='booking_script'` — spec.md §6, "the honesty limit")."""
    specialty_name = session.scalar(select(Specialty.display_name).where(Specialty.specialty_id == booking.specialty_id)) or "Consulta"
    if booking.professional_id is None or booking.unit_id is None or booking.slot_starts_at is None:
        return f"{specialty_name} confirmada (simulação)."
    professional_name = session.scalar(select(Professional.display_name).where(Professional.professional_id == booking.professional_id)) or "profissional (simulação)"
    unit_name = session.scalar(select(Unit.name).where(Unit.unit_id == booking.unit_id)) or "unidade (simulação)"
    local_start = booking.slot_starts_at.astimezone(SAO_PAULO)
    weekday = _WEEKDAY_PT[local_start.weekday()]
    return f"{specialty_name} — {professional_name}, {unit_name}, {weekday} {local_start:%d/%m} às {local_start:%H:%M} (America/São_Paulo)"


def booking_summary_dict(session: Session, booking: AppointmentBooking) -> dict:
    """007/BS-5: the operator-facing computed field — full structured
    detail (not just the rendered line), read fresh through the FKs each
    time, matching `automatic_draft_fields()`'s own "compose on top of
    customer_projection(), never store redundantly" precedent."""
    return {
        "source": booking.source,
        "line": render_booking_summary_line(session, booking),
        "has_slot_detail": booking.professional_id is not None,
    }
