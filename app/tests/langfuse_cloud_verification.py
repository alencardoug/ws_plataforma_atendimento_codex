"""Read back LF-5 smoke traces. No generation, scoring or database writes."""

import json
import math
import time
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select

from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.langfuse_probe import cloud_url
from customer_care.infrastructure.models import AIGeneration, Message, PendingAutonomousSend, RetrievalHit, RetrievalRun
from customer_care.rag.service import load_evidence
from customer_care.shared.settings import get_settings
from langfuse_gate_support import require_isolated_database


def decoded(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def verify() -> dict[str, Any]:
    require_isolated_database()
    settings = get_settings()
    assert settings.langfuse_tracing_enabled and settings.ai_provider == "openai"
    assert settings.langfuse_public_key and settings.langfuse_secret_key
    records: dict[str, Any] = {}
    with get_session_factory()() as db:
        for pending, generation in db.execute(select(PendingAutonomousSend, AIGeneration).join(AIGeneration, AIGeneration.id == PendingAutonomousSend.generation_id)):
            if generation.triggering_message_id is None:
                continue
            sent = db.scalar(select(Message).where(Message.source_generation_id == generation.id, Message.author_type == "OPERATOR"))
            records[generation.triggering_message_id.hex] = {
                "session_id": str(generation.conversation_id), "generation_id": str(generation.id),
                "pending_id": str(pending.id), "status": pending.status, "mechanism": pending.mechanism,
                "text": generation.draft_text, "message_id": str(sent.id) if sent else None,
            }
    assert records, "No smoke pending-send records to verify"
    deadline = time.monotonic() + 30
    verified: list[dict[str, Any]] = []
    with httpx.Client(base_url=cloud_url(settings), auth=(settings.langfuse_public_key.get_secret_value(), settings.langfuse_secret_key.get_secret_value()), timeout=3, follow_redirects=False) as api:
        for trace_id, expected in records.items():
            while True:
                try:
                    response = api.get(f"/api/public/traces/{trace_id}")
                    response.raise_for_status()
                    trace = response.json()
                    observations = trace.get("observations") or []
                    names = {row["name"] for row in observations}
                    ready = {"n5.process_turn", "autonomy.decision", "autonomy.pending_opened", "rag.retrieve", "ai.embedding"} <= names
                    ready = ready and (expected["status"] != "SENT" or {"autonomy.pending_resolved", "message.sent"} <= names)
                    if ready and trace.get("scores"):
                        break
                except (httpx.HTTPError, ValueError):
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Cloud confirmation unavailable for trace {trace_id}")
                time.sleep(1)
            assert trace["sessionId"] == expected["session_id"]
            assert len({row["id"] for row in observations}) == len(observations)
            root = next(row for row in observations if row["name"] == "n5.process_turn")
            decision = next(row for row in observations if row["name"] == "autonomy.decision")
            metadata = decoded(decision["metadata"])
            outcome = decoded(decision["output"])
            assert metadata["mechanism"] == expected["mechanism"]
            assert outcome["final_generation"]["ai_generation_id"] == expected["generation_id"]
            assert outcome["final_generation"]["draft_text"] == expected["text"]
            assert decision["parentObservationId"] == root["id"]
            if expected["status"] == "SENT":
                event = next(row for row in observations if row["name"] == "message.sent")
                assert decoded(event["output"])["message_id"] == expected["message_id"]
                assert decoded(event["output"])["body"] == expected["text"]
            with get_session_factory()() as db:
                for observation in observations:
                    if observation["name"] != "rag.retrieve":
                        continue
                    run_id = decoded(observation["metadata"])["retrieval_run_id"]
                    run = db.get(RetrievalRun, UUID(run_id))
                    assert decoded(observation["input"]) == {"query": run.query_text, "top_k": run.top_k}
                    evidence = decoded(observation["output"])["evidence"]
                    hits = db.scalars(select(RetrievalHit).where(RetrievalHit.retrieval_run_id == run.id).order_by(RetrievalHit.rank)).all()
                    assert len(hits) == len(evidence)
                    for hit, observed in zip(hits, evidence, strict=True):
                        actual = load_evidence(db, hit.id)
                        assert observed["retrieval_hit_id"] == str(hit.id)
                        assert observed["content"] == actual.content and observed["matched_child_excerpt"] == actual.matched_child_excerpt
                        assert observed["score"] == hit.score and observed["expanded_parent_document_id"] == hit.expanded_parent_document_id
            billable = [row for row in observations if row["type"] in {"GENERATION", "EMBEDDING"}]
            assert billable
            for row in billable:
                assert row.get("usageDetails") and row.get("calculatedTotalCost") is not None
                assert row["name"] in {"ai.answer", "ai.clinical_rerank", "ai.date_intent", "ai.n5_free", "ai.embedding"}
            total = sum(row["calculatedTotalCost"] for row in billable)
            assert math.isclose(trace["totalCost"], total, abs_tol=1e-10)
            scores = trace["scores"]
            assert len({(row["id"], row["name"]) for row in scores}) == len(scores)
            verified.append({"trace_id": trace_id, "session_id": trace["sessionId"], "url": cloud_url(settings) + trace["htmlPath"],
                             "path": metadata.get("n5_path"), "fallback_reason": metadata.get("fallback_reason"),
                             "mechanism": expected["mechanism"], "status": expected["status"], "observations": len(observations),
                             "billable_operations": len(billable), "cost_usd": total, "scores": len(scores)})
    paths = {row["path"] for row in verified}
    assert {"reuse_answer", "guided_booking", "freeform_fallback"} <= paths
    assert any(row["mechanism"] == "governed_autonomy" and row["path"] is None for row in verified)
    return {"status": "persisted", "traces": verified, "note": "Technical smoke evidence; not the LF-6 quality assessment"}


if __name__ == "__main__":
    try:
        print(json.dumps(verify(), ensure_ascii=False))
    except Exception as error:
        print(json.dumps({"status": "failed", "error_class": type(error).__name__}))
        raise SystemExit(1) from None
