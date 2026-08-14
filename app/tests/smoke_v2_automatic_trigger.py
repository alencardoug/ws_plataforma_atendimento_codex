"""Executable V2-7 automatic/instant draft trigger smoke (typing debounce)."""

import os
import time

from fastapi.testclient import TestClient

from customer_care.bootstrap import create_app
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import AIGeneration, MessageSelection

IDLE_WAIT_SECONDS = 9.0  # just past the 8-second server-side debounce


def run() -> None:
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/operator/login", json={"email": os.environ["SMOKE_OPERATOR_EMAIL"], "password": os.environ["SMOKE_OPERATOR_PASSWORD"]})
    assert login.status_code == 200, login.text
    operator_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    created = client.post("/api/v1/public/conversations")
    assert created.status_code == 201, created.text
    public = created.json()
    conversation_id = public["conversation"]["id"]
    customer_headers = {"Authorization": f"Bearer {public['access_token']}"}

    claim = client.post(f"/api/v1/operator/conversations/{conversation_id}/claim", headers=operator_headers)
    assert claim.status_code == 200, claim.text

    first_burst = ["Primeira mensagem da rajada.", "Segunda mensagem da rajada."]
    for body in first_burst:
        sent = client.post(f"/api/v1/public/conversations/{conversation_id}/messages", headers=customer_headers, json={"body": body})
        assert sent.status_code == 201, sent.text

    heartbeat = client.post(f"/api/v1/public/conversations/{conversation_id}/typing", headers=customer_headers)
    assert heartbeat.status_code == 204, heartbeat.text

    detail_while_typing = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=operator_headers).json()
    assert detail_while_typing["is_customer_typing"] is True
    assert detail_while_typing["latest_generation"] is None, "must not fire while typing activity is recent"

    time.sleep(IDLE_WAIT_SECONDS)

    after_idle = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=operator_headers).json()
    assert after_idle["is_customer_typing"] is False
    first_generation = after_idle["latest_generation"]
    assert first_generation is not None, "automatic trigger must fire after 8s idle"
    assert first_generation["trigger"] == "AUTOMATIC"
    assert set(first_generation["selected_message_ids"]) == {
        item["id"] for item in after_idle["messages"] if item["body"] in first_burst
    }

    # Polling again immediately (same activity run) must not create a duplicate.
    again = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=operator_headers).json()
    assert again["latest_generation"]["id"] == first_generation["id"], "must fire once per activity run, not once per poll"

    # Second burst: two more customer messages, then idle again — the next
    # automatic generation must cover the accumulated run since the last
    # operator reply (all four messages), not just the new two.
    second_burst = ["Terceira mensagem.", "Quarta mensagem."]
    for body in second_burst:
        sent = client.post(f"/api/v1/public/conversations/{conversation_id}/messages", headers=customer_headers, json={"body": body})
        assert sent.status_code == 201, sent.text
    time.sleep(IDLE_WAIT_SECONDS)

    after_second_idle = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=operator_headers).json()
    second_generation = after_second_idle["latest_generation"]
    assert second_generation is not None and second_generation["id"] != first_generation["id"]
    assert second_generation["trigger"] == "AUTOMATIC"
    assert set(second_generation["selected_message_ids"]) == {
        item["id"] for item in after_second_idle["messages"] if item["body"] in (*first_burst, *second_burst)
    }, "accumulated run must cover all four messages since the last operator reply"

    # No token-by-token streaming: the response is one complete JSON object.
    assert isinstance(second_generation["draft_text"], str)

    with get_session_factory()() as db:
        generations = db.query(AIGeneration).filter(AIGeneration.conversation_id == conversation_id, AIGeneration.trigger == "AUTOMATIC").all()
        assert len(generations) == 2, "exactly two automatic generations, one per activity run"
        selections = db.query(MessageSelection).filter(MessageSelection.ai_generation_id == second_generation["id"]).all()
        assert len(selections) == 4

    print("v2_automatic_trigger_smoke_ok: typing debounce, single-fire-per-run, accumulated context, no streaming")


if __name__ == "__main__":
    run()
