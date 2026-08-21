"""005 (GB): guided slot-choice, then a full N2-draft-based CPF/payment
confirmation flow reusing AA-10's own deterministic parsing — never an
autonomous send, never an LLM call.

**Corrected 2026-08-19 (human decision, D-033):** the original design
paused for a separate "Deseja que eu confirme o agendamento?" step before
handing off to AA-10's autonomous script via an independently-typed
booking-intent phrase. Real usage found two defects: (1) embedding
similarity cannot match ordinal/positional replies ("segunda opção", "3")
at all, since they share no semantic content with an offer's own
specialty/day/time text — no threshold fixes this, it needed deterministic
ordinal parsing; (2) the extra confirm-then-independently-say-"quero
marcar" round trip felt broken, not like one continuous flow. This module
now carries the whole CPF/payment conversation itself, as ordinary
operator-approved drafts, one click per step — mirroring
`booking_script/service.py`'s exact message text and state shape, but
**never** calling `send_scripted_message` and **never** touching
`conversation.booking_script_step` (that field remains exclusively AA-10's
own). Reuses `booking_script.parsing`'s pure CPF/payment parsers (no DB,
no I/O, no autonomous-send coupling) — the one narrow, disclosed import
from `booking_script/*`; `booking_script/service.py` itself (home of the
actual autonomous-send mechanism, `send_scripted_message`) is never
imported, and `conversation.booking_script_step` is never written by this
module. See specs/005-dynamic-pricing-and-guided-booking/spec.md
GB-2..GB-8 (as corrected) and `DECISIONS.md` D-033."""

import re
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Row, select
from sqlalchemy.orm import Session

from customer_care.booking_script.parsing import extract_cpf, extract_payment_confirmation
from customer_care.infrastructure.models import AIGeneration, AppointmentOfferPresentation, Conversation, Message
from customer_care.knowledge.embeddings import EmbeddingProvider
from customer_care.scheduling.availability import record_appointment_booking
from customer_care.scheduling.models import AppointmentBooking, ScheduleSlot

# cosine_distance (lower = more similar). Calibrated 2026-08-19 against
# real text-embedding-3-small output, not a guessed constant: genuine
# paraphrases of an offer measured 0.42-0.66 (a generic "the morning one,
# whichever you have" scored 0.64; a specific "Thursday morning with
# Dr. Eduardo" scored 0.42), an unrelated message scored 0.70-0.71. 0.68
# sits in that gap, biased toward the unrelated side since GB-3's fallback
# (ordinary RAG) is always safe.
SLOT_CHOICE_DISTANCE_THRESHOLD = 0.68

# Deterministic ordinal/positional parsing — tried before embedding
# similarity (D-033 correction, 2026-08-19). "segunda opção"/"3"/"a
# terceira" share no semantic content with an offer's own specialty/day/
# time text, so embedding similarity structurally cannot match them,
# regardless of threshold — this is not a calibration problem. Ordinal
# words are tried first (more reliable than a bare digit, which risks
# false positives against unrelated numbers in the message); a bounded
# 1-4 digit fallback second, since AA-2 never offers more than 4 slots.
_ORDINAL_WORDS: dict[str, int] = {
    "primeira": 1, "primeiro": 1,
    "segunda": 2, "segundo": 2,
    "terceira": 3, "terceiro": 3,
    "quarta": 4, "quarto": 4,
}
# The optional [ºª°]? suffix must sit *inside* the trailing \b, not after
# it: "º"/"ª" (MASCULINE/FEMININE ORDINAL INDICATOR) are Unicode category
# Lo ("letter, other") — word characters as far as \b is concerned — so a
# bare r"\b([1-4])\b" never matches "3º opção" at all (no word/non-word
# transition exists between "3" and "º"). Found via real testing, 2026-08-19.
_ORDINAL_DIGIT = re.compile(r"\b([1-4])[ºª°]?\b")

# D-043 (2026-08-21): found while fixing the booking_script/GB interception
# bug above — once a generic reply is correctly let through to this parser
# instead of being intercepted earlier, "primeira"/"segunda"/"terceira"/
# "quarta" turned out to be ordinary Portuguese words that show up in
# plenty of unrelated sentences ("quero agendar uma **primeira**
# consulta", "o que preciso levar para minha **primeira** consulta",
# "**quarta**-feira de manhã") — not just slot choices. A bare word match
# with no other signal produced exactly the two real false positives this
# fix closes. Now only accepted when either an explicit "opção"/"opcao"
# hint is present anywhere in the message, or the whole message is short
# (a bare "primeira" / "a segunda" / "2" reply, the shape every real
# example in this module and its tests actually uses) — a longer message
# with no such hint falls through to ordinary RAG/LLM composition instead,
# same as any other unmatched reply (GB-3).
_OPTION_HINT = re.compile(r"\bop[çc][ãa]o\b", re.IGNORECASE)
_MAX_WORDS_WITHOUT_OPTION_HINT = 4

# D-033: raw CPF replies never reach durable storage for the GB flow
# either — same non-retention rule AA-10 already applies to its own script
# (spec.md §5 AA-10), extended here since GB now asks the same question
# via a parallel, N2-draft-based path. The payment-confirmation reply is
# deliberately *not* redacted (human decision, 2026-08-19) — it is not
# sensitive the way a CPF is, and is kept verbatim for this step.
GB_CPF_INPUT_REDACTION = "[CPF informado na simulação — dado utilizado na janela de contexto da conversa, não armazenado nos bancos de dados]"

# D-035 (2026-08-19): while GB's CPF question is pending, "voltar"/
# "cancelar"/"alterar horário" (and natural variations — "cancela", "mudar
# horário", "trocar horário", "outro horário") let the customer step back
# to a fresh slot choice instead of the reply being parsed as a (necessarily
# invalid) CPF. Checked before `extract_cpf`, not after — a customer typing
# "cancelar" must never see "CPF inválido".
_STEP_BACK_PATTERN = re.compile(r"\b(voltar|cancelar|cancela)\b|\b(alterar|mudar|trocar)\s+(o\s+)?hor[áa]rio\b|\boutro\s+hor[áa]rio\b", re.IGNORECASE)


def _wants_to_step_back(text: str) -> bool:
    return _STEP_BACK_PATTERN.search(text) is not None


def _parse_ordinal_choice(text: str) -> int | None:
    lowered = text.lower()
    if not _OPTION_HINT.search(lowered) and len(lowered.split()) > _MAX_WORDS_WITHOUT_OPTION_HINT:
        return None
    for word, index in _ORDINAL_WORDS.items():
        # (?!-feira): "quarta"/"quarto" must not match inside a weekday
        # name ("quarta-feira") — the one common short exception even the
        # length gate above doesn't catch on its own.
        if re.search(rf"\b{word}\b(?!-feira)", lowered):
            return index
    match = _ORDINAL_DIGIT.search(lowered)
    return int(match.group(1)) if match else None


def _offer_description(specialty_display_name: str, professional_display_name: str, weekday: str, day_month: str, hour_minute: str) -> str:
    """One-line, embedding-friendly summary of a single offer — distinct
    from `availability._render_offers`'s multi-line customer-facing block."""
    return f"{specialty_display_name} com {professional_display_name}, {weekday} {day_month} às {hour_minute}"


def persist_presented_offers(session: Session, provider: EmbeddingProvider, ai_generation_id: UUID, rows: Sequence[Any]) -> None:
    """GB-1: persists exactly the offers a resolved `appointment_availability`
    generation showed the customer, so a later reply can be matched against
    them without re-running the (possibly now-different) live query.
    `rows` are the `_SlotRow`-shaped tuples `resolve_appointment_availability`
    already returns — imported loosely as `Any` here to avoid a circular
    import with `scheduling.availability`, which itself does not depend on
    this module."""
    from customer_care.scheduling.availability import SAO_PAULO, _WEEKDAY_PT

    descriptions = []
    for slot, specialty, professional, _professional_specialty, _unit in rows:
        local_start = slot.starts_at.astimezone(SAO_PAULO)
        descriptions.append(
            _offer_description(
                specialty.display_name,
                professional.display_name,
                _WEEKDAY_PT[local_start.weekday()],
                f"{local_start:%d/%m}",
                f"{local_start:%H:%M}",
            )
        )
    vectors = provider.embed(descriptions)
    for order, ((slot, *_rest), description, vector) in enumerate(zip(rows, descriptions, vectors, strict=True), 1):
        session.add(AppointmentOfferPresentation(ai_generation_id=ai_generation_id, slot_id=slot.slot_id, display_order=order, description=description, embedding=vector))


_GB_ALL_FLOW_TRIGGERS = ("GUIDED_SLOT_SELECTION", "GUIDED_SLOT_RESELECTION", "GUIDED_CPF_CONFIRMED", "GUIDED_BOOKING_COMPLETE")
_GB_TERMINAL_TRIGGER = "GUIDED_BOOKING_COMPLETE"


def _latest_offer_generation_id(session: Session, conversation: Conversation) -> Row[tuple[UUID, datetime]] | None:
    """The most recent `appointment_availability` resolution's offer set
    for this conversation — no "already acted on" filtering. Shared base
    query: `latest_unconfirmed_offer_generation_id` below adds that
    filtering for GB-2's own draft-time fallback matching; the "voltar"
    step-back branches of `interpret_cpf_reply`/`interpret_payment_reply`
    (D-035) call this directly instead, since their own trigger gating
    already proves the conversation is in an active GB sub-flow — by the
    *payment* step, `GUIDED_CPF_CONFIRMED` has necessarily already
    happened, so going through the filtered lookup there would always
    (incorrectly) come back empty."""
    return session.execute(
        select(AppointmentOfferPresentation.ai_generation_id, AIGeneration.created_at)
        .join(AIGeneration, AIGeneration.id == AppointmentOfferPresentation.ai_generation_id)
        .where(AIGeneration.conversation_id == conversation.id)
        .order_by(AIGeneration.created_at.desc())
        .limit(1)
    ).first()


def latest_unconfirmed_offer_generation_id(session: Session, conversation: Conversation) -> UUID | None:
    """005/GB-2: the most recent `appointment_availability` resolution's
    offer set for this conversation — but only while it is genuinely
    still *unconfirmed*. Returns `None` when either:

    - AA-10's own booking script has already taken over
      (`conversation.booking_script_step is not None`); or
    - **(bug found 2026-08-19)** the offer set's flow has actually
      *finished* — i.e. the most recent GB-flow-trigger generation created
      after it is `GUIDED_BOOKING_COMPLETE`. Without this check, a
      completed booking never stopped being "the pending offer set": once
      the flow reached `GUIDED_BOOKING_COMPLETE` ("Agendamento realizado
      com sucesso. Há algo mais que posso ajudar?"), the *next* customer
      message — even a wholly unrelated clinical question — was still
      matched by embedding-similarity against the same 4 old offers
      instead of falling through to ordinary RAG/LLM composition, since
      nothing had ever marked that offer set as resolved. A later,
      genuinely new `appointment_availability` resolution creates its own
      newer offer set, which this function then correctly picks up as the
      pending one instead.

    **Checks only the *latest* GB-flow trigger, not "any" (D-035,
    2026-08-19):** originally this excluded once `GUIDED_CPF_CONFIRMED`
    had *ever* occurred after the resolution, matching an older design
    with no way back past that state. Once "voltar" (`GUIDED_SLOT_
    RESELECTION`) let the customer step back to a fresh slot choice even
    from the payment step, that "ever" check permanently — and
    incorrectly — locked out the offer set the moment a CPF had been
    confirmed even once, regardless of a later "voltar" un-committing it.
    Only the terminal state (the *most recent* flow-trigger being
    `GUIDED_BOOKING_COMPLETE`) truly means "done"; every other state
    (picked, reselecting, or awaiting payment) is still in progress and,
    since GB-4's own message-creation-time gating (`interpret_cpf_reply`/
    `interpret_payment_reply`) intercepts every reply during those states
    before this function's draft-time fallback path is ever reached, is
    never actually mismatched by relaxing this.

    **Second gap, found and fixed 2026-08-21 (D-043):** the GB-trigger
    check above can only ever see a completion that happened *through GB
    itself*. AA-10's own `booking_script` can independently complete a
    booking for this same conversation without ever writing a GB
    `ai_generations` row at all (`booking_script/service.py` writes plain
    `Message` rows directly) — so a booking finished by AA-10 was
    invisible here, and the offer set stayed "pending" forever, ready to
    false-match a later, wholly unrelated customer question. Closed with a
    second, independent signal: `record_appointment_booking()` is the one
    write path both `guided_booking.py` and `booking_script/service.py`
    share (`scheduling/availability.py`) — any completed booking recorded
    for this conversation after the offer set was shown means it is done,
    regardless of which subsystem finished it."""
    if conversation.booking_script_step is not None:
        return None
    row = _latest_offer_generation_id(session, conversation)
    if row is None:
        return None
    generation_id, resolved_at = row
    latest_flow_trigger = session.scalar(
        select(AIGeneration.trigger)
        .where(
            AIGeneration.conversation_id == conversation.id,
            AIGeneration.created_at > resolved_at,
            AIGeneration.trigger.in_(_GB_ALL_FLOW_TRIGGERS),
        )
        .order_by(AIGeneration.created_at.desc())
        .limit(1)
    )
    if latest_flow_trigger == _GB_TERMINAL_TRIGGER:
        return None
    completed_via_booking_script = session.scalar(
        select(AppointmentBooking.booking_id)
        .where(AppointmentBooking.conversation_id == conversation.id, AppointmentBooking.recorded_at > resolved_at)
        .limit(1)
    )
    if completed_via_booking_script is not None:
        return None
    return generation_id


def interpret_slot_choice(session: Session, provider: EmbeddingProvider, conversation: Conversation, customer_text: str) -> AppointmentOfferPresentation | None:
    """005/GB-2/GB-3: ordinal/positional parsing first (deterministic,
    exact), embedding-similarity second (paraphrases of the offer's own
    content) — no LLM call either way. Returns `None` on no pending offer
    set or no confident match of either kind, letting the caller fall
    through to ordinary RAG composition (GB-3) by construction."""
    generation_id = latest_unconfirmed_offer_generation_id(session, conversation)
    if generation_id is None:
        return None
    ordinal = _parse_ordinal_choice(customer_text)
    if ordinal is not None:
        offer = session.scalar(
            select(AppointmentOfferPresentation).where(
                AppointmentOfferPresentation.ai_generation_id == generation_id,
                AppointmentOfferPresentation.display_order == ordinal,
            )
        )
        if offer is not None:
            # 007/BS-2: stage which specific offer this was, for
            # interpret_payment_reply() to source the booking record from
            # once the flow actually completes (plan.md §2).
            conversation.guided_booking_selected_offer_id = offer.id
            return offer
        # A named ordinal outside this offer set's actual range (e.g.
        # "quarta opção" with only 2 offers) falls through to embedding
        # matching below rather than erroring — that will most likely also
        # fail to a confident match, landing on GB-3's safe RAG fallback.
    [vector] = provider.embed([customer_text])
    best = session.execute(
        select(AppointmentOfferPresentation, AppointmentOfferPresentation.embedding.cosine_distance(vector).label("distance"))
        .where(AppointmentOfferPresentation.ai_generation_id == generation_id)
        .order_by("distance")
        .limit(1)
    ).first()
    if best is None or best.distance > SLOT_CHOICE_DISTANCE_THRESHOLD:
        return None
    conversation.guided_booking_selected_offer_id = best[0].id
    return best[0]


def offer_price_text(session: Session, offer: AppointmentOfferPresentation) -> str:
    """Reads price live through `offer.slot_id` (never denormalized, same
    read-through-the-FK design as the rest of GB-1). Mirrors
    `booking_script/service.py::lookup_recent_specialty_price`'s own
    fallback text for the no-pricing-row case, which should not happen
    against seeded data."""
    from customer_care.scheduling.availability import format_price_brl
    from customer_care.scheduling.models import ProfessionalSpecialty, ScheduleSlot

    slot = session.get(ScheduleSlot, offer.slot_id)
    if slot is None:
        return "a combinar (simulação)"
    price_cents = session.scalar(
        select(ProfessionalSpecialty.fixed_price_cents).where(
            ProfessionalSpecialty.professional_id == slot.professional_id,
            ProfessionalSpecialty.specialty_id == slot.specialty_id,
        )
    )
    return f"{format_price_brl(price_cents)} (simulação)" if price_cents is not None else "a combinar (simulação)"


def render_offer_reselection_text(session: Session, generation_id: UUID) -> str:
    """D-035: re-presents the *same* originally shown offer set (not a
    fresh query — the point of "voltar" is to go back, not to search
    again) as a numbered list, so a follow-up ordinal reply
    ("primeira"/"2"/...) resolves the same way it did the first time via
    `interpret_slot_choice`."""
    offers = session.scalars(
        select(AppointmentOfferPresentation).where(AppointmentOfferPresentation.ai_generation_id == generation_id).order_by(AppointmentOfferPresentation.display_order)
    ).all()
    lines = [f"{offer.display_order}. {offer.description} — {offer_price_text(session, offer)}." for offer in offers]
    return "Sem problema! Escolha outra opção:\n\n" + "\n".join(lines)


def _latest_operator_message_trigger(session: Session, conversation: Conversation) -> str | None:
    """The most recent OPERATOR message's originating generation's
    `trigger`, with no "customer already replied" gating — used only by
    `pending_redaction_step`, which must decide *before* the new customer
    message it concerns is inserted. Contrast with
    `latest_sent_generation_trigger` below, used by draft-time
    interpretation, which runs after that message already exists."""
    latest_operator_message = session.scalar(
        select(Message).where(Message.conversation_id == conversation.id, Message.author_type == "OPERATOR").order_by(Message.created_at.desc()).limit(1)
    )
    if latest_operator_message is None or latest_operator_message.source_generation_id is None:
        return None
    generation = session.get(AIGeneration, latest_operator_message.source_generation_id)
    return generation.trigger if generation is not None else None


def pending_redaction_step(session: Session, conversation: Conversation) -> str | None:
    """005/D-033, narrowed 2026-08-19 (human decision): only the CPF reply
    is redacted — the payment-confirmation reply ("sim"/"não" and free-
    form variants) is not sensitive the way a CPF is, and the human
    explicitly asked to keep it verbatim for this step. Mirrors AA-10's
    own `booking_script_step`-keyed redaction check
    (`booking_script/service.py::persisted_customer_body`), scoped to GB's
    own CPF step only. Returns `"AWAITING_CPF"` / `None` — reuses AA-10's
    vocabulary for the one value that still applies."""
    if conversation.booking_script_step is not None:
        return None
    trigger = _latest_operator_message_trigger(session, conversation)
    if trigger == "GUIDED_SLOT_SELECTION":
        return "AWAITING_CPF"
    return None


def persisted_customer_body(session: Session, conversation: Conversation, raw_body: str) -> str:
    """The only durable value for a customer message while GB's own CPF
    step is pending — parsing still receives the request-local raw value
    (via `interpret_cpf_reply` below), only the stored `Message.body` is
    redacted. The payment-confirmation reply is stored verbatim (human
    decision, 2026-08-19) — `interpret_payment_reply` still reads it the
    same way regardless, since it never depended on this function."""
    step = pending_redaction_step(session, conversation)
    if step == "AWAITING_CPF":
        return GB_CPF_INPUT_REDACTION
    return raw_body


def latest_sent_generation_trigger(session: Session, conversation: Conversation) -> str | None:
    """The trigger of the most recent OPERATOR-sent message's originating
    generation, requiring at least one customer message after it (so this
    only fires once per operator message, at the moment a real reply to it
    exists) — used by `interpret_cpf_reply`/`interpret_payment_reply`,
    called during draft generation for that reply. Reuses
    `Message.source_generation_id`, an existing FK, no new lookup
    mechanism."""
    latest_operator_message = session.scalar(
        select(Message).where(Message.conversation_id == conversation.id, Message.author_type == "OPERATOR").order_by(Message.created_at.desc()).limit(1)
    )
    if latest_operator_message is None or latest_operator_message.source_generation_id is None:
        return None
    has_customer_reply_after = session.scalar(
        select(Message.id)
        .where(Message.conversation_id == conversation.id, Message.author_type == "CUSTOMER", Message.created_at > latest_operator_message.created_at)
        .limit(1)
    )
    if has_customer_reply_after is None:
        return None
    generation = session.get(AIGeneration, latest_operator_message.source_generation_id)
    return generation.trigger if generation is not None else None


def interpret_cpf_reply(session: Session, conversation: Conversation, customer_text: str) -> tuple[str, str] | None:
    """005/GB-4 (corrected): `None` if this customer message isn't a reply
    to a GB-issued CPF request. Else `(draft_text, next_trigger)` — reuses
    `booking_script.parsing.extract_cpf` verbatim (same digit-count-only
    validation, never the real CPF check-digit algorithm, matching AA-10's
    own "é uma simulação" framing).

    **D-035:** "voltar"/"cancelar"/"alterar horário" (checked first, before
    `extract_cpf`) step back to a fresh slot choice instead — the same
    originally offered set, re-presented, `trigger='GUIDED_SLOT_RESELECTION'`
    so a follow-up reply is routed to `interpret_slot_choice` again (GB-2)
    rather than back into this CPF-parsing gate."""
    if conversation.booking_script_step is not None:
        return None
    if latest_sent_generation_trigger(session, conversation) != "GUIDED_SLOT_SELECTION":
        return None
    if _wants_to_step_back(customer_text):
        row = _latest_offer_generation_id(session, conversation)
        if row is not None:
            return render_offer_reselection_text(session, row[0]), "GUIDED_SLOT_RESELECTION"
    cpf = extract_cpf(customer_text)
    if cpf is None:
        return "CPF inválido. Informe um número válido de 11 dígitos.", "GUIDED_SLOT_SELECTION"
    return f"CPF {cpf} confirmado.\n\nO valor foi pago? Responda sim ou não.\n\nDigite Voltar para escolher outro horário.", "GUIDED_CPF_CONFIRMED"


def interpret_payment_reply(session: Session, conversation: Conversation, customer_text: str) -> tuple[str, str] | None:
    """005/GB-4 (corrected): `None` if this customer message isn't a reply
    to a GB-issued payment question. Else `(draft_text, next_trigger)` —
    reuses `booking_script.parsing.extract_payment_confirmation` verbatim
    (same sim/não word-boundary matching, unlimited retries on
    negative/unclear).

    **D-035:** "voltar"/"cancelar"/"alterar horário" (checked first, before
    `extract_payment_confirmation`) step back to a fresh slot choice too —
    same mechanism as `interpret_cpf_reply`'s own step-back, covering both
    the initial "CPF confirmado..." question and its own negative-reply
    re-ask (both share this trigger, so one check covers both)."""
    if conversation.booking_script_step is not None:
        return None
    if latest_sent_generation_trigger(session, conversation) != "GUIDED_CPF_CONFIRMED":
        return None
    if _wants_to_step_back(customer_text):
        row = _latest_offer_generation_id(session, conversation)
        if row is not None:
            return render_offer_reselection_text(session, row[0]), "GUIDED_SLOT_RESELECTION"
    if extract_payment_confirmation(customer_text) is True:
        # 007/BS-2: source the completed-booking record from the specific
        # offer GB-2's ordinal/embedding match identified — staged on the
        # conversation since that step, several messages ago (plan.md §2).
        if conversation.guided_booking_selected_offer_id is not None:
            offer = session.get(AppointmentOfferPresentation, conversation.guided_booking_selected_offer_id)
            slot = session.get(ScheduleSlot, offer.slot_id) if offer is not None else None
            if slot is not None:
                record_appointment_booking(session, conversation, source="guided_booking", specialty_id=slot.specialty_id, professional_id=slot.professional_id, unit_id=slot.unit_id, slot_starts_at=slot.starts_at)
            conversation.guided_booking_selected_offer_id = None
        return "Verificando pagamento. Pagamento verificado. Agendamento realizado com sucesso. Há algo mais que posso ajudar?", "GUIDED_BOOKING_COMPLETE"
    return "O valor foi pago? Responda sim ou não.\n\nDigite Voltar para escolher outro horário.", "GUIDED_CPF_CONFIRMED"


def advance_guided_booking(session: Session, conversation: Conversation, raw_customer_text: str) -> None:
    """005/D-033: the message-creation-time entry point, called only from
    `anonymous_access/router.py`'s `send_customer_message()` alongside
    AA-10's own `advance_booking_script()` — mirrors that function's shape
    deliberately (same call-site pattern, same "parses only the
    request-local raw value" principle) without ever calling into
    `booking_script.service` or touching `booking_script_step`. Stashes
    the interpreted *result* on the conversation (transient state, not an
    audited durable fact — same framing as `booking_script_step` itself)
    for the next draft-generation call to pick up — the only way a later,
    operator-click-driven "Gerar rascunho" can react to what a raw CPF/
    payment reply actually said without ever persisting that raw value
    anywhere. Call `advance_booking_script` first in the caller so AA-10
    takes priority on the rare message that could satisfy both."""
    if conversation.booking_script_step is not None:
        return
    result = interpret_cpf_reply(session, conversation, raw_customer_text) or interpret_payment_reply(session, conversation, raw_customer_text)
    if result is None:
        return
    text, next_trigger = result
    conversation.guided_booking_pending_text = text
    conversation.guided_booking_pending_trigger = next_trigger
