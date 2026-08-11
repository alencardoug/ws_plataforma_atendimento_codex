"""Executable deterministic N2/RAG/citation/take-over smoke."""

import os
from fastapi.testclient import TestClient
from sqlalchemy import select

from customer_care.bootstrap import create_app
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import AIGeneration, AuditEvent, Message, RetrievalHit


def run() -> None:
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/operator/login", json={"email": os.environ["SMOKE_OPERATOR_EMAIL"], "password": os.environ["SMOKE_OPERATOR_PASSWORD"]})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    active = client.get("/api/v1/operator/conversations?scope=active", headers=headers).json()
    assert len(active) == 4
    conversation_id = active[0]["id"]
    detail = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers)
    customer_message = next(item for item in reversed(detail.json()["messages"]) if item["author_type"] == "CUSTOMER")
    generated = client.post(f"/api/v1/operator/conversations/{conversation_id}/drafts", headers=headers, json={"triggering_message_id": customer_message["id"]})
    assert generated.status_code == 201, generated.text
    draft = generated.json()
    assert draft["status"] in {"ANSWER", "ABSTAIN"} and draft["evidence"]
    assert all("retrieval_hit_id" in item for item in draft["evidence"])
    clinical = next((item for item in draft["evidence"] if item["knowledge_type"] == "CLINICAL" and item["customer_citation_allowed"]), None)
    citations = [clinical["retrieval_hit_id"]] if clinical else []
    before_send = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers).json()
    assert all(message["body"] != draft["draft_text"] or message["author_type"] != "OPERATOR" for message in before_send["messages"])
    admin = next((item for item in draft["evidence"] if item["knowledge_type"] == "ADMIN_QA"), None)
    if admin:
        rejected = client.post(f"/api/v1/operator/conversations/{conversation_id}/messages", headers=headers, json={"body": "Não deve publicar fonte administrativa.", "citation_retrieval_hit_ids": [admin["retrieval_hit_id"]]})
        assert rejected.status_code == 422 and rejected.json()["code"] == "CITATION_NOT_EXPOSABLE"
    sent = client.post(f"/api/v1/operator/conversations/{conversation_id}/messages", headers=headers, json={"body": draft["draft_text"] or "Resposta manual.", "source_generation_id": draft["id"], "citation_retrieval_hit_ids": citations})
    assert sent.status_code == 201, sent.text
    if citations:
        assert len(sent.json()["citations"]) == 1

    second_id = active[1]["id"]
    takeover = client.post(f"/api/v1/operator/conversations/{second_id}/take-over", headers=headers)
    assert takeover.status_code == 200 and takeover.json()["effective_mode"] == "N1"
    second_detail = client.get(f"/api/v1/operator/conversations/{second_id}", headers=headers).json()
    second_message = next(item for item in reversed(second_detail["messages"]) if item["author_type"] == "CUSTOMER")
    forbidden = client.post(f"/api/v1/operator/conversations/{second_id}/drafts", headers=headers, json={"triggering_message_id": second_message["id"]})
    assert forbidden.status_code == 409
    manual = client.post(f"/api/v1/operator/conversations/{second_id}/messages", headers=headers, json={"body": "Atendimento manual após take-over."})
    assert manual.status_code == 201
    with get_session_factory()() as db:
        generation = db.get(AIGeneration, draft["id"])
        assert generation is not None
        published = db.scalars(select(Message).where(Message.source_generation_id == generation.id)).all()
        assert len(published) == 1 and published[0].author_type == "OPERATOR"
        hit = db.scalar(select(RetrievalHit).where(RetrievalHit.retrieval_run_id == generation.retrieval_run_id, RetrievalHit.matched_kind == "CLINICAL_CHILD"))
        if hit:
            assert hit.matched_chunk_id and hit.expanded_parent_document_id
        event_types = set(db.scalars(select(AuditEvent.event_type)).all())
        assert {"rag.search_started", "rag.search_completed", "ai.draft_generated", "message.operator_sent", "conversation.taken_over"} <= event_types
    print("n2_smoke_ok: retrieval, internal draft, explicit send, citation policy, take-over")


if __name__ == "__main__":
    run()
