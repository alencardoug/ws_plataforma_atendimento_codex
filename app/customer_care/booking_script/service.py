"""The state machine and the one exceptional send path. plan.md §8b."""

from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from customer_care.audit.service import record_event
from customer_care.booking_script.parsing import detect_booking_intent, extract_cpf, extract_payment_confirmation
from customer_care.infrastructure.models import AIGeneration, AIGenerationSource, AuditEvent, Conversation, Message, QAEntry, RetrievalHit
from customer_care.scheduling.availability import format_price_brl
from customer_care.scheduling.models import ProfessionalSpecialty, Specialty


class BookingScriptStep(str, Enum):
    AWAITING_CPF = "AWAITING_CPF"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"


def send_scripted_message(session: Session, conversation: Conversation, body: str, step: str) -> Message:
    """**The only function in the entire codebase allowed to create a
    customer-visible `Message` without an authenticated-operator
    dependency in its call chain** — grep-able, single-purpose, never
    imported anywhere except `booking_script/` itself (Constitution
    Amendment 1.1.0, `DECISIONS.md` D-031). `step` is an audit-only label
    for which part of the script this send belongs to (e.g.
    `"AWAITING_CPF"` for the "CPF inválido" retry) — not the same value as
    `conversation.booking_script_step`, which the caller updates
    separately once per state-machine transition, not once per message.

    `created_at` is set explicitly from Python's wall clock rather than
    left to the column's `now()` server default — Postgres's `now()` is
    constant for the whole transaction, so two-plus messages sent within
    one `advance_booking_script()` call would otherwise get an *identical*
    `created_at`, and the real message-list ordering
    (`conversations/projections.py`: `ORDER BY created_at, id`) would then
    tie-break on `id` — a random UUID — risking the script's messages
    displaying to the customer out of their scripted order. Found via
    T095's own flaky-under-suite-ordering test failure, not by inspection."""
    message = Message(conversation_id=conversation.id, author_type="OPERATOR", body=body, autonomous_source="booking_script", created_at=datetime.now(UTC))
    session.add(message)
    session.flush()
    conversation.last_message_at = message.created_at
    record_event(
        session,
        "booking_script.autonomous_message_sent",
        "SYSTEM",
        conversation_id=conversation.id,
        payload={"conversation_id": str(conversation.id), "message_id": str(message.id), "step": step},
    )
    return message


def _latest_dynamic_generation(session: Session, conversation: Conversation) -> AIGeneration | None:
    return session.scalar(
        select(AIGeneration)
        .where(AIGeneration.conversation_id == conversation.id, AIGeneration.dynamic_pattern_used.is_(True))
        .order_by(AIGeneration.created_at.desc())
    )


def _resolved_specialty_slug(session: Session, generation: AIGeneration) -> str | None:
    """The resolver name itself is never stored on `AIGeneration` — the
    durable record of "which specialty this resolution was about" is the
    `ai.dynamic_pattern_resolved` audit event's own payload (Phase 5,
    `plan.md` §7), which this reuses rather than inventing a new field."""
    event = session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == "ai.dynamic_pattern_resolved",
            AuditEvent.payload_json["ai_generation_id"].astext == str(generation.id),
        )
    )
    if event is None:
        return None
    specialty_slug = event.payload_json.get("specialty_slug")
    return specialty_slug if isinstance(specialty_slug, str) else None


def has_recent_resolved_availability(session: Session, conversation: Conversation) -> bool:
    """The concrete form of AA-10's own framing: "after a customer
    expresses intent to book one of the real slots AA-1..AA-9 showed
    them." Requires the most recent dynamic-pattern-resolved generation on
    this conversation to specifically be an `appointment_availability`
    resolution — a generic V2 `qa_dynamic_bindings` resolution (e.g. the
    `knowledge_dynamic_fixture` demo table) never starts this script."""
    generation = _latest_dynamic_generation(session, conversation)
    if generation is None:
        return False
    source = session.scalar(select(AIGenerationSource).where(AIGenerationSource.ai_generation_id == generation.id, AIGenerationSource.use_order == 1))
    if source is None:
        return False
    hit = session.get(RetrievalHit, source.retrieval_hit_id)
    if hit is None or not hit.matched_qa_id:
        return False
    qa = session.get(QAEntry, hit.matched_qa_id)
    return qa is not None and qa.dynamic_resolver == "appointment_availability"


def lookup_recent_specialty_price(session: Session, conversation: Conversation) -> int | None:
    """Reuses `professional_specialties.fixed_price_cents` (§3/§4b) —
    no new price source. `None` only if the resolved specialty has since
    lost its pricing row (should not happen with seeded, static data)."""
    generation = _latest_dynamic_generation(session, conversation)
    if generation is None:
        return None
    specialty_slug = _resolved_specialty_slug(session, generation)
    if specialty_slug is None:
        return None
    return session.scalar(
        select(ProfessionalSpecialty.fixed_price_cents)
        .join(Specialty, Specialty.specialty_id == ProfessionalSpecialty.specialty_id)
        .where(Specialty.slug == specialty_slug)
        .limit(1)
    )


def advance_booking_script(session: Session, conversation: Conversation, customer_message: Message) -> None:
    """The single entry point, called only from
    `anonymous_access/router.py`'s `send_customer_message()` (Phase 9
    "Trigger"). `plan.md` §8b."""
    step = conversation.booking_script_step

    if step is None:
        if not detect_booking_intent(customer_message.body):
            return
        if not has_recent_resolved_availability(session, conversation):
            return  # never start the script out of context
        send_scripted_message(session, conversation, "Agendamento realizado", step="START")
        send_scripted_message(session, conversation, "Informe seu CPF - é uma simulação, informe qualquer número de 11 dígitos", step="START")
        conversation.booking_script_step = BookingScriptStep.AWAITING_CPF.value
        return

    if step == BookingScriptStep.AWAITING_CPF.value:
        cpf = extract_cpf(customer_message.body)
        if cpf is None:
            send_scripted_message(session, conversation, "CPF inválido. Informe um número válido de 11 dígitos", step=BookingScriptStep.AWAITING_CPF.value)
            return  # stays on AWAITING_CPF, no retry limit
        send_scripted_message(session, conversation, f"CPF {cpf} confirmado", step=BookingScriptStep.AWAITING_CPF.value)
        price_cents = lookup_recent_specialty_price(session, conversation)
        price_text = f"{format_price_brl(price_cents)} (simulação)" if price_cents is not None else "a combinar (simulação)"
        send_scripted_message(session, conversation, f"O valor da consulta é {price_text}", step=BookingScriptStep.AWAITING_CPF.value)
        send_scripted_message(session, conversation, "O valor foi pago? Responda sim ou não", step=BookingScriptStep.AWAITING_CPF.value)
        conversation.booking_script_step = BookingScriptStep.AWAITING_PAYMENT.value
        return

    if step == BookingScriptStep.AWAITING_PAYMENT.value:
        if extract_payment_confirmation(customer_message.body) is not True:
            send_scripted_message(session, conversation, "O valor foi pago? Responda sim ou não", step=BookingScriptStep.AWAITING_PAYMENT.value)
            return  # stays on AWAITING_PAYMENT, no retry limit
        send_scripted_message(session, conversation, "Verificando pagamento", step=BookingScriptStep.AWAITING_PAYMENT.value)
        send_scripted_message(session, conversation, "Pagamento verificado", step=BookingScriptStep.AWAITING_PAYMENT.value)
        send_scripted_message(session, conversation, "Agendamento realizado com sucesso. Há algo mais que posso ajudar?", step=BookingScriptStep.AWAITING_PAYMENT.value)
        conversation.booking_script_step = None
        return
