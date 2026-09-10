"""012, tasks.md T16: real-database integration tests for the Operator
Booking-Offer action (OB). specs/012-…/spec.md §6, plan.md §4,
acceptance.md #6-#10.

Real retrieval + real embedding calls run inside
generate_booking_offer_draft() (same real-provider discipline as
test_governed_autonomy.py's unclaimed-path test). The resolver itself is
deterministic.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from customer_care.ai.router import generate_booking_offer_draft
from customer_care.auth.security import hash_password
from customer_care.bootstrap import create_app
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import (
    AIGeneration,
    AIGenerationSource,
    AppointmentOfferPresentation,
    Conversation,
    Message,
    MessageSelection,
    OperatorUser,
    PendingAutonomousSend,
    RetrievalHit,
    RetrievalRun,
    SystemSettings,
)
from customer_care.scheduling.guided_booking import interpret_slot_choice
from customer_care.knowledge.embeddings import DeterministicTestEmbeddingProvider


@pytest.fixture
def operator_id():
    factory = get_session_factory()
    with factory() as db:
        op = OperatorUser(email=f"t012-{uuid4().hex[:8]}@example.com", password_hash=hash_password("irrelevant"), display_name="T012 fixture")
        db.add(op)
        db.commit()
        oid = op.id
    yield oid
    with factory() as db:
        db.execute(delete(OperatorUser).where(OperatorUser.id == oid))
        db.commit()


def _make_conversation(db, *, status: str = "ACTIVE", effective_mode: str = "N2", customer_text: str = "quero agendar uma consulta") -> Conversation:
    conv = Conversation(anonymous_token_digest=uuid4().hex, initial_mode="N2", effective_mode=effective_mode, status=status)
    db.add(conv)
    db.flush()
    if customer_text:
        db.add(Message(conversation_id=conv.id, author_type="CUSTOMER", body=customer_text))
    db.commit()
    return conv


def _purge_conversation(conversation_id, operator_id) -> None:
    factory = get_session_factory()
    with factory() as db:
        gen_ids = list(db.scalars(select(AIGeneration.id).where(AIGeneration.conversation_id == conversation_id)))
        run_ids = list(db.scalars(select(AIGeneration.retrieval_run_id).where(AIGeneration.conversation_id == conversation_id)))
        for gid in gen_ids:
            db.execute(delete(AppointmentOfferPresentation).where(AppointmentOfferPresentation.ai_generation_id == gid))
            db.execute(delete(AIGenerationSource).where(AIGenerationSource.ai_generation_id == gid))
            db.execute(delete(MessageSelection).where(MessageSelection.ai_generation_id == gid))
            db.execute(delete(PendingAutonomousSend).where(PendingAutonomousSend.generation_id == gid))
        db.execute(delete(AIGeneration).where(AIGeneration.conversation_id == conversation_id))
        for rid in run_ids:
            if rid is not None:
                db.execute(delete(RetrievalHit).where(RetrievalHit.retrieval_run_id == rid))
                db.execute(delete(RetrievalRun).where(RetrievalRun.id == rid))
        db.execute(delete(RetrievalRun).where(RetrievalRun.conversation_id == conversation_id))
        db.execute(delete(Message).where(Message.conversation_id == conversation_id))
        db.commit()
    with factory() as db:
        try:
            db.execute(delete(Conversation).where(Conversation.id == conversation_id))
            db.commit()
        except Exception:
            db.rollback()


def test_offer_then_slot_choice_flow(operator_id) -> None:
    factory = get_session_factory()
    with factory() as db:
        conv = _make_conversation(db)
        conv_id = conv.id
    try:
        with factory() as db:
            conv = db.get(Conversation, conv_id)
            generation, evidence = generate_booking_offer_draft(db, operator_id, conv, "")
            gen_id = generation.id
            assert generation.trigger == "MANUAL_BOOKING_OFFER"
            assert generation.status == "ANSWER"
            assert generation.provider == "dynamic-pattern-resolver"
            assert generation.dynamic_pattern_used is True
            assert generation.draft_text.strip()
        with factory() as db:
            offers = list(db.scalars(select(AppointmentOfferPresentation).where(AppointmentOfferPresentation.ai_generation_id == gen_id).order_by(AppointmentOfferPresentation.display_order)))
            assert len(offers) >= 1
        # a subsequent ordinal reply resolves through the existing GB path
        with factory() as db:
            conv = db.get(Conversation, conv_id)
            picked = interpret_slot_choice(db, DeterministicTestEmbeddingProvider(), conv, "opção 1")
            assert picked is not None
            assert picked.display_order == 1
    finally:
        _purge_conversation(conv_id, operator_id)


def test_hint_narrows_to_named_specialty(operator_id) -> None:
    factory = get_session_factory()
    with factory() as db:
        conv = _make_conversation(db, customer_text="oi, preciso de ajuda")
        conv_id = conv.id
    try:
        with factory() as db:
            conv = db.get(Conversation, conv_id)
            generation, _ev = generate_booking_offer_draft(db, operator_id, conv, "consulta de mastologia")
            assert generation.status == "ANSWER"
            assert "Mastologia" in generation.draft_text
    finally:
        _purge_conversation(conv_id, operator_id)


def test_empty_agenda_abstains_without_a_customer_message(operator_id) -> None:
    factory = get_session_factory()
    with factory() as db:
        # "domingo" -> next Sunday, a day the simulated agenda never opens
        conv = _make_conversation(db, customer_text="tem horário no domingo?")
        conv_id = conv.id
    try:
        with factory() as db:
            conv = db.get(Conversation, conv_id)
            generation, _ev = generate_booking_offer_draft(db, operator_id, conv, "domingo")
            assert generation.status == "ABSTAIN"
            assert generation.abstention_reason == "DYNAMIC_DATA_UNAVAILABLE"
            assert generation.draft_text == ""
        with factory() as db:
            assert db.scalar(select(Message).where(Message.conversation_id == conv_id, Message.author_type == "OPERATOR")) is None
    finally:
        _purge_conversation(conv_id, operator_id)


def test_never_opens_an_autonomous_send_even_with_both_kill_switches_on(operator_id) -> None:
    factory = get_session_factory()
    with factory() as db:
        settings = db.get(SystemSettings, True)
        prev = (settings.autonomy_kill_switch_enabled, settings.n5_kill_switch_enabled, settings.autonomy_window_seconds)
        settings.autonomy_kill_switch_enabled = True
        settings.n5_kill_switch_enabled = True
        settings.autonomy_window_seconds = 0
        db.commit()
        conv = _make_conversation(db)
        conv_id = conv.id
    try:
        with factory() as db:
            conv = db.get(Conversation, conv_id)
            generation, _ev = generate_booking_offer_draft(db, operator_id, conv, "")
            gen_id = generation.id
        with factory() as db:
            assert db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.generation_id == gen_id)) is None
            assert db.scalar(select(Message).where(Message.conversation_id == conv_id, Message.author_type == "OPERATOR")) is None
    finally:
        _purge_conversation(conv_id, operator_id)
        with factory() as db:
            settings = db.get(SystemSettings, True)
            settings.autonomy_kill_switch_enabled, settings.n5_kill_switch_enabled, settings.autonomy_window_seconds = prev
            db.commit()


def test_rejects_non_active_or_non_n2_conversation(operator_id) -> None:
    factory = get_session_factory()
    with factory() as db:
        conv = _make_conversation(db, status="CLOSED")
        conv_id = conv.id
    try:
        with factory() as db:
            conv = db.get(Conversation, conv_id)
            with pytest.raises(Exception) as exc:
                generate_booking_offer_draft(db, operator_id, conv, "")
            assert "409" in str(exc.value) or "MODE_NOT_ALLOWED" in str(exc.value)
    finally:
        _purge_conversation(conv_id, operator_id)


def test_endpoint_requires_authentication() -> None:
    client = TestClient(create_app())
    resp = client.post(f"/api/v1/operator/conversations/{uuid4()}/booking-offer-draft", json={})
    assert resp.status_code in (401, 403)


def test_openapi_schema_exposes_the_new_path() -> None:
    schema = create_app().openapi()
    path = "/api/v1/operator/conversations/{conversation_id}/booking-offer-draft"
    assert path in schema["paths"], sorted(p for p in schema["paths"] if "booking" in p)
    op = schema["paths"][path]["post"]
    assert "201" in op["responses"]
    body_schema = op["requestBody"]["content"]["application/json"]["schema"]
    # BookingOfferDraftIn — a single optional free-text field
    assert "manual_search_text" in (body_schema.get("properties") or {}) or body_schema.get("$ref")
