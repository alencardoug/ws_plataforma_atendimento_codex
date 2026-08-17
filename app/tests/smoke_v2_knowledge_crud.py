"""Executable V2-8 knowledge-base CRUD smoke: create/read/update/deactivate
for Q&A and clinical parent/child, idempotent re-embedding, and
authorization (T089-T090)."""

import os

from fastapi.testclient import TestClient
from sqlalchemy import select

from customer_care.bootstrap import create_app
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import AuditEvent, QAEntry


def run() -> None:
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/operator/login", json={"email": os.environ["SMOKE_OPERATOR_EMAIL"], "password": os.environ["SMOKE_OPERATOR_PASSWORD"]})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Authorization: no operator credential reaches these routes.
    anon = client.get("/api/v1/operator/knowledge/qa")
    assert anon.status_code == 401, anon.text
    public = client.post("/api/v1/public/conversations").json()
    customer_headers = {"Authorization": f"Bearer {public['access_token']}"}
    customer_attempt = client.get("/api/v1/operator/knowledge/qa", headers=customer_headers)
    assert customer_attempt.status_code == 401, customer_attempt.text

    # --- Q&A CRUD ---
    # Write-time allowlist validation (data-model.md §6): a non-allowlisted
    # source_table is rejected at creation with a 422, not silently accepted
    # to fail later as a generic ABSTAIN at generation time.
    rejected_binding = client.post("/api/v1/operator/knowledge/qa", headers=headers, json={
        "category": "smoke-fixture",
        "question": "Pergunta com tabela inválida",
        "answer_markdown": "Resposta {{slot}}.",
        "dynamic_binding": {"source_table": "not_allowlisted_table", "output_columns": [{"column": "label", "variable_name": "slot"}]},
    })
    assert rejected_binding.status_code == 422 and rejected_binding.json()["code"] == "INVALID_DYNAMIC_BINDING", rejected_binding.text
    rejected_column = client.post("/api/v1/operator/knowledge/qa", headers=headers, json={
        "category": "smoke-fixture",
        "question": "Pergunta com coluna inválida",
        "answer_markdown": "Resposta {{slot}}.",
        "dynamic_binding": {"source_table": "knowledge_dynamic_fixture", "output_columns": [{"column": "not_a_real_column", "variable_name": "slot"}]},
    })
    assert rejected_column.status_code == 422 and rejected_column.json()["code"] == "INVALID_DYNAMIC_BINDING", rejected_column.text

    created = client.post("/api/v1/operator/knowledge/qa", headers=headers, json={
        "category": "smoke-fixture",
        "question": "Pergunta sintética de CRUD",
        "answer_markdown": "Resposta original.",
        "customer_citation_allowed": False,
        "dynamic_binding": {"source_table": "knowledge_dynamic_fixture", "filter": {"category": "smoke-crud"}, "output_columns": [{"column": "label", "variable_name": "slot"}], "row_limit": 2},
    })
    assert created.status_code == 201, created.text
    qa_id = created.json()["qa_id"]
    assert created.json()["dynamic_binding"]["source_table"] == "knowledge_dynamic_fixture"

    fetched = client.get(f"/api/v1/operator/knowledge/qa/{qa_id}", headers=headers)
    assert fetched.status_code == 200 and fetched.json()["answer_markdown"] == "Resposta original."

    listed = client.get("/api/v1/operator/knowledge/qa", headers=headers)
    assert any(item["qa_id"] == qa_id for item in listed.json())

    with get_session_factory()() as db:
        embedded_before = db.get(QAEntry, qa_id).embedded_at

    # No-op update (identical content): must not re-embed (T090 idempotency).
    noop_update = client.patch(f"/api/v1/operator/knowledge/qa/{qa_id}", headers=headers, json={"answer_markdown": "Resposta original."})
    assert noop_update.status_code == 200, noop_update.text
    with get_session_factory()() as db:
        embedded_after_noop = db.get(QAEntry, qa_id).embedded_at
    assert embedded_after_noop == embedded_before, "identical content must not trigger re-embedding"

    # Real content change: must re-embed.
    real_update = client.patch(f"/api/v1/operator/knowledge/qa/{qa_id}", headers=headers, json={"answer_markdown": "Resposta atualizada."})
    assert real_update.status_code == 200 and real_update.json()["answer_markdown"] == "Resposta atualizada."
    with get_session_factory()() as db:
        embedded_after_change = db.get(QAEntry, qa_id).embedded_at
    assert embedded_after_change != embedded_before, "changed content must trigger re-embedding"

    deactivated = client.delete(f"/api/v1/operator/knowledge/qa/{qa_id}", headers=headers)
    assert deactivated.status_code == 204, deactivated.text
    listed_after = client.get("/api/v1/operator/knowledge/qa", headers=headers)
    assert not any(item["qa_id"] == qa_id for item in listed_after.json()), "deactivated entries must not appear in the default listing"
    still_fetchable = client.get(f"/api/v1/operator/knowledge/qa/{qa_id}", headers=headers)
    assert still_fetchable.status_code == 200 and still_fetchable.json()["is_active"] is False

    # --- Clinical document + chunk CRUD ---
    document = client.post("/api/v1/operator/knowledge/clinical-documents", headers=headers, json={"title": "Documento sintético de CRUD", "content_markdown": "Conteúdo do documento-pai."})
    assert document.status_code == 201, document.text
    document_id = document.json()["document_id"]

    chunk = client.post(f"/api/v1/operator/knowledge/clinical-documents/{document_id}/chunks", headers=headers, json={"ordinal": 1, "heading": "Seção 1", "content_markdown": "Conteúdo do filho."})
    assert chunk.status_code == 201, chunk.text
    chunk_id = chunk.json()["chunk_id"]

    duplicate_ordinal = client.post(f"/api/v1/operator/knowledge/clinical-documents/{document_id}/chunks", headers=headers, json={"ordinal": 1, "content_markdown": "Duplicado."})
    assert duplicate_ordinal.status_code == 422, duplicate_ordinal.text

    updated_chunk = client.patch(f"/api/v1/operator/knowledge/clinical-documents/{document_id}/chunks/{chunk_id}", headers=headers, json={"content_markdown": "Conteúdo atualizado do filho."})
    assert updated_chunk.status_code == 200 and updated_chunk.json()["content_markdown"] == "Conteúdo atualizado do filho."

    deactivated_chunk = client.delete(f"/api/v1/operator/knowledge/clinical-documents/{document_id}/chunks/{chunk_id}", headers=headers)
    assert deactivated_chunk.status_code == 204

    deactivated_document = client.delete(f"/api/v1/operator/knowledge/clinical-documents/{document_id}", headers=headers)
    assert deactivated_document.status_code == 204

    with get_session_factory()() as db:
        event_types = set(db.scalars(select(AuditEvent.event_type)).all())
        assert {"knowledge.qa_created", "knowledge.qa_updated", "knowledge.qa_deactivated", "knowledge.clinical_document_created", "knowledge.clinical_document_deactivated", "knowledge.clinical_chunk_created", "knowledge.clinical_chunk_updated", "knowledge.clinical_chunk_deactivated"} <= event_types

    print("v2_knowledge_crud_smoke_ok: create/read/update/deactivate, idempotent re-embed, authorization, audit coverage")


if __name__ == "__main__":
    run()
