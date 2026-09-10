"""D-044 follow-on (human requirement 2026-08-27: "preciso que funcione,
independente do operador"): an unclaimed autonomous reply (N5 here) must
be delivered from the customer's own message / heartbeat / poll — never
only from an operator queue poll. Real HTTP via TestClient, zero operator
interaction. specs/012-…/analysis.md §8.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from customer_care.bootstrap import create_app
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import (
    AIGeneration,
    AIGenerationSource,
    Conversation,
    Message,
    MessageSelection,
    PendingAutonomousSend,
    RetrievalHit,
    RetrievalRun,
    SystemSettings,
)


@pytest.fixture
def n5_immediate():
    """N5 on, governed off, zero idle debounce and zero veto window — the
    standing prod demo config, restored afterward."""
    f = get_session_factory()
    with f() as db:
        s = db.get(SystemSettings, True)
        prev = (s.n5_kill_switch_enabled, s.autonomy_kill_switch_enabled, s.autonomy_window_seconds, s.automatic_trigger_idle_seconds)
        s.n5_kill_switch_enabled = True
        s.autonomy_kill_switch_enabled = False
        s.autonomy_window_seconds = 0
        s.automatic_trigger_idle_seconds = 0
        db.commit()
    yield
    with f() as db:
        s = db.get(SystemSettings, True)
        s.n5_kill_switch_enabled, s.autonomy_kill_switch_enabled, s.autonomy_window_seconds, s.automatic_trigger_idle_seconds = prev
        db.commit()


def _purge(conversation_id) -> None:
    f = get_session_factory()
    with f() as db:
        # Break the FK cycle (retrieval_runs.triggering_message_id -> messages
        # -> messages.source_generation_id -> ai_generations -> retrieval_runs).
        db.execute(update(RetrievalRun).where(RetrievalRun.conversation_id == conversation_id).values(triggering_message_id=None))
        db.execute(update(Message).where(Message.conversation_id == conversation_id).values(source_generation_id=None))
        db.execute(update(Conversation).where(Conversation.id == conversation_id).values(auto_draft_covers_through_message_id=None))
        gids = list(db.scalars(select(AIGeneration.id).where(AIGeneration.conversation_id == conversation_id)))
        rids = list(db.scalars(select(RetrievalRun.id).where(RetrievalRun.conversation_id == conversation_id)))
        for gid in gids:
            db.execute(delete(AIGenerationSource).where(AIGenerationSource.ai_generation_id == gid))
            db.execute(delete(MessageSelection).where(MessageSelection.ai_generation_id == gid))
            db.execute(delete(PendingAutonomousSend).where(PendingAutonomousSend.generation_id == gid))
        for rid in rids:
            db.execute(delete(RetrievalHit).where(RetrievalHit.retrieval_run_id == rid))
        db.execute(delete(AIGeneration).where(AIGeneration.conversation_id == conversation_id))
        db.execute(delete(RetrievalRun).where(RetrievalRun.conversation_id == conversation_id))
        db.execute(delete(Message).where(Message.conversation_id == conversation_id))
        db.commit()
    with f() as db:
        try:
            db.execute(delete(Conversation).where(Conversation.id == conversation_id))
            db.commit()
        except Exception:
            db.rollback()


def test_unclaimed_conversation_gets_an_autonomous_reply_with_no_operator(n5_immediate) -> None:
    client = TestClient(create_app())
    created = client.post("/api/v1/public/conversations")
    assert created.status_code == 201, created.text
    cid = created.json()["conversation"]["id"]
    ch = {"Authorization": f"Bearer {created.json()['access_token']}"}

    sent = client.post(f"/api/v1/public/conversations/{cid}/messages", headers=ch, json={"body": "quero agendar uma consulta"})
    assert sent.status_code == 201, sent.text

    # One customer-side GET poll is all it takes (the message POST itself
    # already drives it with idle/window == 0, but assert via the poll the
    # browser actually does).
    detail = client.get(f"/api/v1/public/conversations/{cid}", headers=ch).json()
    operator_msgs = [m for m in detail["messages"] if m["author_type"] == "OPERATOR"]
    try:
        assert len(operator_msgs) == 1, detail["messages"]
        # conversation stays WAITING — no operator, no claim, no capacity consumed
        assert detail["status"] == "WAITING"
        with get_session_factory()() as db:
            assert db.scalar(select(Conversation.status).where(Conversation.id == cid)) == "WAITING"
            # the delivered message really is the autonomous one (internal
            # field, not exposed in the customer projection above)
            src = db.scalar(select(Message.autonomous_source).where(Message.conversation_id == cid, Message.author_type == "OPERATOR"))
            assert src == "ungoverned_n5", src
    finally:
        _purge(cid)


def test_repeated_polls_never_produce_a_duplicate_autonomous_reply(n5_immediate) -> None:
    client = TestClient(create_app())
    created = client.post("/api/v1/public/conversations")
    cid = created.json()["conversation"]["id"]
    ch = {"Authorization": f"Bearer {created.json()['access_token']}"}
    client.post(f"/api/v1/public/conversations/{cid}/messages", headers=ch, json={"body": "quero agendar uma consulta"})

    try:
        for _ in range(6):
            client.get(f"/api/v1/public/conversations/{cid}", headers=ch)
            client.post(f"/api/v1/public/conversations/{cid}/typing", headers=ch)  # 204, also drives it
        with get_session_factory()() as db:
            op = db.scalars(select(Message).where(Message.conversation_id == cid, Message.author_type == "OPERATOR")).all()
        assert len(op) == 1, [m.body for m in op]
    finally:
        _purge(cid)
