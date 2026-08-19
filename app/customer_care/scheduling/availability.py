"""Deterministic parameter extraction (AA-3/AA-3a) plus, from Phase 3
onward, the purely read-only query resolver (AA-1/AA-2/AA-4/AA-5/AA-8).
See specs/004-dynamic-appointment-availability/plan.md §5 (this phase) and
§4 (Phase 3)."""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Row, and_, extract, select
from sqlalchemy.orm import Session

from customer_care.knowledge.dynamic_binding import DynamicResolution, DynamicResolutionError
from customer_care.scheduling.models import Professional, ProfessionalSpecialty, ScheduleSlot, Specialty, Unit

SAO_PAULO = ZoneInfo("America/Sao_Paulo")

GENERALIST_SLUG = "oncologia-geral"

SPECIALTY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "mastologia-oncologica": ("mastologia", "mama", "peito"),
    "cirurgia-colorretal": ("colorretal", "intestino", "cólon", "colon", "reto"),
    "segunda-opiniao": ("segunda opinião", "segunda opiniao"),
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


def extract_parameters(query_text: str, reference_date: date | None = None) -> ExtractedParameters:
    """Pure, deterministic, no database/I-O. `specialty_slug` always
    resolves to a real seeded specialty — defaults to `GENERALIST_SLUG`
    when no diagnosis-specific keyword matches, never unfiltered
    (`spec.md` AA-3a). `target_date`/`period_hours` stay optional — an
    unmatched one is simply not filtered on downstream."""
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

    return ExtractedParameters(specialty_slug=specialty_slug, target_date=target_date, period_hours=period_hours)


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
    itself, staying purely read-only as AA-2 requires."""
    params = extract_parameters(query_text)
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
