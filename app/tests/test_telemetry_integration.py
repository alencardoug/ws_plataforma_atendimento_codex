"""LF-4/5: real commits, original N5 branches and exact retrieval payloads."""

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from customer_care.ai import router as ai_router
from customer_care.autonomy.service import resolve_elapsed_autonomous_sends
from customer_care.infrastructure import telemetry
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import AIGeneration, AIGenerationSource, Category, Conversation, KnowledgeChunk, Message, MessageSelection, PendingAutonomousSend, RetrievalHit, RetrievalRun, SystemSettings
from customer_care.rag.service import retrieve
from langfuse_gate_support import require_isolated_database
from test_customer_driven_autonomy import _purge
from test_telemetry import recording as recording_fixture

recording = recording_fixture


@pytest.fixture
def setup_turns(recording):
    require_isolated_database()
    factory = get_session_factory()
    conversations = []
    category_slug = "lf013-" + uuid4().hex[:12]
    with factory() as db:
        settings = db.get(SystemSettings, True)
        previous = settings.n5_kill_switch_enabled, settings.autonomy_kill_switch_enabled, settings.autonomy_window_seconds
        settings.n5_kill_switch_enabled, settings.autonomy_kill_switch_enabled, settings.autonomy_window_seconds = True, False, 0
        db.add(Category(slug=category_slug, label="Synthetic LF-5", is_active=True, autonomy_enabled=True))
        db.commit()

    def create(db, *, status="ANSWER", provider="test", trigger="AUTOMATIC", governed=False, weak=False):
        conversation = Conversation(anonymous_token_digest="never-export-digest-" + uuid4().hex, initial_mode="N2", effective_mode="N2", status="WAITING")
        db.add(conversation)
        db.flush()
        message = Message(conversation_id=conversation.id, author_type="CUSTOMER", body="Pergunta sintética", created_at=datetime.now(UTC) - timedelta(seconds=40))
        db.add(message)
        db.flush()
        run = RetrievalRun(conversation_id=conversation.id, triggering_message_id=message.id, purpose="N2_DRAFT", query_text=message.body, embedding_model="test", top_k=1, status="COMPLETED")
        db.add(run)
        db.flush()
        generation = AIGeneration(conversation_id=conversation.id, triggering_message_id=message.id, retrieval_run_id=run.id,
                                  provider=provider, model="not-applicable", prompt_version="test", trigger=trigger, status=status,
                                  draft_text="Mesmo texto sintético", category_slug=category_slug if governed else None,
                                  abstention_reason="INSUFFICIENT_EVIDENCE" if status == "ABSTAIN" else None)
        db.add(generation)
        db.flush()
        db.add(MessageSelection(ai_generation_id=generation.id, message_id=message.id))
        if weak:
            chunk = db.scalar(select(KnowledgeChunk).limit(1))
            hit = RetrievalHit(retrieval_run_id=run.id, matched_kind="CLINICAL_CHILD", matched_chunk_id=chunk.chunk_id,
                               expanded_parent_document_id=chunk.parent_document_id, rank=1, score=0.1)
            db.add(hit)
            db.flush()
            db.add(AIGenerationSource(ai_generation_id=generation.id, retrieval_hit_id=hit.id, use_order=1))
        if governed:
            db.get(SystemSettings, True).autonomy_kill_switch_enabled = True
        db.commit()
        conversations.append(conversation.id)
        return conversation, message, generation

    yield create
    for conversation_id in conversations:
        _purge(conversation_id)
    with factory() as db:
        settings = db.get(SystemSettings, True)
        settings.n5_kill_switch_enabled, settings.autonomy_kill_switch_enabled, settings.autonomy_window_seconds = previous
        db.delete(db.get(Category, category_slug))
        db.commit()


@pytest.mark.parametrize("options,path,reason,mechanism", [
    ({}, "reuse_answer", None, "ungoverned_n5"),
    ({"trigger": "GUIDED_SLOT_SELECTION", "provider": "guided-booking"}, "guided_booking", None, "ungoverned_n5"),
    ({"status": "ABSTAIN"}, "freeform_fallback", "initial_not_answer", "ungoverned_n5"),
    ({"provider": "clinical-parent-document", "weak": True}, "freeform_fallback", "weak_clinical_shortcut", "ungoverned_n5"),
    ({"governed": True}, None, None, "governed_autonomy"),
    ({"trigger": "MANUAL_BOOKING_OFFER", "governed": True}, None, None, None),
])
def test_decision_trace_follows_existing_branch_and_preserves_reused_generation(recording, setup_turns, options, path, reason, mechanism):
    with get_session_factory()() as db:
        conversation, message, generation = setup_turns(db, **options)
        with telemetry.execution_origin("customer_poll"), ai_router._observe_turn(conversation, message, [message]):
            ai_router.maybe_open_autonomous_window(db, generation, conversation)
        pending = db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.conversation_id == conversation.id))
        if mechanism:
            assert pending.mechanism == mechanism
            if path != "freeform_fallback":
                assert pending.generation_id == generation.id
                assert db.get(AIGeneration, pending.generation_id).draft_text == "Mesmo texto sintético"
        else:
            assert pending is None
    decision = next(item.values for item in recording.spans if item.values["name"] == "autonomy.decision")
    assert decision["metadata"].get("n5_path") == path
    assert decision["metadata"].get("fallback_reason") == reason
    assert decision["metadata"].get("mechanism") == mechanism
    assert decision["metadata"]["execution_origin"] == "customer_poll"
    assert "never-export-digest" not in json.dumps([s.values for s in recording.spans])
    assert all(s.ended for s in recording.spans)
    assert not any(s.values["as_type"] == "generation" for s in recording.spans)  # deterministic test providers do not bill


def test_fallback_failure_still_records_reason_without_confirming_open_or_send(recording, setup_turns, monkeypatch):
    failure = OSError("sensitive-provider-diagnostic")

    def unavailable(*args):
        raise failure

    monkeypatch.setattr(ai_router, "generate_ungoverned_reply", unavailable)
    with get_session_factory()() as db:
        conversation, message, generation = setup_turns(db, status="ABSTAIN")
        with pytest.raises(OSError) as caught:
            with ai_router._observe_turn(conversation, message, [message]):
                ai_router.maybe_open_autonomous_window(db, generation, conversation)
        assert caught.value is failure
        assert db.scalar(select(PendingAutonomousSend).where(PendingAutonomousSend.conversation_id == conversation.id)) is None
    assert any(s["name"] == "n5.fallback_started" and s["value"] == 1 for s in recording.scores)
    assert not any(s["name"] in {"n5.pending_opened", "n5.sent"} for s in recording.scores)
    assert "sensitive-provider-diagnostic" not in json.dumps([s.values for s in recording.spans])


def test_rollback_never_confirms_send_and_later_poll_uses_each_generations_own_trace(recording, setup_turns, monkeypatch):
    with get_session_factory()() as db:
        conversation, message, generation = setup_turns(db)
        with ai_router._observe_turn(conversation, message, [message]):
            ai_router.maybe_open_autonomous_window(db, generation, conversation)
        recording.spans.clear()
        recording.scores.clear()
        original_commit = db.commit

        def rollback_commit():
            raise RuntimeError("synthetic commit failure")

        with monkeypatch.context() as patch:
            patch.setattr(db, "commit", rollback_commit)
            with pytest.raises(RuntimeError):
                resolve_elapsed_autonomous_sends(db)
        db.rollback()
        assert not recording.spans and not recording.scores
        assert db.scalar(select(Message).where(Message.conversation_id == conversation.id, Message.author_type == "OPERATOR")) is None
        assert db.commit == original_commit
        unrelated_trace = uuid4().hex
        with telemetry.observe("n5.process_turn", identity=lambda: {"trace_id": unrelated_trace, "session_id": "unrelated-poll"}):
            resolve_elapsed_autonomous_sends(db)
            resolve_elapsed_autonomous_sends(db)
        sent = db.scalars(select(Message).where(Message.conversation_id == conversation.id, Message.author_type == "OPERATOR")).all()
        assert len(sent) == 1 and sent[0].source_generation_id == generation.id
    confirmed = [s for s in recording.spans if s.values["name"] in {"message.sent", "autonomy.pending_resolved"}]
    assert len(confirmed) == 2
    assert all(s.values["trace_context"] == {"trace_id": message.id.hex} for s in confirmed)
    assert [s["value"] for s in recording.scores if s["name"] == "n5.pending_outcome"] == ["SENT"]


def test_retrieval_observes_exact_joined_query_and_ordered_expanded_evidence(recording, setup_turns):
    with get_session_factory()() as db:
        conversation, message, _ = setup_turns(db)
        query = "mensagem um\nmensagem dois\nbusca manual adicional"
        with telemetry.correlation(lambda: {"session_id": str(conversation.id), "operation_purpose": "manual_draft"}):
            run, evidence = retrieve(db, operator_id=None, query=query, purpose="N2_DRAFT", top_k=8, conversation_id=conversation.id, triggering_message_id=message.id)
        db.commit()
        observed = next(s.values for s in recording.spans if s.values["name"] == "rag.retrieve")
        assert observed["input"] == {"query": run.query_text, "top_k": 8}
        assert run.query_text == query
        assert [item["retrieval_hit_id"] for item in observed["output"]["evidence"]] == [str(item.retrieval_hit_id) for item in evidence]
        for actual, exported in zip(evidence, observed["output"]["evidence"], strict=True):
            assert exported["content"] == actual.content
            assert exported["matched_child_excerpt"] == actual.matched_child_excerpt
            assert exported["score"] == actual.score
            hit = db.get(RetrievalHit, actual.retrieval_hit_id)
            assert exported["expanded_parent_document_id"] == hit.expanded_parent_document_id
