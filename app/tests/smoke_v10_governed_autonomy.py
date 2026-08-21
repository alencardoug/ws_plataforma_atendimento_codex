"""010 (Constitution Amendment 1.2.0): real end-to-end HTTP smoke for
governed autonomous response — real embeddings, real LLM generation, a
real short veto window against a real clock (not mocked). Covers the
full lifecycle: category policy + kill switch + window-duration
endpoints, an eligible AUTOMATIC/ANSWER generation opening a window, the
window elapsing and sending autonomously with the correct provenance,
PAUSE cancelling one send without touching the category's own policy,
and GA-6's unclaimed-conversation path.
specs/010-governed-autonomous-response/tasks.md T27, acceptance.md."""

import os
import time

from fastapi.testclient import TestClient

from customer_care.bootstrap import create_app

# 'preparo', not 'agenda': found live that "agenda"'s real content is tied
# to appointment-availability offer presentation, which sweeps the *next*
# customer message into guided-booking's own slot-choice interpretation
# instead of a normal category-gated generation — a real, interesting
# cross-package interaction, but not what this test is exercising.
# 'preparo' has plain informational (dynamic_data_required=false) content.
QUESTION = "Preciso estar em jejum para a consulta?"


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

    # --- Setup: short real window, kill switch on, 'preparo' category on ---
    settings = client.post("/api/v1/operator/autonomy-settings", headers=headers, json={"window_seconds": 3, "kill_switch_enabled": True})
    assert settings.status_code == 200, settings.text
    assert settings.json()["window_seconds"] == 3
    assert settings.json()["kill_switch_enabled"] is True
    category_on = client.post("/api/v1/operator/knowledge/categories/preparo/autonomy", headers=headers, json={"enabled": True})
    assert category_on.status_code == 200, category_on.text
    assert category_on.json()["autonomy_enabled"] is True

    try:
        # --- Claimed-conversation path: window opens, elapses, sends autonomously ---
        conv = client.post("/api/v1/public/conversations").json()
        conversation_id = conv["conversation"]["id"]
        customer_headers = {"Authorization": f"Bearer {conv['access_token']}"}
        sent = client.post(f"/api/v1/public/conversations/{conversation_id}/messages", headers=customer_headers, json={"body": QUESTION})
        assert sent.status_code == 201, sent.text
        claimed = client.post(f"/api/v1/operator/conversations/{conversation_id}/claim", headers=headers)
        assert claimed.status_code == 200, claimed.text

        # V2-7's 8s idle debounce, plus real generation latency, plus the
        # 3s window itself — a generous real-clock budget, not mocked.
        def has_pending() -> bool:
            detail = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers)
            assert detail.status_code == 200, detail.text
            return detail.json().get("pending_autonomous_send") is not None

        pending_appeared = _wait_for(has_pending, timeout_seconds=40)
        assert pending_appeared, "expected a pending_autonomous_send to appear within 40s of claiming an eligible conversation"
        detail = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers).json()
        assert detail["pending_autonomous_send"]["category"] == "preparo", detail["pending_autonomous_send"]

        def message_sent_autonomously() -> bool:
            detail = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers).json()
            return not detail.get("pending_autonomous_send") and any(m.get("autonomous_source") == "governed_autonomy" for m in detail["messages"])

        resolved = _wait_for(message_sent_autonomously, timeout_seconds=10)
        assert resolved, "expected the pending window to resolve to an autonomous send within 10s of the 3s window opening"
        final = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers).json()
        autonomous_messages = [m for m in final["messages"] if m.get("autonomous_source") == "governed_autonomy"]
        assert len(autonomous_messages) == 1, final["messages"]
        assert autonomous_messages[0]["body"], "autonomous message must not be empty"

        # --- PAUSE: cancels one send, category policy untouched ---
        sent2 = client.post(f"/api/v1/public/conversations/{conversation_id}/messages", headers=customer_headers, json={"body": QUESTION + " (segunda vez)"})
        assert sent2.status_code == 201, sent2.text
        pending2_appeared = _wait_for(has_pending, timeout_seconds=40)
        assert pending2_appeared, "expected a second pending_autonomous_send after a second eligible message"
        pending_id = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers).json()["pending_autonomous_send"]["id"]
        paused = client.post(f"/api/v1/operator/conversations/{conversation_id}/pending-autonomous-send/{pending_id}/pause", headers=headers)
        assert paused.status_code == 200, paused.text
        assert paused.json()["status"] == "PAUSED"
        time.sleep(4)  # past the 3s window — must NOT have sent
        after_pause = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers).json()
        assert after_pause.get("pending_autonomous_send") is None
        assert len([m for m in after_pause["messages"] if m.get("autonomous_source") == "governed_autonomy"]) == 1, "PAUSE must not have let the second message send autonomously"
        category_still_on = client.get("/api/v1/operator/knowledge/categories", headers=headers).json()
        preparo = next(c for c in category_still_on if c["slug"] == "preparo")
        assert preparo["autonomy_enabled"] is True, "PAUSE must not change the category's own policy"

        # --- GA-6: unclaimed conversation, kill switch/category still on ---
        conv2 = client.post("/api/v1/public/conversations").json()
        conversation2_id = conv2["conversation"]["id"]
        customer2_headers = {"Authorization": f"Bearer {conv2['access_token']}"}
        sent3 = client.post(f"/api/v1/public/conversations/{conversation2_id}/messages", headers=customer2_headers, json={"body": QUESTION})
        assert sent3.status_code == 201, sent3.text

        def unclaimed_resolved() -> bool:
            queue = client.get("/api/v1/operator/conversations?scope=waiting", headers=headers).json()
            row = next((c for c in queue if c["id"] == conversation2_id), None)
            return row is not None and row["status"] == "WAITING" and row.get("pending_autonomous_send") is None

        # Never claimed — list_conversations() itself is what evaluates
        # and resolves GA-6's trigger, so polling the queue (not the
        # per-conversation detail endpoint, which requires an assignment)
        # is what drives this.
        for _ in range(40):
            queue = client.get("/api/v1/operator/conversations?scope=all", headers=headers).json()
            row = next((c for c in queue if c["id"] == conversation2_id), None)
            if row and (row.get("pending_autonomous_send") or row["status"] != "WAITING"):
                break
            time.sleep(1)
        else:
            raise AssertionError("expected GA-6's unclaimed trigger to produce a pending send within 40s")
        row = next(c for c in client.get("/api/v1/operator/conversations?scope=all", headers=headers).json() if c["id"] == conversation2_id)
        assert row["status"] == "WAITING", "an autonomous send must never change status away from WAITING"
        time.sleep(4)
        row_after = next(c for c in client.get("/api/v1/operator/conversations?scope=all", headers=headers).json() if c["id"] == conversation2_id)
        assert row_after["status"] == "WAITING", "status must remain WAITING even after the autonomous send resolves"
        assert row_after.get("pending_autonomous_send") is None
    finally:
        client.post("/api/v1/operator/knowledge/categories/preparo/autonomy", headers=headers, json={"enabled": False})
        client.post("/api/v1/operator/autonomy-settings", headers=headers, json={"kill_switch_enabled": False, "window_seconds": 30})

    print("smoke_v10_governed_autonomy_ok: category+kill-switch+window endpoints, eligible window open/elapse/autonomous-send, PAUSE without touching category policy, GA-6 unclaimed send preserving WAITING status")


if __name__ == "__main__":
    run()
