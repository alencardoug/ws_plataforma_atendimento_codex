"""005/GB, tasks.md T034/T041/T054 (revised 2026-08-19, D-033):
real-database integration tests for scheduling/guided_booking.py's
GB-1..GB-8 mechanics. Uses DeterministicTestEmbeddingProvider (hash-based,
not semantic — suitable only for exact-match/no-match structural
assertions here; genuine paraphrase-recognition quality is verified
separately by smoke_v5_guided_booking.py against the real provider,
matching this project's existing unit-vs-smoke testing split).
specs/005-dynamic-pricing-and-guided-booking/plan.md §7."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete

from customer_care.auth.security import hash_password
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import (
    AIGeneration,
    AppointmentOfferPresentation,
    Conversation,
    Message,
    OperatorUser,
    RetrievalRun,
)
from customer_care.knowledge.embeddings import DeterministicTestEmbeddingProvider
from customer_care.scheduling.guided_booking import (
    GB_CPF_INPUT_REDACTION,
    advance_guided_booking,
    interpret_cpf_reply,
    interpret_payment_reply,
    interpret_slot_choice,
    latest_unconfirmed_offer_generation_id,
    pending_redaction_step,
    persisted_customer_body,
)
from customer_care.scheduling.models import ScheduleSlot

# Real seeded mastologia-oncologica specialty/professional/unit — same IDs
# test_appointment_availability_resolver.py already relies on.
_UNIT_ID = "10000000-0000-0000-0000-000000000001"
_SPECIALTY_ID = "20000000-0000-0000-0000-000000000001"
_PROFESSIONAL_ID = "30000000-0000-0000-0000-000000000001"

PROVIDER = DeterministicTestEmbeddingProvider()


@pytest.fixture
def operator_id():
    session_factory = get_session_factory()
    with session_factory() as db:
        operator = OperatorUser(email=f"t005-gb-{uuid4().hex[:8]}@example.com", password_hash=hash_password("irrelevant"), display_name="T005 GB fixture")
        db.add(operator)
        db.commit()
        oid = operator.id
    yield oid
    with session_factory() as db:
        db.execute(delete(OperatorUser).where(OperatorUser.id == oid))
        db.commit()


@pytest.fixture
def conversation_with_generation(operator_id):
    """A conversation plus one AIGeneration with 2 persisted offers — the
    minimal fixture GB-2's interpret_slot_choice needs."""
    session_factory = get_session_factory()
    with session_factory() as db:
        conversation = Conversation(anonymous_token_digest=uuid4().hex, initial_mode="N2", effective_mode="N2")
        db.add(conversation)
        db.flush()
        run = RetrievalRun(operator_id=operator_id, purpose="N2_DRAFT", query_text="t005-gb", embedding_model="smoke", top_k=1, status="COMPLETED")
        db.add(run)
        db.flush()
        generation = AIGeneration(
            conversation_id=conversation.id, retrieval_run_id=run.id, operator_id=operator_id, status="ANSWER",
            draft_text="offers", provider="dynamic-pattern-resolver", model="not-applicable", prompt_version="not-applicable",
            trigger="MANUAL_DRAFT", dynamic_pattern_used=True,
        )
        db.add(generation)
        db.flush()
        # FK-satisfying: a slot this fixture owns and cleans up itself,
        # rather than borrowing whatever happens to exist in
        # scheduling.schedule_slots at the moment — other suites
        # (test_appointment_seeding.py) legitimately create/delete their own
        # slots, so ambient state isn't reliable across a full test run. A
        # far-future date avoids any D+1/D+7 collision, matching
        # test_appointment_availability_resolver.py's own fixture pattern.
        far_future = datetime.now(tz=UTC) + timedelta(days=400)
        slot = ScheduleSlot(unit_id=_UNIT_ID, specialty_id=_SPECIALTY_ID, professional_id=_PROFESSIONAL_ID, starts_at=far_future, ends_at=far_future + timedelta(minutes=60), status="available")
        db.add(slot)
        db.flush()
        descriptions = ["Mastologia oncológica com Dra. Ana, segunda-feira 20/08 às 09:00", "Cirurgia colorretal com Dr. Bruno, terça-feira 21/08 às 15:00"]
        vectors = PROVIDER.embed(descriptions)
        for order, (description, vector) in enumerate(zip(descriptions, vectors, strict=True), 1):
            db.add(AppointmentOfferPresentation(ai_generation_id=generation.id, slot_id=slot.slot_id, display_order=order, description=description, embedding=vector))
        db.commit()
        conversation_id, generation_id, slot_id = conversation.id, generation.id, slot.slot_id
    yield conversation_id, generation_id, descriptions
    with session_factory() as db:
        db.execute(delete(Message).where(Message.conversation_id == conversation_id))
        db.execute(delete(AppointmentOfferPresentation).where(AppointmentOfferPresentation.ai_generation_id == generation_id))
        db.execute(delete(AIGeneration).where(AIGeneration.id == generation_id))
        db.execute(delete(ScheduleSlot).where(ScheduleSlot.slot_id == slot_id))
        db.execute(delete(RetrievalRun).where(RetrievalRun.operator_id == operator_id))
        db.execute(delete(Conversation).where(Conversation.id == conversation_id))
        db.commit()


def _send_operator_message(db, conversation_id, generation_id, operator_id, body: str) -> None:
    db.add(Message(conversation_id=conversation_id, author_type="OPERATOR", operator_id=operator_id, body=body, source_generation_id=generation_id))
    db.commit()


def _send_customer_message(db, conversation_id, body: str) -> None:
    db.add(Message(conversation_id=conversation_id, author_type="CUSTOMER", body=body))
    db.commit()


class TestLatestUnconfirmedOfferGenerationId:
    def test_returns_the_generation_id_when_offers_are_pending(self, conversation_with_generation) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        with get_session_factory()() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            assert latest_unconfirmed_offer_generation_id(db, conversation) == generation_id

    def test_returns_none_once_booking_script_has_taken_over(self, conversation_with_generation) -> None:
        conversation_id, _generation_id, _descriptions = conversation_with_generation
        session_factory = get_session_factory()
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            conversation.booking_script_step = "AWAITING_CPF"
            db.commit()
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            assert latest_unconfirmed_offer_generation_id(db, conversation) is None


class TestInterpretSlotChoice:
    def test_exact_text_match_returns_that_offer(self, conversation_with_generation) -> None:
        conversation_id, _generation_id, descriptions = conversation_with_generation
        with get_session_factory()() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            offer = interpret_slot_choice(db, PROVIDER, conversation, descriptions[1])
        assert offer is not None
        assert offer.description == descriptions[1]

    @pytest.mark.parametrize("text,expected_order", [("segunda opção", 2), ("a segunda", 2), ("2", 2), ("primeira", 1), ("1", 1), ("quero a primeira opção por favor", 1)])
    def test_ordinal_reference_matches_by_position_not_embedding(self, conversation_with_generation, text: str, expected_order: int) -> None:
        """D-033: the whole point of the ordinal parser — these phrases
        share no semantic content with either offer's own description, so
        only positional parsing (not embedding similarity, even with the
        real provider) can resolve them."""
        conversation_id, _generation_id, descriptions = conversation_with_generation
        with get_session_factory()() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            offer = interpret_slot_choice(db, PROVIDER, conversation, text)
        assert offer is not None
        assert offer.display_order == expected_order
        assert offer.description == descriptions[expected_order - 1]

    def test_ordinal_out_of_range_falls_through_to_embedding_not_error(self, conversation_with_generation) -> None:
        conversation_id, _generation_id, _descriptions = conversation_with_generation
        with get_session_factory()() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            # Only 2 offers exist in this fixture; "quarta opção" (4) is
            # out of range and must not raise.
            interpret_slot_choice(db, PROVIDER, conversation, "quarta opção")  # no exception

    def test_no_pending_offers_returns_none(self, operator_id) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            conversation = Conversation(anonymous_token_digest=uuid4().hex, initial_mode="N2", effective_mode="N2")
            db.add(conversation)
            db.commit()
            conversation_id = conversation.id
        try:
            with session_factory() as db:
                reloaded = db.get(Conversation, conversation_id)
                assert reloaded is not None
                assert interpret_slot_choice(db, PROVIDER, reloaded, "qualquer coisa") is None
        finally:
            with session_factory() as db:
                db.execute(delete(Conversation).where(Conversation.id == conversation_id))
                db.commit()


class TestInterpretCpfReply:
    def test_none_when_no_cpf_request_was_sent(self, conversation_with_generation) -> None:
        conversation_id, _generation_id, _descriptions = conversation_with_generation
        with get_session_factory()() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            assert interpret_cpf_reply(db, conversation, "123.456.789-10") is None

    def test_invalid_cpf_reasks_staying_on_slot_selection_trigger(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        session_factory = get_session_factory()
        with session_factory() as db:
            generation = db.get(AIGeneration, generation_id)
            assert generation is not None
            generation.trigger = "GUIDED_SLOT_SELECTION"
            _send_operator_message(db, conversation_id, generation_id, operator_id, "Informe seu CPF...")
        with session_factory() as db:
            _send_customer_message(db, conversation_id, "Ah 123456a8910")
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            result = interpret_cpf_reply(db, conversation, "Ah 123456a8910")
        assert result == ("CPF inválido. Informe um número válido de 11 dígitos.", "GUIDED_SLOT_SELECTION")

    def test_valid_cpf_confirms_and_asks_payment(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        session_factory = get_session_factory()
        with session_factory() as db:
            generation = db.get(AIGeneration, generation_id)
            assert generation is not None
            generation.trigger = "GUIDED_SLOT_SELECTION"
            _send_operator_message(db, conversation_id, generation_id, operator_id, "Informe seu CPF...")
        with session_factory() as db:
            _send_customer_message(db, conversation_id, "tabom 123.456..789.10")
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            result = interpret_cpf_reply(db, conversation, "tabom 123.456..789.10")
        assert result is not None
        text, next_trigger = result
        assert text == "CPF 123.456.789-10 confirmado. O valor foi pago? Responda sim ou não."
        assert next_trigger == "GUIDED_CPF_CONFIRMED"


class TestInterpretPaymentReply:
    def test_none_when_no_payment_question_was_sent(self, conversation_with_generation) -> None:
        conversation_id, _generation_id, _descriptions = conversation_with_generation
        with get_session_factory()() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            assert interpret_payment_reply(db, conversation, "sim") is None

    def test_affirmative_completes_the_booking(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        session_factory = get_session_factory()
        with session_factory() as db:
            generation = db.get(AIGeneration, generation_id)
            assert generation is not None
            generation.trigger = "GUIDED_CPF_CONFIRMED"
            _send_operator_message(db, conversation_id, generation_id, operator_id, "CPF confirmado. O valor foi pago?")
        with session_factory() as db:
            _send_customer_message(db, conversation_id, "tabom simm paguei")
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            result = interpret_payment_reply(db, conversation, "tabom simm paguei")
        assert result is not None
        text, next_trigger = result
        assert text == "Verificando pagamento. Pagamento verificado. Agendamento realizado com sucesso. Há algo mais que posso ajudar?"
        assert next_trigger == "GUIDED_BOOKING_COMPLETE"

    def test_negative_reasks_staying_on_cpf_confirmed_trigger(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        session_factory = get_session_factory()
        with session_factory() as db:
            generation = db.get(AIGeneration, generation_id)
            assert generation is not None
            generation.trigger = "GUIDED_CPF_CONFIRMED"
            _send_operator_message(db, conversation_id, generation_id, operator_id, "CPF confirmado. O valor foi pago?")
        with session_factory() as db:
            _send_customer_message(db, conversation_id, "Então, não paguei")
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            result = interpret_payment_reply(db, conversation, "Então, não paguei")
        assert result == ("O valor foi pago? Responda sim ou não.", "GUIDED_CPF_CONFIRMED")


class TestAdvanceGuidedBooking:
    """The message-creation-time orchestrator — the only place a raw CPF/
    payment reply is ever read (D-033)."""

    def test_stages_pending_text_on_valid_cpf(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        session_factory = get_session_factory()
        with session_factory() as db:
            generation = db.get(AIGeneration, generation_id)
            assert generation is not None
            generation.trigger = "GUIDED_SLOT_SELECTION"
            _send_operator_message(db, conversation_id, generation_id, operator_id, "Informe seu CPF...")
        with session_factory() as db:
            _send_customer_message(db, conversation_id, "tabom 123.456..789.10")
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            advance_guided_booking(db, conversation, "tabom 123.456..789.10")
            db.commit()
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            assert conversation.guided_booking_pending_text == "CPF 123.456.789-10 confirmado. O valor foi pago? Responda sim ou não."
            assert conversation.guided_booking_pending_trigger == "GUIDED_CPF_CONFIRMED"

    def test_no_op_once_booking_script_has_taken_over(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        session_factory = get_session_factory()
        with session_factory() as db:
            generation = db.get(AIGeneration, generation_id)
            assert generation is not None
            generation.trigger = "GUIDED_SLOT_SELECTION"
            _send_operator_message(db, conversation_id, generation_id, operator_id, "Informe seu CPF...")
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            conversation.booking_script_step = "AWAITING_CPF"
            db.commit()
        with session_factory() as db:
            _send_customer_message(db, conversation_id, "123.456.789-10")
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            advance_guided_booking(db, conversation, "123.456.789-10")
            db.commit()
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            assert conversation.guided_booking_pending_text is None


class TestRedaction:
    """D-033: GB's own CPF reply must never reach durable storage raw —
    same rule AA-10 already applies to its own script. The payment-
    confirmation reply is deliberately *not* redacted (human decision,
    2026-08-19) — kept verbatim for that step."""

    def test_pending_redaction_step_awaiting_cpf(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        session_factory = get_session_factory()
        with session_factory() as db:
            generation = db.get(AIGeneration, generation_id)
            assert generation is not None
            generation.trigger = "GUIDED_SLOT_SELECTION"
            _send_operator_message(db, conversation_id, generation_id, operator_id, "Informe seu CPF...")
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            assert pending_redaction_step(db, conversation) == "AWAITING_CPF"
            assert persisted_customer_body(db, conversation, "123.456.789-10") == GB_CPF_INPUT_REDACTION

    def test_payment_reply_is_kept_verbatim_not_redacted(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        session_factory = get_session_factory()
        with session_factory() as db:
            generation = db.get(AIGeneration, generation_id)
            assert generation is not None
            generation.trigger = "GUIDED_CPF_CONFIRMED"
            _send_operator_message(db, conversation_id, generation_id, operator_id, "O valor foi pago?")
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            assert pending_redaction_step(db, conversation) is None
            assert persisted_customer_body(db, conversation, "sim") == "sim"

    def test_no_redaction_outside_gb_cpf_payment_steps(self, conversation_with_generation) -> None:
        conversation_id, _generation_id, _descriptions = conversation_with_generation
        with get_session_factory()() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            assert pending_redaction_step(db, conversation) is None
            assert persisted_customer_body(db, conversation, "qualquer coisa") == "qualquer coisa"
