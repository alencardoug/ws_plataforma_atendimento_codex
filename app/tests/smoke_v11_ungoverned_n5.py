"""011 (Constitution Amendment 1.3.0): real end-to-end HTTP smoke for
ungoverned fictional-demo autonomy (N5) — real LLM generation, a real
short veto window against a real clock (not mocked). Covers: the two new
autonomy-settings fields, a genuinely uncovered question (real embeddings
confirm no category match) still getting an autonomous reply with N5 on
and the governed (N3/N4) kill switch off, and that a category-matched
question still uses the governed mechanism (N5 adds no duplicate) when
both are on.
specs/011-ungoverned-fictional-demo-autonomy-n5/tasks.md T27, acceptance.md."""

import os
import time

from fastapi.testclient import TestClient

from customer_care.bootstrap import create_app

# Deliberately outside the knowledge base entirely — real retrieval must
# find nothing category-relevant, unlike smoke_v10's 'preparo' question.
UNCOVERED_QUESTION = "Qual a previsão do tempo para amanhã em Marte? (smoke v11)"
COVERED_QUESTION = "Preciso estar em jejum para a consulta?"


def _wait_for(predicate, timeout_seconds: float, interval_seconds: float = 1.0):
    deadline = time.monotonic() + timeout_seconds
    result = predicate()
    while not result and time.monotonic() < deadline:
        time.sleep(interval_seconds)
        result = predicate()
    return result


def run() -> None:
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/operator/login", json={"email": os.environ["SMOKE_OPERATOR_EMAIL"], "password": os.environ["SMOKE_OPERATOR_PASSWORD"]})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # --- Setup: short real window, N5 kill switch on, governed kill switch off ---
    settings = client.post("/api/v1/operator/autonomy-settings", headers=headers, json={"window_seconds": 3, "kill_switch_enabled": False, "n5_kill_switch_enabled": True, "automatic_trigger_idle_seconds": 8})
    assert settings.status_code == 200, settings.text
    assert settings.json()["n5_kill_switch_enabled"] is True
    assert settings.json()["automatic_trigger_idle_seconds"] == 8

    try:
        # --- N5-only path: uncovered question, governed kill switch off, still gets an autonomous reply ---
        conv = client.post("/api/v1/public/conversations").json()
        conversation_id = conv["conversation"]["id"]
        customer_headers = {"Authorization": f"Bearer {conv['access_token']}"}
        sent = client.post(f"/api/v1/public/conversations/{conversation_id}/messages", headers=customer_headers, json={"body": UNCOVERED_QUESTION})
        assert sent.status_code == 201, sent.text
        claimed = client.post(f"/api/v1/operator/conversations/{conversation_id}/claim", headers=headers)
        assert claimed.status_code == 200, claimed.text

        def has_pending() -> bool:
            detail = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers)
            assert detail.status_code == 200, detail.text
            return detail.json().get("pending_autonomous_send") is not None

        pending_appeared = _wait_for(has_pending, timeout_seconds=40)
        assert pending_appeared, "expected a pending_autonomous_send (mechanism=ungoverned_n5) within 40s of an uncovered question, N5 on"
        pending = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers).json()["pending_autonomous_send"]
        assert pending["mechanism"] == "ungoverned_n5", pending
        assert pending["category"] is None, pending

        def message_sent_autonomously() -> bool:
            detail = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers).json()
            return not detail.get("pending_autonomous_send") and any(m.get("autonomous_source") == "ungoverned_n5" for m in detail["messages"])

        resolved = _wait_for(message_sent_autonomously, timeout_seconds=10)
        assert resolved, "expected the pending window to resolve to an ungoverned_n5 autonomous send within 10s"
        final = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers).json()
        autonomous_messages = [m for m in final["messages"] if m.get("autonomous_source") == "ungoverned_n5"]
        assert len(autonomous_messages) == 1, final["messages"]
        assert autonomous_messages[0]["body"], "ungoverned autonomous message must not be empty"

        # --- N5 does not duplicate an already-grounded governed answer ---
        governed_on = client.post("/api/v1/operator/autonomy-settings", headers=headers, json={"kill_switch_enabled": True})
        assert governed_on.status_code == 200, governed_on.text
        category_on = client.post("/api/v1/operator/knowledge/categories/preparo/autonomy", headers=headers, json={"enabled": True})
        assert category_on.status_code == 200, category_on.text

        conv2 = client.post("/api/v1/public/conversations").json()
        conversation2_id = conv2["conversation"]["id"]
        customer2_headers = {"Authorization": f"Bearer {conv2['access_token']}"}
        sent2 = client.post(f"/api/v1/public/conversations/{conversation2_id}/messages", headers=customer2_headers, json={"body": COVERED_QUESTION})
        assert sent2.status_code == 201, sent2.text
        claimed2 = client.post(f"/api/v1/operator/conversations/{conversation2_id}/claim", headers=headers)
        assert claimed2.status_code == 200, claimed2.text

        def has_pending2() -> bool:
            detail = client.get(f"/api/v1/operator/conversations/{conversation2_id}", headers=headers)
            return detail.json().get("pending_autonomous_send") is not None

        pending2_appeared = _wait_for(has_pending2, timeout_seconds=40)
        assert pending2_appeared, "expected a pending_autonomous_send for the category-matched question"
        pending2 = client.get(f"/api/v1/operator/conversations/{conversation2_id}", headers=headers).json()["pending_autonomous_send"]
        assert pending2["mechanism"] == "governed_autonomy", pending2
        assert pending2["category"] == "preparo", pending2
    finally:
        client.post("/api/v1/operator/knowledge/categories/preparo/autonomy", headers=headers, json={"enabled": False})
        client.post("/api/v1/operator/autonomy-settings", headers=headers, json={"kill_switch_enabled": False, "n5_kill_switch_enabled": False, "window_seconds": 30, "automatic_trigger_idle_seconds": 8})

    print("smoke_v11_ungoverned_n5_ok: n5_kill_switch_enabled/automatic_trigger_idle_seconds endpoints, uncovered question autonomous send (mechanism=ungoverned_n5) with governed switch off, category-matched question keeps mechanism=governed_autonomy with both switches on")


if __name__ == "__main__":
    run()
