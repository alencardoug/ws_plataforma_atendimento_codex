"""Optional paid smoke using configured OpenAI embedding and generation models."""

import os
from fastapi.testclient import TestClient

from customer_care.bootstrap import create_app


def run() -> None:
    client = TestClient(create_app())
    created = client.post("/api/v1/public/conversations")
    assert created.status_code == 201, created.text
    public = created.json()
    conversation_id = public["conversation"]["id"]
    customer_headers = {"Authorization": f"Bearer {public['access_token']}"}
    question = client.post(
        f"/api/v1/public/conversations/{conversation_id}/messages",
        headers=customer_headers,
        json={"body": "Quais cuidados devo ter com o dreno depois de uma cirurgia de mama?"},
    )
    assert question.status_code == 201, question.text
    login = client.post(
        "/api/v1/auth/operator/login",
        json={"email": os.environ["SMOKE_OPERATOR_EMAIL"], "password": os.environ["SMOKE_OPERATOR_PASSWORD"]},
    )
    assert login.status_code == 200, login.text
    operator_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    claim = client.post(f"/api/v1/operator/conversations/{conversation_id}/claim", headers=operator_headers)
    assert claim.status_code == 200, claim.text
    draft = client.post(
        f"/api/v1/operator/conversations/{conversation_id}/drafts",
        headers=operator_headers,
        json={"triggering_message_id": question.json()["id"]},
    )
    assert draft.status_code == 201, draft.text
    generated = draft.json()
    before_send = client.get(f"/api/v1/public/conversations/{conversation_id}", headers=customer_headers).json()
    assert len(before_send["messages"]) == 1
    citation = next((item["retrieval_hit_id"] for item in generated["evidence"] if item["knowledge_type"] == "CLINICAL" and item["customer_citation_allowed"]), None)
    sent = client.post(
        f"/api/v1/operator/conversations/{conversation_id}/messages",
        headers=operator_headers,
        json={"body": generated["draft_text"], "source_generation_id": generated["id"], "citation_retrieval_hit_ids": [citation] if citation else []},
    )
    assert sent.status_code == 201, sent.text
    after_send = client.get(f"/api/v1/public/conversations/{conversation_id}", headers=customer_headers).json()
    assert len(after_send["messages"]) == 2
    assert after_send["messages"][-1]["author_type"] == "OPERATOR"
    print({"real_provider_smoke": "ok", "generation_status": generated["status"], "evidence_count": len(generated["evidence"]), "citation_count": len(sent.json()["citations"])})


if __name__ == "__main__":
    run()
