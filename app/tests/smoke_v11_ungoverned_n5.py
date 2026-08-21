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

        # --- D-043 (2026-08-21) regression: N5 delivers an already-grounded
        # ANSWER verbatim instead of discarding it for a fresh, evidence-free
        # LLM call. Governed kill switch is still off here (default state
        # from this script's own setup above) — a real production bug found
        # this exact combination (N5 on, governed off, a grounded ANSWER
        # with a category the operator never separately enabled for governed
        # autonomy) silently threw the grounded answer away every time.
        conv3 = client.post("/api/v1/public/conversations").json()
        conversation3_id = conv3["conversation"]["id"]
        customer3_headers = {"Authorization": f"Bearer {conv3['access_token']}"}
        sent3 = client.post(f"/api/v1/public/conversations/{conversation3_id}/messages", headers=customer3_headers, json={"body": COVERED_QUESTION})
        assert sent3.status_code == 201, sent3.text
        claimed3 = client.post(f"/api/v1/operator/conversations/{conversation3_id}/claim", headers=headers)
        assert claimed3.status_code == 200, claimed3.text

        def has_pending3() -> bool:
            detail = client.get(f"/api/v1/operator/conversations/{conversation3_id}", headers=headers)
            return detail.json().get("pending_autonomous_send") is not None

        pending3_appeared = _wait_for(has_pending3, timeout_seconds=40)
        assert pending3_appeared, "expected a pending_autonomous_send for a grounded, uncategorized-for-governed-autonomy question"
        before = client.get(f"/api/v1/operator/conversations/{conversation3_id}", headers=headers).json()
        pending3 = before["pending_autonomous_send"]
        assert pending3["mechanism"] == "ungoverned_n5", pending3
        original_generation = before["latest_generation"]
        assert original_generation["status"] == "ANSWER", original_generation
        assert pending3["draft_text"] == original_generation["draft_text"], "N5 must deliver the existing grounded draft verbatim, not a different one"

        def message3_sent_autonomously() -> bool:
            detail = client.get(f"/api/v1/operator/conversations/{conversation3_id}", headers=headers).json()
            return not detail.get("pending_autonomous_send") and any(m.get("autonomous_source") == "ungoverned_n5" for m in detail["messages"])

        resolved3 = _wait_for(message3_sent_autonomously, timeout_seconds=10)
        assert resolved3, "expected the pending window to resolve to an ungoverned_n5 autonomous send within 10s"
        after = client.get(f"/api/v1/operator/conversations/{conversation3_id}", headers=headers).json()
        # The decisive check: no *new* AIGeneration was manufactured — the
        # conversation's latest generation is still the exact same row that
        # existed before the window ever opened, never re-generated from
        # scratch with no evidence.
        assert after["latest_generation"]["id"] == original_generation["id"], (before, after)
        sent_message = next(m for m in after["messages"] if m.get("autonomous_source") == "ungoverned_n5")
        assert sent_message["source_generation_id"] == original_generation["id"], sent_message
        assert sent_message["body"] == original_generation["draft_text"], sent_message
        close3 = client.post(f"/api/v1/operator/conversations/{conversation3_id}/close", headers=headers)
        assert close3.status_code == 200, close3.text

        # --- D-043-2 (2026-08-21) regression: GB's (005) own slot-selection
        # output must still reach the customer under N5 with no operator
        # manually sending it — GB was designed (D-032) to always require
        # an explicit operator send, before N5 existed. Once booking_script
        # became unreachable (D-043), GB is the only real booking path, so
        # this gap left a customer who correctly picked a slot with no
        # reply at all.
        seeded = client.post("/api/v1/operator/scheduling/ensure-availability", headers=headers)
        assert seeded.status_code == 200, seeded.text
        conv4 = client.post("/api/v1/public/conversations").json()
        conversation4_id = conv4["conversation"]["id"]
        customer4_headers = {"Authorization": f"Bearer {conv4['access_token']}"}
        claimed4 = client.post(f"/api/v1/operator/conversations/{conversation4_id}/claim", headers=headers)
        assert claimed4.status_code == 200, claimed4.text
        sent4 = client.post(f"/api/v1/public/conversations/{conversation4_id}/messages", headers=customer4_headers, json={"body": "Preciso agendar uma consulta."})
        assert sent4.status_code == 201, sent4.text

        def offers_sent_autonomously() -> bool:
            detail = client.get(f"/api/v1/operator/conversations/{conversation4_id}", headers=headers).json()
            return not detail.get("pending_autonomous_send") and any(m.get("autonomous_source") == "ungoverned_n5" for m in detail["messages"])

        assert _wait_for(offers_sent_autonomously, timeout_seconds=45), "expected the initial offers draft to autonomously send within 45s"

        slot_msg = client.post(f"/api/v1/public/conversations/{conversation4_id}/messages", headers=customer4_headers, json={"body": "primeira opção"})
        assert slot_msg.status_code == 201, slot_msg.text

        def has_pending4_slot() -> bool:
            detail = client.get(f"/api/v1/operator/conversations/{conversation4_id}", headers=headers)
            return detail.json().get("pending_autonomous_send") is not None

        assert _wait_for(has_pending4_slot, timeout_seconds=40), "expected the GB slot-choice draft (trigger=GUIDED_SLOT_SELECTION) to become a pending N5 send — this is the exact bug report D-043-2 closes"
        pending4 = client.get(f"/api/v1/operator/conversations/{conversation4_id}", headers=headers).json()["pending_autonomous_send"]
        assert pending4["mechanism"] == "ungoverned_n5", pending4
        assert "Informe seu CPF" in pending4["draft_text"], pending4

        def slot_sent_autonomously() -> bool:
            detail = client.get(f"/api/v1/operator/conversations/{conversation4_id}", headers=headers).json()
            return not detail.get("pending_autonomous_send") and any(m.get("autonomous_source") == "ungoverned_n5" and "Informe seu CPF" in m.get("body", "") for m in detail["messages"])

        assert _wait_for(slot_sent_autonomously, timeout_seconds=10), "expected the GB slot-choice confirmation to autonomously send within 10s"
        close4 = client.post(f"/api/v1/operator/conversations/{conversation4_id}/close", headers=headers)
        assert close4.status_code == 200, close4.text

        # --- D-043-2 regression: a bare greeting must never autosend an
        # entire unrelated clinical document (real retrieval score ~0.31,
        # well below _AUTONOMOUS_CLINICAL_MIN_SCORE=0.40 — noise, not a
        # genuine match).
        conv5 = client.post("/api/v1/public/conversations").json()
        conversation5_id = conv5["conversation"]["id"]
        customer5_headers = {"Authorization": f"Bearer {conv5['access_token']}"}
        claimed5 = client.post(f"/api/v1/operator/conversations/{conversation5_id}/claim", headers=headers)
        assert claimed5.status_code == 200, claimed5.text
        sent5 = client.post(f"/api/v1/public/conversations/{conversation5_id}/messages", headers=customer5_headers, json={"body": "Oi"})
        assert sent5.status_code == 201, sent5.text

        def message5_sent_autonomously() -> bool:
            detail = client.get(f"/api/v1/operator/conversations/{conversation5_id}", headers=headers).json()
            return not detail.get("pending_autonomous_send") and any(m.get("autonomous_source") == "ungoverned_n5" for m in detail["messages"])

        assert _wait_for(message5_sent_autonomously, timeout_seconds=45), "expected a bare greeting to still autonomously send a reply within 45s — N5 must never leave the customer without one"
        final5 = client.get(f"/api/v1/operator/conversations/{conversation5_id}", headers=headers).json()
        greeting_message = next(m for m in final5["messages"] if m.get("autonomous_source") == "ungoverned_n5")
        assert not greeting_message["body"].lstrip().startswith("#"), f"a bare greeting must never autosend a full clinical document verbatim: {greeting_message['body'][:200]!r}"
        close5 = client.post(f"/api/v1/operator/conversations/{conversation5_id}/close", headers=headers)
        assert close5.status_code == 200, close5.text

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

    print("smoke_v11_ungoverned_n5_ok: n5_kill_switch_enabled/automatic_trigger_idle_seconds endpoints, uncovered question autonomous send (mechanism=ungoverned_n5) with governed switch off, category-matched question keeps mechanism=governed_autonomy with both switches on, D-043 grounded-answer-delivered-verbatim regression, D-043-2 GB-under-N5 and weak-clinical-match regressions")


if __name__ == "__main__":
    run()
