"""005: real end-to-end HTTP smoke for dynamic pricing (PL) and guided
booking selection (GB) against a rebuilt backend — real embeddings, zero
LLM calls for any resolved/guided generation, confirms genuine paraphrase
recognition (not just exact-text match, which the deterministic-provider
unit tests in test_guided_booking.py already cover), and confirms every
guided-selection/confirmation output still requires an explicit operator
send. specs/005-dynamic-pricing-and-guided-booking/tasks.md T045/T055,
acceptance.md."""

import os

from fastapi.testclient import TestClient

from customer_care.bootstrap import create_app


def run() -> None:
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/operator/login", json={"email": os.environ["SMOKE_OPERATOR_EMAIL"], "password": os.environ["SMOKE_OPERATOR_PASSWORD"]})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    seeded = client.post("/api/v1/operator/scheduling/ensure-availability", headers=headers)
    assert seeded.status_code == 200, seeded.text

    # --- PL: price_lookup resolves for real, no LLM ------------------------
    price_conv = client.post("/api/v1/public/conversations")
    assert price_conv.status_code == 201, price_conv.text
    price_conversation_id = price_conv.json()["conversation"]["id"]
    price_customer_headers = {"Authorization": f"Bearer {price_conv.json()['access_token']}"}
    claim = client.post(f"/api/v1/operator/conversations/{price_conversation_id}/claim", headers=headers)
    assert claim.status_code == 200, claim.text
    price_msg = client.post(f"/api/v1/public/conversations/{price_conversation_id}/messages", headers=price_customer_headers, json={"body": "Quanto custa uma consulta de mastologia?"})
    assert price_msg.status_code == 201, price_msg.text
    price_draft = client.post(f"/api/v1/operator/conversations/{price_conversation_id}/drafts", headers=headers, json={"selected_message_ids": [price_msg.json()["id"]]})
    assert price_draft.status_code == 201, price_draft.text
    price_body = price_draft.json()
    assert price_body["dynamic_pattern_used"] is True, price_body
    assert price_body["model"] == "not-applicable", price_body
    assert "R$" in price_body["draft_text"] and "(simulação)" in price_body["draft_text"], price_body
    close = client.post(f"/api/v1/operator/conversations/{price_conversation_id}/close", headers=headers)
    assert close.status_code == 200, close.text

    # --- GB: guided slot selection + confirmation, real paraphrases --------
    conversation = client.post("/api/v1/public/conversations")
    assert conversation.status_code == 201, conversation.text
    conversation_id = conversation.json()["conversation"]["id"]
    customer_headers = {"Authorization": f"Bearer {conversation.json()['access_token']}"}
    claim = client.post(f"/api/v1/operator/conversations/{conversation_id}/claim", headers=headers)
    assert claim.status_code == 200, claim.text

    def send_customer(body: str) -> dict:
        response = client.post(f"/api/v1/public/conversations/{conversation_id}/messages", headers=customer_headers, json={"body": body})
        assert response.status_code == 201, response.text
        return response.json()

    def draft_on(message_id: str) -> dict:
        response = client.post(f"/api/v1/operator/conversations/{conversation_id}/drafts", headers=headers, json={"selected_message_ids": [message_id]})
        assert response.status_code == 201, response.text
        return response.json()

    def operator_send(generation: dict) -> None:
        response = client.post(f"/api/v1/operator/conversations/{conversation_id}/messages", headers=headers, json={"body": generation["draft_text"], "source_generation_id": generation["id"]})
        assert response.status_code == 201, response.text

    availability_msg = send_customer("Existe consulta disponível essa semana?")
    availability_draft = draft_on(availability_msg["id"])
    assert availability_draft["dynamic_pattern_used"] is True, availability_draft
    assert "(simulação)" in availability_draft["draft_text"], availability_draft
    assert availability_draft["evidence"][0]["title"] != "Quanto custa uma consulta de mastologia?", "query matched the price entry, not an availability one — retrieval ambiguity, not a GB bug"
    operator_send(availability_draft)

    # GB-3 first: an unrelated reply must NOT be misread as a slot choice.
    unrelated_msg = send_customer("Vocês têm estacionamento no local?")
    unrelated_draft = draft_on(unrelated_msg["id"])
    assert unrelated_draft["trigger"] != "GUIDED_SLOT_SELECTION", unrelated_draft

    # GB-2: a real paraphrase (not the offer's own exact text) — all AA-9
    # seeded generalist slots are 08:00 morning appointments, so "the
    # morning one" is a genuine paraphrase of any offered slot without
    # hardcoding which exact weekday got seeded this run.
    choice_msg = send_customer("Pode ser aquele horário de manhã mesmo, o primeiro que vocês tiverem")
    choice_draft = draft_on(choice_msg["id"])
    assert choice_draft["trigger"] == "GUIDED_SLOT_SELECTION", choice_draft
    assert choice_draft["model"] == "not-applicable", choice_draft
    assert "Deseja que eu confirme o agendamento?" in choice_draft["draft_text"], choice_draft
    operator_send(choice_draft)

    # GB-4: a real varied affirmative phrasing (not literally "sim").
    confirm_msg = send_customer("Pode confirmar sim, por favor")
    confirm_draft = draft_on(confirm_msg["id"])
    assert confirm_draft["trigger"] == "GUIDED_CONFIRMATION", confirm_draft
    assert confirm_draft["draft_text"] == "Perfeito, entendido! Pode me confirmar que deseja seguir com esse agendamento?", confirm_draft
    # GB-5: still just a draft — nothing was sent to the customer automatically.
    detail_before_send = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers)
    assert detail_before_send.status_code == 200, detail_before_send.text
    operator_messages_before = [m for m in detail_before_send.json()["messages"] if m.get("author_type") == "OPERATOR"]
    assert confirm_draft["draft_text"] not in [m["body"] for m in operator_messages_before], "GB-4 output must never reach the customer without an explicit operator send"

    close = client.post(f"/api/v1/operator/conversations/{conversation_id}/close", headers=headers)
    assert close.status_code == 200, close.text

    print("smoke_v5_guided_booking_ok: real price_lookup resolution, real-paraphrase slot-choice and confirmation-intent recognition, zero LLM calls, GB-4 output confirmed draft-only")


if __name__ == "__main__":
    run()
