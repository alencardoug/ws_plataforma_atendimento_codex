"""005/GB, tasks.md T034/T041/T054: real-database integration tests for
scheduling/guided_booking.py's GB-1..GB-5 mechanics. Uses
DeterministicTestEmbeddingProvider (hash-based, not semantic — suitable
only for exact-match/no-match structural assertions here; genuine
paraphrase-recognition quality is verified separately by
smoke_v5_guided_booking.py against the real provider, matching this
project's existing unit-vs-smoke testing split). specs/005-dynamic-pricing-
and-guided-booking/plan.md §7."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete

from customer_care.ai.router import GB4_AFFIRMATIVE_TEXT, GB4_REASK_TEXT
from customer_care.auth.security import hash_password
from customer_care.booking_script.parsing import BOOKING_INTENT_KEYWORDS
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
    AFFIRMATIVE_REFERENCE_PHRASES,
    NEGATIVE_REFERENCE_PHRASES,
    interpret_confirmation_intent,
    interpret_slot_choice,
    latest_unconfirmed_offer_generation_id,
    preceding_confirmation_question_generation_id,
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


class TestInterpretConfirmationIntent:
    def test_exact_affirmative_reference_phrase_classifies_true(self) -> None:
        assert interpret_confirmation_intent(PROVIDER, AFFIRMATIVE_REFERENCE_PHRASES[0]) is True

    def test_exact_negative_reference_phrase_classifies_false(self) -> None:
        assert interpret_confirmation_intent(PROVIDER, NEGATIVE_REFERENCE_PHRASES[0]) is False

    def test_unrelated_text_is_ambiguous_under_the_hash_provider(self) -> None:
        # DeterministicTestEmbeddingProvider is hash-based, not semantic —
        # an unrelated string is not expected to clear either group's
        # threshold, which is exactly the "re-ask" branch this exercises.
        assert interpret_confirmation_intent(PROVIDER, "isso é um texto completamente não relacionado sobre outra coisa qualquer") is None


class TestPrecedingConfirmationQuestionGenerationId:
    def test_none_when_no_operator_message_exists(self, conversation_with_generation) -> None:
        conversation_id, _generation_id, _descriptions = conversation_with_generation
        with get_session_factory()() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            assert preceding_confirmation_question_generation_id(db, conversation) is None

    def test_true_once_a_guided_slot_selection_message_was_sent_and_replied_to(self, conversation_with_generation, operator_id) -> None:
        conversation_id, generation_id, _descriptions = conversation_with_generation
        session_factory = get_session_factory()
        with session_factory() as db:
            generation = db.get(AIGeneration, generation_id)
            assert generation is not None
            generation.trigger = "GUIDED_SLOT_SELECTION"
            operator_message = Message(conversation_id=conversation_id, author_type="OPERATOR", operator_id=operator_id, body="Entendi que você escolheu...", source_generation_id=generation_id)
            db.add(operator_message)
            db.commit()
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            # No customer reply yet — must not trigger.
            assert preceding_confirmation_question_generation_id(db, conversation) is None
        with session_factory() as db:
            db.add(Message(conversation_id=conversation_id, author_type="CUSTOMER", body="sim"))
            db.commit()
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation is not None
            assert preceding_confirmation_question_generation_id(db, conversation) == generation_id


class TestGB5KeywordOverlapGuard:
    """spec.md GB-5/§9 item 2: GB-4's fixed acknowledgement/re-ask text must
    never itself contain a phrase that would independently satisfy AA-10's
    detect_booking_intent() — the customer must still say something real,
    this feature never puts trigger words in the operator's mouth."""

    def test_affirmative_template_does_not_overlap_booking_intent_keywords(self) -> None:
        lowered = GB4_AFFIRMATIVE_TEXT.lower()
        for keyword in BOOKING_INTENT_KEYWORDS:
            assert keyword not in lowered, f"{keyword!r} unexpectedly present in GB4_AFFIRMATIVE_TEXT"

    def test_reask_template_does_not_overlap_booking_intent_keywords(self) -> None:
        lowered = GB4_REASK_TEXT.lower()
        for keyword in BOOKING_INTENT_KEYWORDS:
            assert keyword not in lowered, f"{keyword!r} unexpectedly present in GB4_REASK_TEXT"

    def test_reask_is_worded_differently_from_the_gb2_confirmation_question(self) -> None:
        assert GB4_REASK_TEXT != "Deseja que eu confirme o agendamento?"
