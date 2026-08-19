"""T095: real-database integration tests for advance_booking_script()
(AA-10) — the full happy-path script verbatim, the invalid-CPF-then-valid
branch, the não-then-sim branch, the no-prior-availability guard, a fresh
restart after completion, autonomous_source/audit-event tagging on every
send, and confirmation that the raw CPF/payment answer are never
persisted anywhere. specs/004-dynamic-appointment-availability/spec.md
AA-10, acceptance.md §L/§M/§N."""

from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from customer_care.auth.security import hash_password
from customer_care.booking_script.service import (
    CPF_INPUT_REDACTION,
    PAYMENT_INPUT_REDACTION,
    advance_booking_script,
    persisted_customer_body,
)
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import (
    AIGeneration,
    AIGenerationSource,
    AuditEvent,
    Conversation,
    Message,
    OperatorUser,
    QAEntry,
    RetrievalHit,
    RetrievalRun,
)
from customer_care.audit.service import record_event

MASTOLOGIA_SPECIALTY_SLUG = "mastologia-oncologica"
MASTOLOGIA_PRICE_TEXT = "R$ 980,00 (simulação)"


def _customer_message(session: Session, conversation: Conversation, body: str) -> str:
    """Mirror the HTTP route: persist only the AA-10-safe body while
    returning the request-local raw input for deterministic parsing."""
    message = Message(
        conversation_id=conversation.id,
        author_type="CUSTOMER",
        body=persisted_customer_body(conversation.booking_script_step, body),
    )
    session.add(message)
    session.flush()
    return body


def _autonomous_bodies(session: Session, conversation_id) -> list[str]:
    rows = session.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.autonomous_source == "booking_script")
        .order_by(Message.created_at)
    ).all()
    return [row.body for row in rows]


@pytest.fixture
def conversation_with_resolved_availability():
    """A conversation with a real, resolved appointment_availability
    generation already on it — the precondition AA-10's trigger requires
    (`has_recent_resolved_availability`)."""
    session_factory = get_session_factory()
    suffix = uuid4().hex[:8]
    qa_id = f"t095-{suffix}"
    email = f"t095-{suffix}@example.com"
    with session_factory() as db:
        operator = OperatorUser(email=email, password_hash=hash_password("irrelevant"), display_name="T095 fixture")
        db.add(operator)
        qa = QAEntry(qa_id=qa_id, category="smoke-fixture", question="fixture", answer_markdown="fixture", dynamic_data_required=True, dynamic_resolver="appointment_availability", customer_citation_allowed=False)
        db.add(qa)
        conversation = Conversation(anonymous_token_digest=f"t095-{suffix}", initial_mode="N2", effective_mode="N2")
        db.add(conversation)
        db.flush()
        run = RetrievalRun(conversation_id=conversation.id, operator_id=operator.id, purpose="N2_MANUAL_SEARCH", query_text="fixture", embedding_model="fixture", top_k=1, status="COMPLETED")
        db.add(run)
        db.flush()
        hit = RetrievalHit(retrieval_run_id=run.id, matched_kind="ADMIN_QA", matched_qa_id=qa_id, rank=1, score=1.0)
        db.add(hit)
        db.flush()
        generation = AIGeneration(conversation_id=conversation.id, retrieval_run_id=run.id, operator_id=operator.id, status="ANSWER", draft_text="fixture slots", dynamic_pattern_used=True, provider="dynamic-pattern-resolver", model="not-applicable", prompt_version="not-applicable", trigger="MANUAL_EVIDENCE")
        db.add(generation)
        db.flush()
        db.add(AIGenerationSource(ai_generation_id=generation.id, retrieval_hit_id=hit.id, use_order=1))
        record_event(db, "ai.dynamic_pattern_resolved", "OPERATOR", actor_id=operator.id, conversation_id=conversation.id, payload={"ai_generation_id": str(generation.id), "specialty_slug": MASTOLOGIA_SPECIALTY_SLUG, "slot_count": 1})
        db.commit()
        conversation_id = conversation.id

    yield conversation_id

    # audit_events is append-only (Constitution Article IX) — a DB trigger
    # rejects any DELETE/UPDATE, and it FK-references conversation_id, so
    # the conversation (and everything else this fixture created) cannot
    # be hard-deleted either. Left behind as harmless synthetic test
    # residue, matching this project's established convention for smoke
    # fixtures (e.g. tests/smoke_n2.py's own dynamic-QA fixtures).


def test_full_happy_path_script_verbatim(conversation_with_resolved_availability) -> None:
    conversation_id = conversation_with_resolved_availability
    session_factory = get_session_factory()

    with session_factory() as db:
        conversation = db.get(Conversation, conversation_id)
        message = _customer_message(db, conversation, "Quero marcar essa consulta")
        advance_booking_script(db, conversation, message)
        db.commit()
        assert _autonomous_bodies(db, conversation_id) == [
            "Agendamento realizado",
            "Informe seu CPF - é uma simulação, informe qualquer número de 11 dígitos",
        ]
        assert conversation.booking_script_step == "AWAITING_CPF"

    with session_factory() as db:
        conversation = db.get(Conversation, conversation_id)
        message = _customer_message(db, conversation, "tabom 123.456..789.10")
        advance_booking_script(db, conversation, message)
        db.commit()
        bodies = _autonomous_bodies(db, conversation_id)
        assert bodies[2:] == [
            "CPF 123.456.789-10 confirmado",
            f"O valor da consulta é {MASTOLOGIA_PRICE_TEXT}",
            "O valor foi pago? Responda sim ou não",
        ]
        assert conversation.booking_script_step == "AWAITING_PAYMENT"

    with session_factory() as db:
        conversation = db.get(Conversation, conversation_id)
        message = _customer_message(db, conversation, "tabom simm paguei")
        advance_booking_script(db, conversation, message)
        db.commit()
        bodies = _autonomous_bodies(db, conversation_id)
        assert bodies[5:] == [
            "Verificando pagamento",
            "Pagamento verificado",
            "Agendamento realizado com sucesso. Há algo mais que posso ajudar?",
        ]
        assert conversation.booking_script_step is None


def test_invalid_cpf_then_valid_branch(conversation_with_resolved_availability) -> None:
    conversation_id = conversation_with_resolved_availability
    session_factory = get_session_factory()

    with session_factory() as db:
        conversation = db.get(Conversation, conversation_id)
        message = _customer_message(db, conversation, "Quero marcar essa consulta")
        advance_booking_script(db, conversation, message)
        db.commit()

    with session_factory() as db:
        conversation = db.get(Conversation, conversation_id)
        message = _customer_message(db, conversation, "Ah 123456a8910")
        advance_booking_script(db, conversation, message)
        db.commit()
        assert _autonomous_bodies(db, conversation_id)[-1] == "CPF inválido. Informe um número válido de 11 dígitos"
        assert conversation.booking_script_step == "AWAITING_CPF"  # unchanged, no retry limit

    with session_factory() as db:
        conversation = db.get(Conversation, conversation_id)
        message = _customer_message(db, conversation, "tabom 123.456..789.10")
        advance_booking_script(db, conversation, message)
        db.commit()
        assert "CPF 123.456.789-10 confirmado" in _autonomous_bodies(db, conversation_id)
        assert conversation.booking_script_step == "AWAITING_PAYMENT"


def test_nao_then_sim_branch_reasks_identical_question(conversation_with_resolved_availability) -> None:
    conversation_id = conversation_with_resolved_availability
    session_factory = get_session_factory()

    with session_factory() as db:
        conversation = db.get(Conversation, conversation_id)
        advance_booking_script(db, conversation, _customer_message(db, conversation, "Quero marcar essa consulta"))
        db.commit()
    with session_factory() as db:
        conversation = db.get(Conversation, conversation_id)
        advance_booking_script(db, conversation, _customer_message(db, conversation, "tabom 123.456..789.10"))
        db.commit()

    with session_factory() as db:
        conversation = db.get(Conversation, conversation_id)
        message = _customer_message(db, conversation, "Então, não paguei")
        advance_booking_script(db, conversation, message)
        db.commit()
        assert _autonomous_bodies(db, conversation_id)[-1] == "O valor foi pago? Responda sim ou não"
        assert conversation.booking_script_step == "AWAITING_PAYMENT"  # unchanged, no retry limit

    with session_factory() as db:
        conversation = db.get(Conversation, conversation_id)
        message = _customer_message(db, conversation, "tabom simm paguei")
        advance_booking_script(db, conversation, message)
        db.commit()
        assert _autonomous_bodies(db, conversation_id)[-1] == "Agendamento realizado com sucesso. Há algo mais que posso ajudar?"
        assert conversation.booking_script_step is None


def test_no_prior_resolved_availability_never_starts_script() -> None:
    session_factory = get_session_factory()
    with session_factory() as db:
        conversation = Conversation(anonymous_token_digest=f"t095-noavail-{uuid4().hex}", initial_mode="N2", effective_mode="N2")
        db.add(conversation)
        db.flush()
        message = _customer_message(db, conversation, "Quero marcar essa consulta")
        advance_booking_script(db, conversation, message)
        db.commit()
        conversation_id = conversation.id
        assert _autonomous_bodies(db, conversation_id) == []
        assert conversation.booking_script_step is None

    with session_factory() as db:
        db.execute(delete(Message).where(Message.conversation_id == conversation_id))
        db.execute(delete(Conversation).where(Conversation.id == conversation_id))
        db.commit()


def test_second_booking_intent_after_completed_flow_starts_fresh(conversation_with_resolved_availability) -> None:
    conversation_id = conversation_with_resolved_availability
    session_factory = get_session_factory()

    for body in ("Quero marcar essa consulta", "tabom 123.456..789.10", "tabom simm paguei"):
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            advance_booking_script(db, conversation, _customer_message(db, conversation, body))
            db.commit()

    with session_factory() as db:
        conversation = db.get(Conversation, conversation_id)
        assert conversation.booking_script_step is None
        before = len(_autonomous_bodies(db, conversation_id))
        message = _customer_message(db, conversation, "pode agendar de novo")
        advance_booking_script(db, conversation, message)
        db.commit()
        after = _autonomous_bodies(db, conversation_id)
        assert after[before:] == [
            "Agendamento realizado",
            "Informe seu CPF - é uma simulação, informe qualquer número de 11 dígitos",
        ]
        assert conversation.booking_script_step == "AWAITING_CPF"


def test_every_autonomous_send_is_tagged_and_audited(conversation_with_resolved_availability) -> None:
    conversation_id = conversation_with_resolved_availability
    session_factory = get_session_factory()

    with session_factory() as db:
        conversation = db.get(Conversation, conversation_id)
        advance_booking_script(db, conversation, _customer_message(db, conversation, "Quero marcar essa consulta"))
        db.commit()

    with session_factory() as db:
        messages = db.scalars(select(Message).where(Message.conversation_id == conversation_id, Message.author_type == "OPERATOR")).all()
        assert len(messages) == 2
        for message in messages:
            assert message.autonomous_source == "booking_script"

        events = db.scalars(select(AuditEvent).where(AuditEvent.event_type == "booking_script.autonomous_message_sent", AuditEvent.conversation_id == conversation_id)).all()
        assert len(events) == 2
        for event in events:
            assert event.actor_type == "SYSTEM"
            assert set(event.payload_json.keys()) == {"conversation_id", "message_id", "step"}
            assert event.payload_json["step"] == "START"


def test_raw_cpf_and_payment_answer_never_persisted(conversation_with_resolved_availability) -> None:
    conversation_id = conversation_with_resolved_availability
    session_factory = get_session_factory()

    for body in ("Quero marcar essa consulta", "Ah 123456a8910", "tabom 123.456..789.10", "Então, não paguei", "tabom simm paguei"):
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            advance_booking_script(db, conversation, _customer_message(db, conversation, body))
            db.commit()

    with session_factory() as db:
        conversation = db.get(Conversation, conversation_id)
        assert conversation.booking_script_step is None

        # The formatted CPF deliberately appears in the fixed "CPF ...
        # confirmado" output. The submitted strings themselves are never
        # durable: sensitive CUSTOMER rows contain only fixed disclosure
        # markers, and no audit payload contains the raw input.
        message_bodies = [row.body for row in db.scalars(select(Message).where(Message.conversation_id == conversation_id)).all()]
        assert CPF_INPUT_REDACTION in message_bodies
        assert PAYMENT_INPUT_REDACTION in message_bodies
        for raw_input in ("Ah 123456a8910", "tabom 123.456..789.10", "Então, não paguei", "tabom simm paguei"):
            assert raw_input not in message_bodies

        for event in db.scalars(select(AuditEvent).where(AuditEvent.conversation_id == conversation_id)).all():
            payload_text = str(event.payload_json)
            assert "123456a8910" not in payload_text
            assert "123.456..789.10" not in payload_text
            assert "não paguei" not in payload_text
            assert "simm paguei" not in payload_text
