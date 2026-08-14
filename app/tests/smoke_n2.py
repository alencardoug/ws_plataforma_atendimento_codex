"""Executable deterministic N2/RAG/citation/take-over smoke."""

import os
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from customer_care.bootstrap import create_app
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import AIGeneration, AIGenerationSource, AuditEvent, Message, QADynamicBinding, QAEntry, RetrievalHit, RetrievalRun


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
    generated = client.post(f"/api/v1/operator/conversations/{conversation_id}/drafts", headers=headers, json={"selected_message_ids": [customer_message["id"]]})
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
    forbidden = client.post(f"/api/v1/operator/conversations/{second_id}/drafts", headers=headers, json={"selected_message_ids": [second_message["id"]]})
    assert forbidden.status_code == 409
    manual = client.post(f"/api/v1/operator/conversations/{second_id}/messages", headers=headers, json={"body": "Atendimento manual após take-over."})
    assert manual.status_code == 201

    # V2-4: message-context selection validation (spec.md acceptance C.2/C.4, tasks.md T036)
    # Release one held conversation to free capacity, then create a fresh one
    # with two real customer messages (the operator endpoint used above only
    # creates OPERATOR-authored messages, not a second CUSTOMER message).
    release_third = client.post(f"/api/v1/operator/conversations/{active[2]['id']}/release", headers=headers)
    assert release_third.status_code == 200, release_third.text
    fresh = client.post("/api/v1/public/conversations")
    assert fresh.status_code == 201, fresh.text
    fresh_body = fresh.json()
    fresh_id = fresh_body["conversation"]["id"]
    fresh_customer_headers = {"Authorization": f"Bearer {fresh_body['access_token']}"}
    for body in ("Primeira mensagem sintética.", "Segunda mensagem sintética."):
        sent_customer_message = client.post(f"/api/v1/public/conversations/{fresh_id}/messages", headers=fresh_customer_headers, json={"body": body})
        assert sent_customer_message.status_code == 201, sent_customer_message.text
    claim_fresh = client.post(f"/api/v1/operator/conversations/{fresh_id}/claim", headers=headers)
    assert claim_fresh.status_code == 200, claim_fresh.text
    fresh_detail = client.get(f"/api/v1/operator/conversations/{fresh_id}", headers=headers).json()
    fresh_customer_ids = [item["id"] for item in fresh_detail["messages"] if item["author_type"] == "CUSTOMER"]
    assert len(fresh_customer_ids) == 2

    multi_select = client.post(f"/api/v1/operator/conversations/{fresh_id}/drafts", headers=headers, json={"selected_message_ids": fresh_customer_ids})
    assert multi_select.status_code == 201, multi_select.text
    assert set(multi_select.json()["selected_message_ids"]) == set(fresh_customer_ids)

    empty_selection = client.post(f"/api/v1/operator/conversations/{fresh_id}/drafts", headers=headers, json={"selected_message_ids": [], "manual_search_text": ""})
    assert empty_selection.status_code == 422 and empty_selection.json()["code"] == "EMPTY_SELECTION", empty_selection.text

    manual_text_only = client.post(f"/api/v1/operator/conversations/{fresh_id}/drafts", headers=headers, json={"selected_message_ids": [], "manual_search_text": "horário de atendimento"})
    assert manual_text_only.status_code == 201, manual_text_only.text
    assert manual_text_only.json()["selected_message_ids"] == []

    cross_conversation = client.post(f"/api/v1/operator/conversations/{fresh_id}/drafts", headers=headers, json={"selected_message_ids": [customer_message["id"]]})
    assert cross_conversation.status_code == 422 and cross_conversation.json()["code"] == "MESSAGE_NOT_IN_CONVERSATION", cross_conversation.text

    no_regenerate_route = client.post(f"/api/v1/operator/drafts/{draft['id']}/regenerate", headers=headers)
    assert no_regenerate_route.status_code == 404, "V2 removes the separate Regenerar endpoint (spec.md V2-7)"

    # V2-3: "Buscar evidências" — single evidence selection, independent of message context (T054, T057)
    search_results = client.post("/api/v1/operator/knowledge/search", headers=headers, json={"query": "horário de atendimento", "top_k": 8}).json()
    admin_hit = next((item for item in search_results["evidence"] if item["knowledge_type"] == "ADMIN_QA"), None)
    clinical_hit = next((item for item in search_results["evidence"] if item["knowledge_type"] == "CLINICAL"), None)
    assert admin_hit or clinical_hit, "expected at least one evidence item from manual search"

    if admin_hit:
        selected_qa = client.post(f"/api/v1/operator/knowledge/evidence/{admin_hit['retrieval_hit_id']}/select", headers=headers, json={"conversation_id": fresh_id})
        assert selected_qa.status_code == 201, selected_qa.text
        selected_qa_body = selected_qa.json()
        assert selected_qa_body["trigger"] == "MANUAL_EVIDENCE"
        assert selected_qa_body["selected_message_ids"] == [], "MANUAL_EVIDENCE must never populate message_selections"

    if clinical_hit:
        selected_clinical = client.post(f"/api/v1/operator/knowledge/evidence/{clinical_hit['retrieval_hit_id']}/select", headers=headers, json={"conversation_id": fresh_id})
        assert selected_clinical.status_code == 201, selected_clinical.text
        selected_clinical_body = selected_clinical.json()
        assert selected_clinical_body["model"] == "not-applicable", "clinical selection must never use LLM composition (spec.md V2-3)"
        assert selected_clinical_body["trigger"] == "MANUAL_EVIDENCE"
        assert selected_clinical_body["selected_message_ids"] == []

    # V2-6: a dynamic_data_required Q&A entry with a failing/unconfigured
    # binding must fall back safely through the HTTP API — never leak the
    # audit-only failure cause into the customer-facing response (T078).
    operator_id = client.get("/api/v1/operator/me", headers=headers).json()["id"]
    dynamic_qa_id = f"smoke-dynamic-{uuid4().hex[:8]}"
    with get_session_factory()() as db:
        qa = QAEntry(qa_id=dynamic_qa_id, category="smoke-fixture", question="Pergunta sintética dinâmica", answer_markdown="Vaga: {{slot}}", dynamic_data_required=True, customer_citation_allowed=False)
        db.add(qa)
        db.flush()  # qa_dynamic_bindings' FK requires qa_entries to exist first
        db.add(QADynamicBinding(qa_id=dynamic_qa_id, source_table="not_allowlisted_table", filter={}, output_columns=[{"column": "label", "variable_name": "slot"}], row_limit=4))
        run = RetrievalRun(operator_id=operator_id, purpose="N2_MANUAL_SEARCH", query_text="smoke", embedding_model="smoke", top_k=1, status="COMPLETED")
        db.add(run)
        db.flush()
        dynamic_hit = RetrievalHit(retrieval_run_id=run.id, matched_kind="ADMIN_QA", matched_qa_id=dynamic_qa_id, rank=1, score=1.0)
        db.add(dynamic_hit)
        db.commit()
        dynamic_hit_id = dynamic_hit.id
        dynamic_run_id = run.id
    try:
        selected_dynamic = client.post(f"/api/v1/operator/knowledge/evidence/{dynamic_hit_id}/select", headers=headers, json={"conversation_id": fresh_id})
        assert selected_dynamic.status_code == 201, selected_dynamic.text
        selected_dynamic_body = selected_dynamic.json()
        assert selected_dynamic_body["status"] == "ABSTAIN" and selected_dynamic_body["reason_code"] == "DYNAMIC_DATA_UNAVAILABLE"
        assert selected_dynamic_body["draft_text"] == ""
        assert "not_allowlisted_table" not in str(selected_dynamic_body), "audit-only cause must never reach the API response"
        assert selected_dynamic_body["dynamic_pattern_used"] is False
    finally:
        with get_session_factory()() as db:
            # Dependency order: generations/sources -> hits -> run -> binding -> qa.
            db.execute(delete(AIGenerationSource).where(AIGenerationSource.retrieval_hit_id == dynamic_hit_id))
            db.execute(delete(AIGeneration).where(AIGeneration.retrieval_run_id == dynamic_run_id))
            db.execute(delete(RetrievalHit).where(RetrievalHit.id == dynamic_hit_id))
            db.execute(delete(RetrievalRun).where(RetrievalRun.id == dynamic_run_id))
            db.execute(delete(QADynamicBinding).where(QADynamicBinding.qa_id == dynamic_qa_id))
            db.execute(delete(QAEntry).where(QAEntry.qa_id == dynamic_qa_id))
            db.commit()

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
