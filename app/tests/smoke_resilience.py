"""Executable N1 feature-flag and provider-failure/manual-fallback smoke."""

import os

from fastapi.testclient import TestClient

import customer_care.ai.router as ai_router
from customer_care.bootstrap import create_app
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import AIGeneration, Conversation


def run() -> None:
    client = TestClient(create_app())
    login = client.post(
        "/api/v1/auth/operator/login",
        json={"email": os.environ["SMOKE_OPERATOR_EMAIL"], "password": os.environ["SMOKE_OPERATOR_PASSWORD"]},
    )
    assert login.status_code == 200, login.text
    operator_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    created = client.post("/api/v1/public/conversations").json()
    conversation_id = created["conversation"]["id"]
    customer_headers = {"Authorization": f"Bearer {created['access_token']}"}
    customer_message = client.post(
        f"/api/v1/public/conversations/{conversation_id}/messages",
        headers=customer_headers,
        json={"body": "Pergunta sintética para atendimento manual"},
    )
    claimed = client.post(f"/api/v1/operator/conversations/{conversation_id}/claim", headers=operator_headers)
    assert claimed.status_code == 200, claimed.text

    search_response = client.post(
        "/api/v1/operator/knowledge/search",
        headers=operator_headers,
        json={"query": "horário", "conversation_id": conversation_id},
    )
    if os.getenv("SMOKE_EXPECT_SEARCH_ENABLED") == "true":
        assert search_response.status_code == 200 and search_response.json()["evidence"], search_response.text
        admin = next((item for item in search_response.json()["evidence"] if item["knowledge_type"] == "ADMIN_QA"), None)
        if admin:
            assert "matched_child_excerpt" not in admin or admin["matched_child_excerpt"] is None
    else:
        assert search_response.status_code == 403 and search_response.json()["code"] == "N1_SEARCH_DISABLED", search_response.text
    manual_n1 = client.post(
        f"/api/v1/operator/conversations/{conversation_id}/messages",
        headers=operator_headers,
        json={"body": "Resposta manual N1 disponível."},
    )
    assert manual_n1.status_code == 201, manual_n1.text

    with get_session_factory()() as db:
        conversation = db.get(Conversation, conversation_id)
        assert conversation is not None
        conversation.initial_mode = "N2"
        conversation.effective_mode = "N2"
        db.commit()

    def unavailable_provider():
        raise RuntimeError("synthetic provider outage")

    ai_router.configured_generation_provider = unavailable_provider
    failed_draft = client.post(
        f"/api/v1/operator/conversations/{conversation_id}/drafts",
        headers=operator_headers,
        json={"triggering_message_id": customer_message.json()["id"]},
    )
    assert failed_draft.status_code == 503 and failed_draft.json()["code"] == "AI_PROVIDER_UNAVAILABLE", failed_draft.text
    manual_after_failure = client.post(
        f"/api/v1/operator/conversations/{conversation_id}/messages",
        headers=operator_headers,
        json={"body": "Resposta manual após indisponibilidade da IA."},
    )
    assert manual_after_failure.status_code == 201, manual_after_failure.text
    with get_session_factory()() as db:
        generations = db.query(AIGeneration).filter(AIGeneration.conversation_id == conversation_id).all()
        assert len(generations) == 1 and generations[0].status == "FAILED"

    print("resilience_smoke_ok: N1 search flag, N1 manual send, provider failure, manual fallback")


if __name__ == "__main__":
    run()
