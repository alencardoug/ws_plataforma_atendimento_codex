"""011, tasks.md T24: real-database integration tests for ungoverned
fictional-demo autonomy (Constitution Amendment 1.3.0, N5) —
maybe_open_autonomous_window()'s ungoverned branch,
generate_ungoverned_reply(), resolve_elapsed_autonomous_sends()'s
mechanism-aware autonomous_source, and automatic_trigger_idle_seconds.
Mirrors test_governed_autonomy.py's own fixture/cleanup discipline (a
dedicated fixture category, never a real catalog one) but does not
re-test PAUSE/EDIT/TAKE OVER at this level — those resolution paths are
mechanism-agnostic (never reference `.category`) and are covered by
smoke_v11_ungoverned_n5.py/v11.spec.ts instead, matching
test_governed_autonomy.py's own precedent (010 itself never unit-tested
them here either — acceptance.md outcomes 5/6).
specs/011-ungoverned-fictional-demo-autonomy-n5/spec.md §6, plan.md §4/§6."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from customer_care.ai.router import evaluate_unclaimed_autonomous_trigger, maybe_open_autonomous_window
from customer_care.auth.security import hash_password
from customer_care.autonomy.service import resolve_elapsed_autonomous_sends
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import AIGeneration, AIGenerationSource, Category, Conversation, Message, MessageSelection, OperatorUser, PendingAutonomousSend, RetrievalHit, RetrievalRun, SystemSettings

TEST_CATEGORY_SLUG = "t011-ungoverned-n5-fixture"


@pytest.fixture
def operator_id():
    session_factory = get_session_factory()
    with session_factory() as db:
        operator = OperatorUser(email=f"t011-{uuid4().hex[:8]}@example.com", password_hash=hash_password("irrelevant"), display_name="T011 fixture")
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
    reuses a real catalog category or test_governed_autonomy.py's own
    fixture slug."""
    session_factory = get_session_factory()
    with session_factory() as db:
        db.merge(Category(slug=TEST_CATEGORY_SLUG, label="T011 fixture", is_active=True, autonomy_enabled=False))
        db.commit()
    yield TEST_CATEGORY_SLUG
    with session_factory() as db:
        db.execute(delete(Category).where(Category.slug == TEST_CATEGORY_SLUG))
        db.commit()


@pytest.fixture(autouse=True)
def both_switches():
    """Every test in this file controls both switches explicitly on its
    own generation/category setup — this fixture only guarantees a known,
    restored-afterward starting point (both off), matching
    test_governed_autonomy.py's own kill_switch_on fixture precedent but
    for two independent switches."""
    session_factory = get_session_factory()
    with session_factory() as db:
        settings = db.get(SystemSettings, True)
        before_governed = settings.autonomy_kill_switch_enabled
        before_n5 = settings.n5_kill_switch_enabled
        before_idle = settings.automatic_trigger_idle_seconds
    yield
    with session_factory() as db:
        settings = db.get(SystemSettings, True)
        settings.autonomy_kill_switch_enabled = before_governed
        settings.n5_kill_switch_enabled = before_n5
        settings.automatic_trigger_idle_seconds = before_idle
        db.commit()


def _make_generation(db, *, status="ANSWER", trigger="AUTOMATIC", category_slug=TEST_CATEGORY_SLUG, operator_id=None, conversation_status="ACTIVE"):
    conversation = Conversation(anonymous_token_digest=uuid4().hex, initial_mode="N2", effective_mode="N2", status=conversation_status)
    db.add(conversation)
    db.flush()
    run = RetrievalRun(operator_id=operator_id, purpose="N2_DRAFT", query_text="t011", embedding_model="smoke", top_k=1, status="COMPLETED")
    db.add(run)
    db.flush()
    generation = AIGeneration(conversation_id=conversation.id, retrieval_run_id=run.id, operator_id=operator_id, status=status, draft_text="resposta de teste (simulação)", provider="test", model="not-applicable", prompt_version="not-applicable", trigger=trigger, category_slug=category_slug)
    db.add(generation)
    db.commit()
    return conversation, generation


# Real seeded chunk/parent-document pair, reused rather than duplicated —
# same pattern test_guided_booking.py's own _UNIT_ID/_SPECIALTY_ID uses.
_REAL_CHUNK_ID = "COLORRETAL-APOIO_EMOCIONAL-001-C01"
_REAL_PARENT_DOCUMENT_ID = "COLORRETAL-APOIO_EMOCIONAL-001"


def _make_clinical_shortcut_generation(db, *, score: float, operator_id=None, category_slug=None):
    """D-043-2: a full_parent_draft()-shaped generation — provider ==
    "clinical-parent-document", with one real RetrievalHit/AIGenerationSource
    pair carrying the given score, exactly the shape
    _clinical_top_evidence_score() reads."""
    conversation = Conversation(anonymous_token_digest=uuid4().hex, initial_mode="N2", effective_mode="N2")
    db.add(conversation)
    db.flush()
    run = RetrievalRun(operator_id=operator_id, purpose="N2_DRAFT", query_text="t011-clinical", embedding_model="smoke", top_k=1, status="COMPLETED")
    db.add(run)
    db.flush()
    hit = RetrievalHit(retrieval_run_id=run.id, matched_kind="CLINICAL_CHILD", matched_chunk_id=_REAL_CHUNK_ID, expanded_parent_document_id=_REAL_PARENT_DOCUMENT_ID, rank=1, score=score)
    db.add(hit)
    db.flush()
    generation = AIGeneration(conversation_id=conversation.id, retrieval_run_id=run.id, operator_id=operator_id, status="ANSWER", draft_text="documento clínico completo (fixture)", provider="clinical-parent-document", model="not-applicable", prompt_version="not-applicable", trigger="AUTOMATIC", category_slug=category_slug)
    db.add(generation)
    db.flush()
    db.add(AIGenerationSource(ai_generation_id=generation.id, retrieval_hit_id=hit.id, use_order=1))
    db.commit()
    return conversation, generation


def _cleanup(db, conversation_id, generation_ids, operator_id):
    conversation = db.get(Conversation, conversation_id)
    if conversation:
        conversation.auto_draft_covers_through_message_id = None
        db.commit()
    for generation_id in generation_ids:
        db.execute(delete(PendingAutonomousSend).where(PendingAutonomousSend.generation_id == generation_id))
        db.execute(delete(AIGenerationSource).where(AIGenerationSource.ai_generation_id == generation_id))
        db.execute(delete(MessageSelection).where(MessageSelection.ai_generation_id == generation_id))
    db.execute(delete(Message).where(Message.conversation_id == conversation_id))
    for generation_id in generation_ids:
        generation = db.get(AIGeneration, generation_id)
        if generation:
            db.execute(delete(RetrievalHit).where(RetrievalHit.retrieval_run_id == generation.retrieval_run_id))
        db.execute(delete(AIGeneration).where(AIGeneration.id == generation_id))
    db.execute(delete(RetrievalRun).where(RetrievalRun.operator_id == operator_id))
    db.commit()
    try:
        db.execute(delete(Conversation).where(Conversation.id == conversation_id))
        db.commit()
    except Exception:
        db.rollback()


class TestEligibilityGate:
    def test_both_off_never_opens_a_window(self, operator_id, category) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            conversation, generation = _make_generation(db, operator_id=operator_id)
            maybe_open_autonomous_window(db, generation, conversation)
            assert db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.generation_id == generation.id)) is None
            _cleanup(db, conversation.id, [generation.id], operator_id)

    def test_n5_on_category_matched_uses_governed_mechanism_not_ungoverned(self, operator_id, category) -> None:
        """spec.md N5-2: N5 never duplicates or overrides an already-
        grounded answer — only one AIGeneration ever exists here, and its
        pending row's mechanism stays 'governed_autonomy'."""
        session_factory = get_session_factory()
        with session_factory() as db:
            db.get(Category, category).autonomy_enabled = True
            settings = db.get(SystemSettings, True)
            settings.autonomy_kill_switch_enabled = True
            settings.n5_kill_switch_enabled = True
            db.commit()
            conversation, generation = _make_generation(db, operator_id=operator_id)
            maybe_open_autonomous_window(db, generation, conversation)
            pending = db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.generation_id == generation.id))
            assert pending is not None
            assert pending.mechanism == "governed_autonomy"
            assert pending.category == category
            other_generations = db.scalars(select(AIGeneration).where(AIGeneration.conversation_id == conversation.id, AIGeneration.id != generation.id)).all()
            assert other_generations == []
            db.get(Category, category).autonomy_enabled = False
            db.commit()
            _cleanup(db, conversation.id, [generation.id], operator_id)

    def test_n5_on_answer_with_no_category_delivers_existing_generation(self, operator_id, category) -> None:
        """D-043 (2026-08-21): a grounded `ANSWER` must never be discarded
        and re-generated from scratch by the ungoverned branch — N5 delivers
        that same generation verbatim (no new AIGeneration row, no fresh
        evidence-free LLM call)."""
        session_factory = get_session_factory()
        with session_factory() as db:
            settings = db.get(SystemSettings, True)
            settings.n5_kill_switch_enabled = True
            db.commit()
            conversation, generation = _make_generation(db, operator_id=operator_id, category_slug=None)
            maybe_open_autonomous_window(db, generation, conversation)
            pending = db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.conversation_id == conversation.id))
            assert pending is not None
            assert pending.mechanism == "ungoverned_n5"
            assert pending.category is None
            assert pending.generation_id == generation.id
            other_generations = db.scalars(select(AIGeneration).where(AIGeneration.conversation_id == conversation.id, AIGeneration.id != generation.id)).all()
            assert other_generations == []
            _cleanup(db, conversation.id, [generation.id], operator_id)

    def test_n5_on_answer_with_governed_switch_off_delivers_existing_generation_not_a_fresh_llm_call(self, operator_id, category) -> None:
        """D-043 (2026-08-21) regression for the exact bug found in
        production: a category *is* present and autonomy-enabled for it,
        but the *global* governed kill switch is off (this project's own
        standing default demo configuration, N5-only) — the governed
        branch above correctly declines to open a window, but the
        ungoverned branch must still deliver the already-grounded answer
        as-is, not manufacture an evidence-free replacement."""
        session_factory = get_session_factory()
        with session_factory() as db:
            db.get(Category, category).autonomy_enabled = True
            settings = db.get(SystemSettings, True)
            settings.autonomy_kill_switch_enabled = False
            settings.n5_kill_switch_enabled = True
            db.commit()
            conversation, generation = _make_generation(db, operator_id=operator_id)
            maybe_open_autonomous_window(db, generation, conversation)
            pending = db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.conversation_id == conversation.id))
            assert pending is not None
            assert pending.mechanism == "ungoverned_n5"
            assert pending.generation_id == generation.id
            other_generations = db.scalars(select(AIGeneration).where(AIGeneration.conversation_id == conversation.id, AIGeneration.id != generation.id)).all()
            assert other_generations == []
            db.get(Category, category).autonomy_enabled = False
            db.commit()
            _cleanup(db, conversation.id, [generation.id], operator_id)

    def test_n5_on_abstain_falls_through_to_ungoverned(self, operator_id, category) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            settings = db.get(SystemSettings, True)
            settings.n5_kill_switch_enabled = True
            db.commit()
            conversation, generation = _make_generation(db, operator_id=operator_id, status="ABSTAIN", category_slug=None)
            maybe_open_autonomous_window(db, generation, conversation)
            pending = db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.conversation_id == conversation.id))
            assert pending is not None
            assert pending.mechanism == "ungoverned_n5"
            ungoverned = db.get(AIGeneration, pending.generation_id)
            assert ungoverned.status == "ANSWER"
            _cleanup(db, conversation.id, [ungoverned.id, generation.id], operator_id)

    def test_n5_off_abstain_still_never_opens_a_window(self, operator_id, category) -> None:
        """Regression: Amendment 1.2.0 clause (a)'s never-autonomous-on-
        ABSTAIN rule is unaffected whenever N5's own switch is off."""
        session_factory = get_session_factory()
        with session_factory() as db:
            conversation, generation = _make_generation(db, operator_id=operator_id, status="ABSTAIN", category_slug=None)
            maybe_open_autonomous_window(db, generation, conversation)
            assert db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.conversation_id == conversation.id)) is None
            other_generations = db.scalars(select(AIGeneration).where(AIGeneration.conversation_id == conversation.id, AIGeneration.id != generation.id)).all()
            assert other_generations == []
            _cleanup(db, conversation.id, [generation.id], operator_id)


class TestGuidedBookingEligibility:
    """D-043-2 (2026-08-21): GB (005) generations are never trigger=='AUTOMATIC'
    — 010's own governed branch must stay closed to them regardless of
    switch state, while N5 (only) now delivers them, matching the
    human decision to extend N5 (never N3/N4) to GB's own fixed-template
    output once booking_script's own D-043 fix made it the only real
    booking path."""

    @pytest.mark.parametrize("gb_trigger", ["GUIDED_SLOT_SELECTION", "GUIDED_SLOT_RESELECTION", "GUIDED_CPF_CONFIRMED", "GUIDED_BOOKING_COMPLETE"])
    def test_gb_trigger_delivers_verbatim_under_n5(self, operator_id, category, gb_trigger: str) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            settings = db.get(SystemSettings, True)
            settings.n5_kill_switch_enabled = True
            db.commit()
            conversation, generation = _make_generation(db, operator_id=operator_id, trigger=gb_trigger, category_slug=None)
            maybe_open_autonomous_window(db, generation, conversation)
            pending = db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.conversation_id == conversation.id))
            assert pending is not None, f"{gb_trigger} must be eligible for N5 delivery"
            assert pending.mechanism == "ungoverned_n5"
            assert pending.category is None
            assert pending.generation_id == generation.id, "GB output is delivered verbatim, never re-generated"
            other_generations = db.scalars(select(AIGeneration).where(AIGeneration.conversation_id == conversation.id, AIGeneration.id != generation.id)).all()
            assert other_generations == []
            _cleanup(db, conversation.id, [generation.id], operator_id)

    def test_gb_trigger_never_opens_a_window_when_n5_off(self, operator_id, category) -> None:
        """Without N5, GB's own D-032 decision (operator must explicitly
        send) still holds — no autonomy mechanism applies to GB output."""
        session_factory = get_session_factory()
        with session_factory() as db:
            conversation, generation = _make_generation(db, operator_id=operator_id, trigger="GUIDED_SLOT_SELECTION", category_slug=None)
            maybe_open_autonomous_window(db, generation, conversation)
            assert db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.conversation_id == conversation.id)) is None
            _cleanup(db, conversation.id, [generation.id], operator_id)

    def test_gb_trigger_never_uses_governed_mechanism_even_with_both_switches_on(self, operator_id, category) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            db.get(Category, category).autonomy_enabled = True
            settings = db.get(SystemSettings, True)
            settings.autonomy_kill_switch_enabled = True
            settings.n5_kill_switch_enabled = True
            db.commit()
            # A GB generation never carries a category_slug, but exercise
            # the governed-branch guard directly regardless.
            conversation, generation = _make_generation(db, operator_id=operator_id, trigger="GUIDED_CPF_CONFIRMED", category_slug=category)
            maybe_open_autonomous_window(db, generation, conversation)
            pending = db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.conversation_id == conversation.id))
            assert pending is not None
            assert pending.mechanism == "ungoverned_n5", "GB triggers must never use the governed (N3/N4) mechanism"
            db.get(Category, category).autonomy_enabled = False
            db.commit()
            _cleanup(db, conversation.id, [generation.id], operator_id)


class TestClinicalRelevanceGate:
    """D-043-2 (2026-08-21): full_parent_draft()'s unconditional
    clinical-rank-one shortcut is safe for N1/N2 manual review, not for
    autonomous send — a low-score match (noise, e.g. a bare greeting) must
    not autosend the full unrelated document."""

    def test_weak_clinical_shortcut_falls_back_to_ungoverned_llm_under_n5(self, operator_id, category) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            settings = db.get(SystemSettings, True)
            settings.n5_kill_switch_enabled = True
            db.commit()
            conversation, generation = _make_clinical_shortcut_generation(db, score=0.31, operator_id=operator_id)
            maybe_open_autonomous_window(db, generation, conversation)
            pending = db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.conversation_id == conversation.id))
            assert pending is not None, "the customer must still get a reply — just not the irrelevant document"
            assert pending.mechanism == "ungoverned_n5"
            assert pending.generation_id != generation.id, "the weak clinical draft must not be delivered as-is"
            ungoverned = db.get(AIGeneration, pending.generation_id)
            assert ungoverned.provider == "ungoverned-n5"
            assert ungoverned.status == "ANSWER"
            _cleanup(db, conversation.id, [ungoverned.id, generation.id], operator_id)

    def test_strong_clinical_shortcut_delivers_verbatim_under_n5(self, operator_id, category) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            settings = db.get(SystemSettings, True)
            settings.n5_kill_switch_enabled = True
            db.commit()
            conversation, generation = _make_clinical_shortcut_generation(db, score=0.7, operator_id=operator_id)
            maybe_open_autonomous_window(db, generation, conversation)
            pending = db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.conversation_id == conversation.id))
            assert pending is not None
            assert pending.mechanism == "ungoverned_n5"
            assert pending.generation_id == generation.id, "a genuinely relevant clinical match is delivered verbatim"
            other_generations = db.scalars(select(AIGeneration).where(AIGeneration.conversation_id == conversation.id, AIGeneration.id != generation.id)).all()
            assert other_generations == []
            _cleanup(db, conversation.id, [generation.id], operator_id)

    def test_weak_clinical_shortcut_blocks_the_governed_branch_too(self, operator_id, category) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            db.get(Category, category).autonomy_enabled = True
            settings = db.get(SystemSettings, True)
            settings.autonomy_kill_switch_enabled = True
            settings.n5_kill_switch_enabled = False
            db.commit()
            conversation, generation = _make_clinical_shortcut_generation(db, score=0.31, operator_id=operator_id, category_slug=category)
            maybe_open_autonomous_window(db, generation, conversation)
            assert db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.conversation_id == conversation.id)) is None, "a weak clinical match must not be sent by N3/N4 either — it stays an ordinary N2 draft for a human to review"
            db.get(Category, category).autonomy_enabled = False
            db.commit()
            _cleanup(db, conversation.id, [generation.id], operator_id)


class TestResolution:
    def test_window_elapses_and_sends_with_ungoverned_source(self, operator_id, category) -> None:
        session_factory = get_session_factory()
        with session_factory() as db:
            conversation, generation = _make_generation(db, operator_id=operator_id)
            past = datetime.now(UTC) - timedelta(seconds=1)
            pending = PendingAutonomousSend(generation_id=generation.id, conversation_id=conversation.id, category=None, mechanism="ungoverned_n5", window_seconds=0, opens_at=past, resolves_at=past, status="PENDING")
            db.add(pending)
            db.commit()
            resolve_elapsed_autonomous_sends(db)
            db.refresh(pending)
            assert pending.status == "SENT"
            message = db.scalar(select(Message).where(Message.conversation_id == conversation.id))
            assert message is not None
            assert message.autonomous_source == "ungoverned_n5"
            assert message.operator_id is None
            _cleanup(db, conversation.id, [generation.id], operator_id)


class TestUnclaimedTrigger:
    def test_waiting_conversation_gets_an_ungoverned_autonomous_send(self, category) -> None:
        """GA-6-style guarantee, for N5: an unclaimed conversation's status
        stays WAITING, no capacity consumed, whatever the underlying
        evidence-gated generation would have done — N5 always fills the
        gap when it's on."""
        session_factory = get_session_factory()
        with session_factory() as db:
            settings = db.get(SystemSettings, True)
            settings.n5_kill_switch_enabled = True
            settings.automatic_trigger_idle_seconds = 0
            db.commit()
            conversation = Conversation(anonymous_token_digest=uuid4().hex, initial_mode="N2", effective_mode="N2", status="WAITING", last_customer_activity_at=datetime.now(UTC) - timedelta(seconds=30))
            db.add(conversation)
            db.flush()
            message = Message(conversation_id=conversation.id, author_type="CUSTOMER", body="Mensagem totalmente fora da base de conhecimento (t011 fixture xyzabc)")
            db.add(message)
            db.commit()
            conversation_id = conversation.id
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            evaluate_unclaimed_autonomous_trigger(db, conversation)
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            assert conversation.status == "WAITING"
            generations = db.scalars(select(AIGeneration).where(AIGeneration.conversation_id == conversation_id)).all()
            pending = db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.conversation_id == conversation_id))
            assert pending is not None
            assert pending.mechanism == "ungoverned_n5"
            conversation.auto_draft_covers_through_message_id = None
            db.commit()
            for generation in generations:
                assert generation.operator_id is None
                db.execute(delete(PendingAutonomousSend).where(PendingAutonomousSend.generation_id == generation.id))
                db.execute(delete(AIGenerationSource).where(AIGenerationSource.ai_generation_id == generation.id))
                db.execute(delete(MessageSelection).where(MessageSelection.ai_generation_id == generation.id))
                db.execute(delete(RetrievalHit).where(RetrievalHit.retrieval_run_id == generation.retrieval_run_id))
            db.commit()
            # A 3-way FK cycle (ai_generations.retrieval_run_id ->
            # retrieval_runs; retrieval_runs.triggering_message_id ->
            # messages; messages.source_generation_id -> ai_generations,
            # set when resolve_elapsed_autonomous_sends() actually sent
            # this test's own autonomous message) — break it by nulling
            # messages.source_generation_id first, same as
            # auto_draft_covers_through_message_id above.
            for message in db.scalars(select(Message).where(Message.conversation_id == conversation_id)).all():
                message.source_generation_id = None
            # ai_generations.prior_generation_id is a self-reference (the
            # ungoverned generation chains to the evidence-gated one it
            # followed, plan.md §3) — also nulled before any delete, same
            # cycle-breaking approach as source_generation_id above (two
            # generations may also share one retrieval_run_id — this
            # project's own known-fixture-cleanup discipline: null every
            # cyclic FK first, then delete freely, not "figure out an
            # order").
            for generation in generations:
                generation.prior_generation_id = None
            db.commit()
            for generation in generations:
                db.execute(delete(AIGeneration).where(AIGeneration.id == generation.id))
            for retrieval_run_id in {generation.retrieval_run_id for generation in generations}:
                db.execute(delete(RetrievalRun).where(RetrievalRun.id == retrieval_run_id))
            db.commit()
            db.execute(delete(Message).where(Message.conversation_id == conversation_id))
            db.commit()
        with session_factory() as db:
            try:
                db.execute(delete(Conversation).where(Conversation.id == conversation_id))
                db.commit()
            except Exception:
                db.rollback()


class TestIdleSeconds:
    def test_custom_idle_seconds_delays_the_uncovered_run(self, operator_id) -> None:
        """plan.md §6: a real, not simulated, timing check against
        _uncovered_customer_run()'s own idle-debounce guard via the public
        evaluate_unclaimed_autonomous_trigger() entry point."""
        session_factory = get_session_factory()
        with session_factory() as db:
            settings = db.get(SystemSettings, True)
            settings.automatic_trigger_idle_seconds = 3600
            db.commit()
            conversation = Conversation(anonymous_token_digest=uuid4().hex, initial_mode="N2", effective_mode="N2", status="WAITING", last_customer_activity_at=datetime.now(UTC) - timedelta(seconds=30))
            db.add(conversation)
            db.flush()
            db.add(Message(conversation_id=conversation.id, author_type="CUSTOMER", body="Mensagem recente (t011 idle fixture)"))
            db.commit()
            conversation_id = conversation.id
        with session_factory() as db:
            conversation = db.get(Conversation, conversation_id)
            evaluate_unclaimed_autonomous_trigger(db, conversation)
        with session_factory() as db:
            generation = db.scalar(select(AIGeneration).where(AIGeneration.conversation_id == conversation_id))
            assert generation is None, "a 3600s idle threshold must not have elapsed for a 30s-old message"
            db.execute(delete(Message).where(Message.conversation_id == conversation_id))
            db.execute(delete(Conversation).where(Conversation.id == conversation_id))
            db.commit()
