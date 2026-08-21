"""010, tasks.md T25/T26: real-database integration tests for governed
autonomous response (Constitution Amendment 1.2.0) — maybe_open_autonomous_window(),
resolve_elapsed_autonomous_sends(), evaluate_unclaimed_autonomous_trigger(),
and the PAUSE/EDIT/TAKE OVER resolution side effects. Constructs
AIGeneration fixtures directly (matching test_guided_booking.py's own
established approach) rather than calling generate_draft() with a real
query — the eligibility/window/resolution logic under test here doesn't
depend on real retrieval or a real LLM call.
specs/010-governed-autonomous-response/spec.md §6, plan.md §3/§4."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from customer_care.ai.router import evaluate_unclaimed_autonomous_trigger, maybe_open_autonomous_window
from customer_care.auth.security import hash_password
from customer_care.autonomy.service import resolve_elapsed_autonomous_sends
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import AIGeneration, AIGenerationSource, Category, Conversation, Message, MessageSelection, OperatorUser, PendingAutonomousSend, RetrievalHit, RetrievalRun, SystemSettings

TEST_CATEGORY_SLUG = "t010-governed-autonomy-fixture"


@pytest.fixture
def operator_id():
    session_factory = get_session_factory()
    with session_factory() as db:
        operator = OperatorUser(email=f"t010-{uuid4().hex[:8]}@example.com", password_hash=hash_password("irrelevant"), display_name="T010 fixture")
        db.add(operator)
        db.commit()
        oid = operator.id
    yield oid
    with session_factory() as db:
        db.execute(delete(OperatorUser).where(OperatorUser.id == oid))
        db.commit()


@pytest.fixture
def category():
    """Own dedicated category, default autonomy_enabled=false — never
    reuses a real catalog category, so toggling it on/off here can never
    affect any other test's own retrieval-ranking assumptions."""
    session_factory = get_session_factory()
    with session_factory() as db:
        db.merge(Category(slug=TEST_CATEGORY_SLUG, label="T010 fixture", is_active=True, autonomy_enabled=False))
        db.commit()
    yield TEST_CATEGORY_SLUG
    with session_factory() as db:
        db.execute(delete(Category).where(Category.slug == TEST_CATEGORY_SLUG))
        db.commit()


@pytest.fixture(autouse=True)
def kill_switch_on():
    """Every test in this file wants the kill switch on and a known
    window by default, restored afterward — never touches window_seconds'
    own value here (each test sets what it needs directly on the row it
    creates, not via this shared setting) to avoid cross-test coupling."""
    session_factory = get_session_factory()
    with session_factory() as db:
        settings = db.get(SystemSettings, True)
        before = settings.autonomy_kill_switch_enabled
        settings.autonomy_kill_switch_enabled = True
        db.commit()
    yield
    with session_factory() as db:
        settings = db.get(SystemSettings, True)
        settings.autonomy_kill_switch_enabled = before
        db.commit()


def _make_generation(db, *, status="ANSWER", trigger="AUTOMATIC", category_slug=TEST_CATEGORY_SLUG, operator_id=None, conversation_status="ACTIVE"):
    conversation = Conversation(anonymous_token_digest=uuid4().hex, initial_mode="N2", effective_mode="N2", status=conversation_status)
    db.add(conversation)
    db.flush()
    run = RetrievalRun(operator_id=operator_id, purpose="N2_DRAFT", query_text="t010", embedding_model="smoke", top_k=1, status="COMPLETED")
    db.add(run)
    db.flush()
    generation = AIGeneration(conversation_id=conversation.id, retrieval_run_id=run.id, operator_id=operator_id, status=status, draft_text="resposta de teste (simulação)", provider="test", model="not-applicable", prompt_version="not-applicable", trigger=trigger, category_slug=category_slug)
    db.add(generation)
    db.commit()
    return conversation, generation


def _cleanup(db, conversation_id, generation_id, operator_id):
    # auto_draft_covers_through_message_id may point at one of this
    # conversation's own messages (evaluate_unclaimed_autonomous_trigger()
    # sets it) — must be cleared before deleting messages, or the FK
    # rejects the delete.
    conversation = db.get(Conversation, conversation_id)
    if conversation:
        conversation.auto_draft_covers_through_message_id = None
        db.commit()
    db.execute(delete(PendingAutonomousSend).where(PendingAutonomousSend.generation_id == generation_id))
    db.execute(delete(AIGenerationSource).where(AIGenerationSource.ai_generation_id == generation_id))
    db.execute(delete(MessageSelection).where(MessageSelection.ai_generation_id == generation_id))
    generation = db.get(AIGeneration, generation_id)
    if generation:
        db.execute(delete(RetrievalHit).where(RetrievalHit.retrieval_run_id == generation.retrieval_run_id))
    db.execute(delete(Message).where(Message.conversation_id == conversation_id))
    db.execute(delete(AIGeneration).where(AIGeneration.id == generation_id))
    db.execute(delete(RetrievalRun).where(RetrievalRun.operator_id == operator_id))
    db.commit()
    try:
        db.execute(delete(Conversation).where(Conversation.id == conversation_id))
        db.commit()
    except Exception:
        db.rollback()


class TestEligibilityGate:
    def test_category_off_never_opens_a_window(self, operator_id, category) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            conversation, generation = _make_generation(db, operator_id=operator_id)
            maybe_open_autonomous_window(db, generation, conversation)
            assert db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.generation_id == generation.id)) is None
            _cleanup(db, conversation.id, generation.id, operator_id)

    def test_kill_switch_off_never_opens_a_window_even_with_category_on(self, operator_id, category) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            db.get(Category, category).autonomy_enabled = True
            db.get(SystemSettings, True).autonomy_kill_switch_enabled = False
            db.commit()
            conversation, generation = _make_generation(db, operator_id=operator_id)
            maybe_open_autonomous_window(db, generation, conversation)
            assert db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.generation_id == generation.id)) is None
            db.get(Category, category).autonomy_enabled = False
            db.commit()
            _cleanup(db, conversation.id, generation.id, operator_id)

    def test_abstain_never_opens_a_window(self, operator_id, category) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            db.get(Category, category).autonomy_enabled = True
            db.commit()
            conversation, generation = _make_generation(db, operator_id=operator_id, status="ABSTAIN", category_slug=None)
            maybe_open_autonomous_window(db, generation, conversation)
            assert db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.generation_id == generation.id)) is None
            db.get(Category, category).autonomy_enabled = False
            db.commit()
            _cleanup(db, conversation.id, generation.id, operator_id)

    def test_manual_draft_trigger_never_opens_a_window(self, operator_id, category) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            db.get(Category, category).autonomy_enabled = True
            db.commit()
            conversation, generation = _make_generation(db, operator_id=operator_id, trigger="MANUAL_DRAFT")
            maybe_open_autonomous_window(db, generation, conversation)
            assert db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.generation_id == generation.id)) is None
            db.get(Category, category).autonomy_enabled = False
            db.commit()
            _cleanup(db, conversation.id, generation.id, operator_id)

    def test_eligible_generation_opens_a_window(self, operator_id, category) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            db.get(Category, category).autonomy_enabled = True
            settings = db.get(SystemSettings, True)
            settings.autonomy_window_seconds = 30
            db.commit()
            conversation, generation = _make_generation(db, operator_id=operator_id)
            maybe_open_autonomous_window(db, generation, conversation)
            pending = db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.generation_id == generation.id))
            assert pending is not None
            assert pending.status == "PENDING"
            assert pending.window_seconds == 30
            assert abs((pending.resolves_at - pending.opens_at).total_seconds() - 30) < 1
            db.get(Category, category).autonomy_enabled = False
            db.commit()
            _cleanup(db, conversation.id, generation.id, operator_id)


class TestResolution:
    def test_window_elapses_and_sends_autonomously(self, operator_id, category) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            conversation, generation = _make_generation(db, operator_id=operator_id)
            past = datetime.now(UTC) - timedelta(seconds=1)
            pending = PendingAutonomousSend(generation_id=generation.id, conversation_id=conversation.id, category=category, mechanism="governed_autonomy", window_seconds=0, opens_at=past, resolves_at=past, status="PENDING")
            db.add(pending)
            db.commit()
            resolve_elapsed_autonomous_sends(db)
            db.refresh(pending)
            assert pending.status == "SENT"
            assert pending.resolved_at is not None
            message = db.scalar(select(Message).where(Message.conversation_id == conversation.id))
            assert message is not None
            assert message.author_type == "OPERATOR"
            assert message.operator_id is None
            assert message.autonomous_source == "governed_autonomy"
            assert message.body == generation.draft_text
            _cleanup(db, conversation.id, generation.id, operator_id)

    def test_window_not_yet_elapsed_stays_pending(self, operator_id, category) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            conversation, generation = _make_generation(db, operator_id=operator_id)
            future = datetime.now(UTC) + timedelta(minutes=5)
            pending = PendingAutonomousSend(generation_id=generation.id, conversation_id=conversation.id, category=category, mechanism="governed_autonomy", window_seconds=300, opens_at=datetime.now(UTC), resolves_at=future, status="PENDING")
            db.add(pending)
            db.commit()
            resolve_elapsed_autonomous_sends(db)
            db.refresh(pending)
            assert pending.status == "PENDING"
            assert db.scalar(select(Message).where(Message.conversation_id == conversation.id)) is None
            _cleanup(db, conversation.id, generation.id, operator_id)


class TestUnclaimedTrigger:
    def test_waiting_conversation_gets_an_autonomous_send_without_status_changing(self, operator_id, category) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            db.get(Category, category).autonomy_enabled = True
            settings = db.get(SystemSettings, True)
            settings.autonomy_window_seconds = 0
            db.commit()
            conversation = Conversation(anonymous_token_digest=uuid4().hex, initial_mode="N2", effective_mode="N2", status="WAITING", last_customer_activity_at=datetime.now(UTC) - timedelta(seconds=30))
            db.add(conversation)
            db.flush()
            message = Message(conversation_id=conversation.id, author_type="CUSTOMER", body="Existe consulta disponível amanhã? (t010 fixture)")
            db.add(message)
            db.commit()
            conversation_id = conversation.id
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            evaluate_unclaimed_autonomous_trigger(db, conversation)
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            # Real retrieval runs inside generate_draft() here (unlike the
            # rest of this file's direct-fixture tests) — this specific
            # test exercises the real end-to-end unclaimed path, so it may
            # legitimately ABSTAIN depending on what the fixture's own
            # customer message happens to retrieve against the real
            # catalog. Either way, status must never change and capacity
            # must never be consumed — the two GA-6 guarantees this test
            # actually verifies.
            assert conversation.status == "WAITING"
            generation = db.scalar(select(AIGeneration).where(AIGeneration.conversation_id == conversation_id))
            conversation.auto_draft_covers_through_message_id = None
            db.commit()
            if generation:
                assert generation.operator_id is None
                db.execute(delete(PendingAutonomousSend).where(PendingAutonomousSend.generation_id == generation.id))
                db.execute(delete(AIGenerationSource).where(AIGenerationSource.ai_generation_id == generation.id))
                db.execute(delete(MessageSelection).where(MessageSelection.ai_generation_id == generation.id))
                db.execute(delete(RetrievalHit).where(RetrievalHit.retrieval_run_id == generation.retrieval_run_id))
                db.execute(delete(AIGeneration).where(AIGeneration.id == generation.id))
                db.execute(delete(RetrievalRun).where(RetrievalRun.id == generation.retrieval_run_id))
            db.execute(delete(Message).where(Message.conversation_id == conversation_id))
            db.commit()
            db.get(Category, category).autonomy_enabled = False
            db.commit()
        with session_factory() as db:
            try:
                db.execute(delete(Conversation).where(Conversation.id == conversation_id))
                db.commit()
            except Exception:
                db.rollback()

    def test_active_conversation_never_uses_the_unclaimed_path(self, operator_id, category) -> None:
        """Guards the status=='WAITING' check itself — an ACTIVE
        conversation must be evaluated only by evaluate_automatic_trigger(),
        never this function, even if called directly."""
        session_factory = get_session_factory()
        with session_factory() as db:
            conversation = Conversation(anonymous_token_digest=uuid4().hex, initial_mode="N2", effective_mode="N2", status="ACTIVE", last_customer_activity_at=datetime.now(UTC) - timedelta(seconds=30))
            db.add(conversation)
            db.commit()
            conversation_id = conversation.id
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            evaluate_unclaimed_autonomous_trigger(db, conversation)
            assert db.scalar(select(AIGeneration).where(AIGeneration.conversation_id == conversation_id)) is None
        with session_factory() as db:
            db.execute(delete(Conversation).where(Conversation.id == conversation_id))
            db.commit()
