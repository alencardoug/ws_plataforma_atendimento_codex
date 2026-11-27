"""005/GB, tasks.md T034/T041/T054 (revised 2026-08-19, D-033):
real-database integration tests for scheduling/guided_booking.py's
GB-1..GB-8 mechanics. Uses DeterministicTestEmbeddingProvider (hash-based,
not semantic — suitable only for exact-match/no-match structural
assertions here; genuine paraphrase-recognition quality is verified
separately by smoke_v5_guided_booking.py against the real provider,
matching this project's existing unit-vs-smoke testing split).
specs/005-dynamic-pricing-and-guided-booking/plan.md §7."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

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
    GB_CANCELLED_TEXT,
    GB_CPF_INPUT_REDACTION,
    advance_guided_booking,
    interpret_cpf_reply,
    interpret_payment_reply,
    interpret_slot_choice,
    latest_unconfirmed_offer_generation_id,
    pending_redaction_step,
    persisted_customer_body,
)
from customer_care.scheduling.models import AppointmentBooking, ScheduleSlot

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
        # D-045: tests add their own later GB-step generations via
        # _add_generation(); remove every generation of this conversation.
        db.execute(delete(AIGeneration).where(AIGeneration.conversation_id == conversation_id))
        db.execute(delete(ScheduleSlot).where(ScheduleSlot.slot_id == slot_id))
        db.execute(delete(RetrievalRun).where(RetrievalRun.operator_id == operator_id))
        db.commit()
    # 007/BS-4: a completed-booking test (or any future test reaching
    # GUIDED_BOOKING_COMPLETE) writes an append-only audit_events row
    # referencing this conversation_id (Constitution Article IX — a DB
    # trigger rejects deleting audit_events, so the conversation can never
    # be hard-deleted afterward either). This attempt is a separate
    # transaction from the block above specifically so a failure here
    # cannot roll back the legitimate deletes that already succeeded —
    # matches test_booking_script_flow.py's own already-established
    # "leave harmless synthetic test residue" precedent for the same
    # constraint.
    with session_factory() as db:
        try:
            db.execute(delete(Conversation).where(Conversation.id == conversation_id))
            db.commit()
        except IntegrityError:
            db.rollback()




def _send_operator_message(db, conversation_id, generation_id, operator_id, body: str) -> None:
    db.add(Message(conversation_id=conversation_id, author_type="OPERATOR", operator_id=operator_id, body=body, source_generation_id=generation_id))
    db.commit()


def _send_customer_message(db, conversation_id, body: str) -> None:
    db.add(Message(conversation_id=conversation_id, author_type="CUSTOMER", body=body))
    db.commit()


def _add_generation(conversation_id, operator_id, trigger: str, *, send: bool = False, body: str | None = None) -> UUID:
    """A later GB-step generation (own transaction, so its created_at is
    strictly after the fixture's offer generation). `send=True` also
    delivers it as an OPERATOR message. Removed by the fixture teardown."""
    with get_session_factory()() as db:
        run = RetrievalRun(operator_id=operator_id, purpose="N2_DRAFT", query_text=f"t005-gb-{trigger}", embedding_model="smoke", top_k=1, status="COMPLETED")
        db.add(run)
        db.flush()
        generation = AIGeneration(
            conversation_id=conversation_id, retrieval_run_id=run.id, operator_id=operator_id, status="ANSWER",
            draft_text=body or trigger, provider="guided-booking", model="not-applicable", prompt_version="not-applicable",
            trigger=trigger, dynamic_pattern_used=True,
        )
        db.add(generation)
        db.commit()
        generation_id = generation.id
        if send:
            _send_operator_message(db, conversation_id, generation_id, operator_id, body or trigger)
    return generation_id


def _send_cpf_request(conversation_id, generation_id, operator_id) -> None:
    """D-045: the offer-resolution generation itself is the CPF request."""
    with get_session_factory()() as db:
        _send_operator_message(db, conversation_id, generation_id, operator_id, "Para continuar o agendamento, informe seu CPF...")


def _confirm_cpf(conversation_id, generation_id, operator_id) -> UUID:
    """D-045: sends the offer set's CPF request, then the
    `GUIDED_CPF_CONFIRMED` (numbered offers) that slot choice now requires."""
    _send_cpf_request(conversation_id, generation_id, operator_id)
    return _add_generation(conversation_id, operator_id, "GUIDED_CPF_CONFIRMED", send=True, body="CPF confirmado. Escolha um dos horários...")


def _reload(db, conversation_id) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    assert conversation is not None
    return conversation


class TestLatestUnconfirmedOfferGenerationId:
    def test_returns_the_generation_id_when_offers_are_pending(self, conversation_with_generation) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        with get_session_factory()() as db:
            assert latest_unconfirmed_offer_generation_id(db, _reload(db, conversation_id)) == generation_id

    def test_returns_none_once_booking_script_has_taken_over(self, conversation_with_generation) -> None:
        conversation_id, _generation_id, _descriptions = conversation_with_generation
        session_factory = get_session_factory()
        with session_factory() as db:
            _reload(db, conversation_id).booking_script_step = "AWAITING_CPF"
            db.commit()
        with session_factory() as db:
            assert latest_unconfirmed_offer_generation_id(db, _reload(db, conversation_id)) is None

    @pytest.mark.parametrize("terminal_trigger", ["GUIDED_BOOKING_COMPLETE", "GUIDED_BOOKING_CANCELLED"])
    def test_returns_none_once_the_flow_has_finished(self, conversation_with_generation, operator_id, terminal_trigger: str) -> None:
        """Bug found 2026-08-19 (D-034): a finished flow must stop being "the
        pending offer set". D-045 adds the cancelled terminal state."""
        conversation_id, generation_id, descriptions = conversation_with_generation
        _confirm_cpf(conversation_id, generation_id, operator_id)
        _add_generation(conversation_id, operator_id, terminal_trigger)
        with get_session_factory()() as db:
            conversation = _reload(db, conversation_id)
            assert latest_unconfirmed_offer_generation_id(db, conversation) is None
            assert interpret_slot_choice(db, PROVIDER, conversation, descriptions[1]) is None

    def test_returns_none_once_booking_script_alone_completed_the_booking(self, conversation_with_generation, operator_id) -> None:
        """D-043: any completed `AppointmentBooking` row for this
        conversation, whatever its `source`, also excludes the offer set."""
        conversation_id, generation_id, descriptions = conversation_with_generation
        _confirm_cpf(conversation_id, generation_id, operator_id)
        session_factory = get_session_factory()
        with session_factory() as db:
            booking = AppointmentBooking(conversation_id=conversation_id, source="booking_script", specialty_id=_SPECIALTY_ID)
            db.add(booking)
            db.commit()
            booking_id = booking.booking_id
        try:
            with session_factory() as db:
                conversation = _reload(db, conversation_id)
                assert latest_unconfirmed_offer_generation_id(db, conversation) is None
                assert interpret_slot_choice(db, PROVIDER, conversation, descriptions[1]) is None
        finally:
            with session_factory() as db:
                db.execute(delete(AppointmentBooking).where(AppointmentBooking.booking_id == booking_id))
                db.commit()

    @pytest.mark.parametrize("later_trigger", ["GUIDED_CPF_REQUEST", "GUIDED_CPF_CONFIRMED", "GUIDED_SLOT_SELECTION", "GUIDED_SLOT_RESELECTION"])
    def test_still_pending_for_every_non_terminal_gb_trigger(self, conversation_with_generation, operator_id, later_trigger: str) -> None:
        """D-035 (revised): only the *latest* GB trigger being terminal
        excludes — every in-progress state stays pending."""
        conversation_id, generation_id, _descriptions = conversation_with_generation
        _add_generation(conversation_id, operator_id, later_trigger)
        with get_session_factory()() as db:
            assert latest_unconfirmed_offer_generation_id(db, _reload(db, conversation_id)) == generation_id

    def test_a_later_voltar_keeps_the_set_matchable(self, conversation_with_generation, operator_id) -> None:
        """Slot chosen, then "voltar" from the payment step: the offer set
        must still be matchable for a fresh choice."""
        conversation_id, generation_id, descriptions = conversation_with_generation
        _confirm_cpf(conversation_id, generation_id, operator_id)
        _add_generation(conversation_id, operator_id, "GUIDED_SLOT_SELECTION", send=True)
        _add_generation(conversation_id, operator_id, "GUIDED_SLOT_RESELECTION", send=True)
        with get_session_factory()() as db:
            conversation = _reload(db, conversation_id)
            assert latest_unconfirmed_offer_generation_id(db, conversation) == generation_id
            assert interpret_slot_choice(db, PROVIDER, conversation, descriptions[1]) is not None


class TestInterpretSlotChoice:
    def test_refused_before_the_cpf_was_confirmed(self, conversation_with_generation, operator_id) -> None:
        """D-045: the whole point of the reorder — offers that were never
        shown (CPF not yet confirmed) can't be chosen, by text or ordinal."""
        conversation_id, generation_id, descriptions = conversation_with_generation
        _send_cpf_request(conversation_id, generation_id, operator_id)
        with get_session_factory()() as db:
            conversation = _reload(db, conversation_id)
            assert interpret_slot_choice(db, PROVIDER, conversation, descriptions[1]) is None
            assert interpret_slot_choice(db, PROVIDER, conversation, "2") is None

    def test_an_unsent_cpf_confirmation_does_not_count(self, conversation_with_generation, operator_id) -> None:
        conversation_id, _generation_id, descriptions = conversation_with_generation
        _add_generation(conversation_id, operator_id, "GUIDED_CPF_CONFIRMED", send=False)
        with get_session_factory()() as db:
            assert interpret_slot_choice(db, PROVIDER, _reload(db, conversation_id), descriptions[1]) is None

    def test_a_newer_unsent_offer_draft_does_not_hijack_the_sent_set(self, conversation_with_generation, operator_id) -> None:
        """D-045: GB answers only the offer set the customer was actually
        sent. A later offer draft the operator never sent must not become
        "the" set and block (or redirect) the customer's slot choice."""
        conversation_id, generation_id, descriptions = conversation_with_generation
        _confirm_cpf(conversation_id, generation_id, operator_id)
        newer_id = _add_generation(conversation_id, operator_id, "MANUAL_DRAFT")
        with get_session_factory()() as db:
            slot_id = db.scalar(select(AppointmentOfferPresentation.slot_id).where(AppointmentOfferPresentation.ai_generation_id == generation_id).limit(1))
            [vector] = PROVIDER.embed(["Endocrinologia com Dra. Zoe, sexta-feira 30/08 às 11:00"])
            db.add(AppointmentOfferPresentation(ai_generation_id=newer_id, slot_id=slot_id, display_order=1, description="Endocrinologia com Dra. Zoe, sexta-feira 30/08 às 11:00", embedding=vector))
            db.commit()
        try:
            with get_session_factory()() as db:
                offer = interpret_slot_choice(db, PROVIDER, _reload(db, conversation_id), "primeira opção")
            assert offer is not None
            assert offer.ai_generation_id == generation_id
            assert offer.description == descriptions[0]
        finally:
            with get_session_factory()() as db:
                db.execute(delete(AppointmentOfferPresentation).where(AppointmentOfferPresentation.ai_generation_id == newer_id))
                db.commit()

    def test_exact_text_match_returns_that_offer(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, descriptions = conversation_with_generation
        _confirm_cpf(conversation_id, generation_id, operator_id)
        with get_session_factory()() as db:
            offer = interpret_slot_choice(db, PROVIDER, _reload(db, conversation_id), descriptions[1])
        assert offer is not None
        assert offer.description == descriptions[1]

    @pytest.mark.parametrize("text,expected_order", [("segunda opção", 2), ("a segunda", 2), ("2", 2), ("primeira", 1), ("1", 1), ("quero a primeira opção por favor", 1)])
    def test_ordinal_reference_matches_by_position_not_embedding(self, conversation_with_generation, operator_id, text: str, expected_order: int) -> None:
        """D-033: positional parsing, not embedding similarity."""
        conversation_id, generation_id, descriptions = conversation_with_generation
        _confirm_cpf(conversation_id, generation_id, operator_id)
        with get_session_factory()() as db:
            offer = interpret_slot_choice(db, PROVIDER, _reload(db, conversation_id), text)
        assert offer is not None
        assert offer.display_order == expected_order
        assert offer.description == descriptions[expected_order - 1]

    @pytest.mark.parametrize(
        "text",
        [
            "Quero agendar uma primeira consulta",
            "Quero saber o que preciso levar para a minha primeira consulta",
            "quarta-feira de manhã",
        ],
    )
    def test_ordinal_words_embedded_in_an_unrelated_sentence_do_not_false_match(self, conversation_with_generation, operator_id, text: str) -> None:
        """D-043: ordinary Portuguese ordinal words in a longer sentence are
        not a slot choice."""
        conversation_id, generation_id, _descriptions = conversation_with_generation
        _confirm_cpf(conversation_id, generation_id, operator_id)
        with get_session_factory()() as db:
            assert interpret_slot_choice(db, PROVIDER, _reload(db, conversation_id), text) is None

    def test_ordinal_out_of_range_falls_through_to_embedding_not_error(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        _confirm_cpf(conversation_id, generation_id, operator_id)
        with get_session_factory()() as db:
            interpret_slot_choice(db, PROVIDER, _reload(db, conversation_id), "quarta opção")  # only 2 offers; no exception

    def test_no_pending_offers_returns_none(self, operator_id) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            conversation = Conversation(anonymous_token_digest=uuid4().hex, initial_mode="N2", effective_mode="N2")
            db.add(conversation)
            db.commit()
            conversation_id = conversation.id
        try:
            with session_factory() as db:
                assert interpret_slot_choice(db, PROVIDER, _reload(db, conversation_id), "qualquer coisa") is None
        finally:
            with session_factory() as db:
                db.execute(delete(Conversation).where(Conversation.id == conversation_id))
                db.commit()


class TestInterpretCpfReply:
    """D-045: the CPF step is now the first one — reached by sending the
    offer-resolution generation itself (its text is the CPF request)."""

    def test_none_when_no_cpf_request_was_sent(self, conversation_with_generation) -> None:
        conversation_id, _generation_id, _descriptions = conversation_with_generation
        with get_session_factory()() as db:
            assert interpret_cpf_reply(db, _reload(db, conversation_id), "123.456.789-10") is None

    def test_invalid_cpf_reasks_on_the_cpf_request_trigger(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        _send_cpf_request(conversation_id, generation_id, operator_id)
        with get_session_factory()() as db:
            _send_customer_message(db, conversation_id, "Ah 123456a8910")
        with get_session_factory()() as db:
            result = interpret_cpf_reply(db, _reload(db, conversation_id), "Ah 123456a8910")
        assert result == ("CPF inválido. Informe um número válido de 11 dígitos.\n\nDigite Cancelar para desistir do agendamento.", "GUIDED_CPF_REQUEST")

    def test_valid_cpf_shows_the_numbered_offers(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, descriptions = conversation_with_generation
        _send_cpf_request(conversation_id, generation_id, operator_id)
        with get_session_factory()() as db:
            _send_customer_message(db, conversation_id, "tabom 123.456..789.10")
        with get_session_factory()() as db:
            result = interpret_cpf_reply(db, _reload(db, conversation_id), "tabom 123.456..789.10")
        assert result is not None
        text, next_trigger = result
        assert next_trigger == "GUIDED_CPF_CONFIRMED"
        assert text.startswith("CPF 123.456.789-10 confirmado.\n\nEscolha um dos horários disponíveis:\n\n1. ")
        assert f"1. {descriptions[0]} — " in text
        assert f"2. {descriptions[1]} — " in text
        assert text.endswith("Responda com o número da opção desejada.")
        assert "O valor foi pago" not in text

    def test_valid_cpf_after_an_invalid_retry(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        _send_cpf_request(conversation_id, generation_id, operator_id)
        _add_generation(conversation_id, operator_id, "GUIDED_CPF_REQUEST", send=True)
        with get_session_factory()() as db:
            _send_customer_message(db, conversation_id, "12345678910")
        with get_session_factory()() as db:
            result = interpret_cpf_reply(db, _reload(db, conversation_id), "12345678910")
        assert result is not None
        assert result[1] == "GUIDED_CPF_CONFIRMED"

    @pytest.mark.parametrize("text", ["Voltar", "voltar", "Cancelar", "cancela por favor", "outro horário"])
    def test_step_back_phrase_cancels_the_flow(self, conversation_with_generation, operator_id, text: str) -> None:
        """D-045: no earlier step exists before the CPF — "cancelar"/"voltar"
        end the flow, and never produce "CPF inválido"."""
        conversation_id, generation_id, _descriptions = conversation_with_generation
        _send_cpf_request(conversation_id, generation_id, operator_id)
        with get_session_factory()() as db:
            _send_customer_message(db, conversation_id, text)
        with get_session_factory()() as db:
            result = interpret_cpf_reply(db, _reload(db, conversation_id), text)
        assert result == (GB_CANCELLED_TEXT, "GUIDED_BOOKING_CANCELLED")

    def test_full_order_cpf_then_offers_then_slot_choice(self, conversation_with_generation, operator_id) -> None:
        """D-045 end-to-end at the interpretation layer: CPF request → valid
        CPF → numbered offers sent → an ordinal reply is a slot choice, not
        a CPF."""
        conversation_id, generation_id, descriptions = conversation_with_generation
        _send_cpf_request(conversation_id, generation_id, operator_id)
        with get_session_factory()() as db:
            _send_customer_message(db, conversation_id, "12345678910")
        with get_session_factory()() as db:
            result = interpret_cpf_reply(db, _reload(db, conversation_id), "12345678910")
        assert result is not None
        _add_generation(conversation_id, operator_id, result[1], send=True, body=result[0])
        with get_session_factory()() as db:
            _send_customer_message(db, conversation_id, "primeira opção")
        with get_session_factory()() as db:
            conversation = _reload(db, conversation_id)
            assert interpret_cpf_reply(db, conversation, "primeira opção") is None
            assert interpret_payment_reply(db, conversation, "primeira opção") is None
            offer = interpret_slot_choice(db, PROVIDER, conversation, "primeira opção")
        assert offer is not None
        assert offer.description == descriptions[0]


class TestInterpretPaymentReply:
    """D-045: the payment question now follows the slot choice
    (`GUIDED_SLOT_SELECTION`)."""

    def test_none_when_no_payment_question_was_sent(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        _send_cpf_request(conversation_id, generation_id, operator_id)
        with get_session_factory()() as db:
            _send_customer_message(db, conversation_id, "sim")
        with get_session_factory()() as db:
            assert interpret_payment_reply(db, _reload(db, conversation_id), "sim") is None

    def _ask_payment(self, conversation_id, generation_id, operator_id) -> None:
        _confirm_cpf(conversation_id, generation_id, operator_id)
        _add_generation(conversation_id, operator_id, "GUIDED_SLOT_SELECTION", send=True, body="Entendi que você escolheu... O valor foi pago?")

    def test_affirmative_completes_the_booking(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        self._ask_payment(conversation_id, generation_id, operator_id)
        with get_session_factory()() as db:
            _send_customer_message(db, conversation_id, "tabom simm paguei")
        with get_session_factory()() as db:
            result = interpret_payment_reply(db, _reload(db, conversation_id), "tabom simm paguei")
        assert result == ("Verificando pagamento. Pagamento verificado. Agendamento realizado com sucesso. Há algo mais que posso ajudar?", "GUIDED_BOOKING_COMPLETE")

    def test_affirmative_records_an_appointment_booking_sourced_from_the_chosen_offer(self, conversation_with_generation, operator_id) -> None:
        """007/BS-2: slot choice stages the offer; the affirmative payment
        reply records the booking from it."""
        conversation_id, generation_id, descriptions = conversation_with_generation
        session_factory = get_session_factory()
        _confirm_cpf(conversation_id, generation_id, operator_id)
        with session_factory() as db:
            offer = interpret_slot_choice(db, PROVIDER, _reload(db, conversation_id), descriptions[1])
            assert offer is not None
            db.commit()
        _add_generation(conversation_id, operator_id, "GUIDED_SLOT_SELECTION", send=True)
        with session_factory() as db:
            _send_customer_message(db, conversation_id, "sim, paguei")
        try:
            with session_factory() as db:
                conversation = _reload(db, conversation_id)
                assert conversation.guided_booking_selected_offer_id == offer.id
                assert interpret_payment_reply(db, conversation, "sim, paguei") is not None
                db.commit()
            with session_factory() as db:
                assert _reload(db, conversation_id).guided_booking_selected_offer_id is None, "must be cleared after being consumed"
                booking = db.scalar(select(AppointmentBooking).where(AppointmentBooking.conversation_id == conversation_id))
                assert booking is not None
                assert booking.source == "guided_booking"
                assert booking.specialty_id == UUID(_SPECIALTY_ID)
                assert booking.professional_id == UUID(_PROFESSIONAL_ID)
                assert booking.unit_id == UUID(_UNIT_ID)
                assert booking.slot_starts_at is not None
        finally:
            with session_factory() as db:
                db.execute(delete(AppointmentBooking).where(AppointmentBooking.conversation_id == conversation_id))
                db.commit()

    def test_negative_reasks_staying_on_slot_selection_trigger(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        self._ask_payment(conversation_id, generation_id, operator_id)
        with get_session_factory()() as db:
            _send_customer_message(db, conversation_id, "Então, não paguei")
        with get_session_factory()() as db:
            result = interpret_payment_reply(db, _reload(db, conversation_id), "Então, não paguei")
        assert result == ("O valor foi pago? Responda sim ou não.\n\nDigite Voltar para escolher outro horário.", "GUIDED_SLOT_SELECTION")

    @pytest.mark.parametrize("text", ["Voltar", "voltar", "Cancelar", "cancela por favor", "quero alterar horário", "mudar o horário", "trocar horário", "outro horário"])
    def test_step_back_phrase_re_presents_the_original_offers(self, conversation_with_generation, operator_id, text: str) -> None:
        """D-035: from the payment step, "voltar" re-presents the same offers."""
        conversation_id, generation_id, descriptions = conversation_with_generation
        self._ask_payment(conversation_id, generation_id, operator_id)
        with get_session_factory()() as db:
            _send_customer_message(db, conversation_id, text)
        with get_session_factory()() as db:
            result = interpret_payment_reply(db, _reload(db, conversation_id), text)
        assert result is not None
        response_text, next_trigger = result
        assert next_trigger == "GUIDED_SLOT_RESELECTION"
        assert descriptions[0] in response_text
        assert descriptions[1] in response_text


class TestAdvanceGuidedBooking:
    """The message-creation-time orchestrator — the only place a raw CPF/
    payment reply is ever read (D-033)."""

    def test_stages_the_offers_on_valid_cpf(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, descriptions = conversation_with_generation
        _send_cpf_request(conversation_id, generation_id, operator_id)
        with get_session_factory()() as db:
            _send_customer_message(db, conversation_id, "tabom 123.456..789.10")
        with get_session_factory()() as db:
            advance_guided_booking(db, _reload(db, conversation_id), "tabom 123.456..789.10")
            db.commit()
        with get_session_factory()() as db:
            conversation = _reload(db, conversation_id)
            assert conversation.guided_booking_pending_text is not None
            assert conversation.guided_booking_pending_text.startswith("CPF 123.456.789-10 confirmado.\n\nEscolha um dos horários disponíveis:")
            assert descriptions[0] in conversation.guided_booking_pending_text
            assert conversation.guided_booking_pending_trigger == "GUIDED_CPF_CONFIRMED"

    def test_no_op_once_booking_script_has_taken_over(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        _send_cpf_request(conversation_id, generation_id, operator_id)
        with get_session_factory()() as db:
            _reload(db, conversation_id).booking_script_step = "AWAITING_CPF"
            db.commit()
        with get_session_factory()() as db:
            _send_customer_message(db, conversation_id, "123.456.789-10")
        with get_session_factory()() as db:
            advance_guided_booking(db, _reload(db, conversation_id), "123.456.789-10")
            db.commit()
        with get_session_factory()() as db:
            assert _reload(db, conversation_id).guided_booking_pending_text is None


class TestRedaction:
    """D-033, moved by D-045: the reply to a CPF request (now the first
    step) is redacted; slot-choice and payment replies are kept verbatim."""

    def test_reply_to_the_offer_cpf_request_is_redacted(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        _send_cpf_request(conversation_id, generation_id, operator_id)
        with get_session_factory()() as db:
            conversation = _reload(db, conversation_id)
            assert pending_redaction_step(db, conversation) == "AWAITING_CPF"
            assert persisted_customer_body(db, conversation, "123.456.789-10") == GB_CPF_INPUT_REDACTION

    def test_reply_to_the_invalid_cpf_retry_is_redacted(self, conversation_with_generation, operator_id) -> None:
        conversation_id, _generation_id, _descriptions = conversation_with_generation
        _add_generation(conversation_id, operator_id, "GUIDED_CPF_REQUEST", send=True)
        with get_session_factory()() as db:
            assert pending_redaction_step(db, _reload(db, conversation_id)) == "AWAITING_CPF"

    @pytest.mark.parametrize("trigger", ["GUIDED_CPF_CONFIRMED", "GUIDED_SLOT_SELECTION", "GUIDED_SLOT_RESELECTION", "GUIDED_BOOKING_CANCELLED"])
    def test_later_step_replies_are_kept_verbatim(self, conversation_with_generation, operator_id, trigger: str) -> None:
        conversation_id, _generation_id, _descriptions = conversation_with_generation
        _add_generation(conversation_id, operator_id, trigger, send=True)
        with get_session_factory()() as db:
            conversation = _reload(db, conversation_id)
            assert pending_redaction_step(db, conversation) is None
            assert persisted_customer_body(db, conversation, "sim") == "sim"

    def test_no_redaction_outside_gb_steps(self, conversation_with_generation) -> None:
        conversation_id, _generation_id, _descriptions = conversation_with_generation
        with get_session_factory()() as db:
            conversation = _reload(db, conversation_id)
            assert pending_redaction_step(db, conversation) is None
            assert persisted_customer_body(db, conversation, "qualquer coisa") == "qualquer coisa"
