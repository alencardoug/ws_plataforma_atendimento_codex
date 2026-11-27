"""005: real end-to-end HTTP smoke for dynamic pricing (PL) and guided
booking selection (GB) against a rebuilt backend — real embeddings, zero
LLM calls for any resolved/guided generation, confirms genuine paraphrase
and ordinal-choice recognition (not just exact-text match, which the
deterministic-provider unit tests in test_guided_booking.py already
cover), the CPF-first flow (D-045), the "Voltar"
step-back-to-reselection flow (D-035), and confirms every GB output still
requires an explicit operator send.
specs/005-dynamic-pricing-and-guided-booking/tasks.md T045/T055,
acceptance.md, DECISIONS.md D-033/D-035."""

import os
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from customer_care.ai.providers import CLINICAL_DEFLECTION_TEXT
from customer_care.bootstrap import create_app
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import Message
from customer_care.scheduling.guided_booking import GB_CPF_INPUT_REDACTION


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

    # D-045 (2026-11-27): CPF before offers. The booking-intent message
    # still resolves availability, but the draft asks for the CPF; the
    # offers appear only after a valid CPF.
    availability_msg = send_customer("Existe consulta disponível essa semana?")
    availability_draft = draft_on(availability_msg["id"])
    assert availability_draft["dynamic_pattern_used"] is True, availability_draft
    assert availability_draft["evidence"][0]["title"] != "Quanto custa uma consulta de mastologia?", "query matched the price entry, not an availability one — retrieval ambiguity, not a GB bug"
    assert "informe seu CPF" in availability_draft["draft_text"], availability_draft
    assert "(simulação)" not in availability_draft["draft_text"], availability_draft
    operator_send(availability_draft)

    # Invalid CPF re-asks on its own trigger (still requires operator send).
    bad_cpf_msg = send_customer("Ah 123456a8910")
    bad_cpf_draft = draft_on(bad_cpf_msg["id"])
    assert bad_cpf_draft["trigger"] == "GUIDED_CPF_REQUEST", bad_cpf_draft
    assert bad_cpf_draft["draft_text"] == "CPF inválido. Informe um número válido de 11 dígitos.\n\nDigite Cancelar para desistir do agendamento.", bad_cpf_draft
    operator_send(bad_cpf_draft)

    # A valid CPF confirms and shows the numbered offers.
    cpf_msg = send_customer("tabom 123.456..789.10")
    cpf_draft = draft_on(cpf_msg["id"])
    assert cpf_draft["trigger"] == "GUIDED_CPF_CONFIRMED", cpf_draft
    assert cpf_draft["draft_text"].startswith("CPF 123.456.789-10 confirmado.\n\nEscolha um dos horários disponíveis:\n\n1. "), cpf_draft
    assert "2." in cpf_draft["draft_text"] and "(simulação)" in cpf_draft["draft_text"], cpf_draft
    operator_send(cpf_draft)

    # D-043 regression: a generic booking-intent phrase replying to the
    # offers must NOT let AA-10's booking_script hijack the flow. Drafted
    # only, never sent.
    hijack_probe_msg = send_customer("Quero agendar uma primeira consulta")
    detail_after_probe = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers).json()
    assert not any(m.get("autonomous_source") == "booking_script" for m in detail_after_probe["messages"]), detail_after_probe["messages"]
    draft_on(hijack_probe_msg["id"])

    # GB-3: an unrelated reply must NOT be misread as a slot choice.
    unrelated_msg = send_customer("Vocês têm estacionamento no local?")
    unrelated_draft = draft_on(unrelated_msg["id"])
    assert unrelated_draft["trigger"] != "GUIDED_SLOT_SELECTION", unrelated_draft

    # GB-2 (D-033): an ordinal reference resolves by position. D-045: the
    # slot choice now asks the payment question.
    choice_msg = send_customer("segunda opção")
    choice_draft = draft_on(choice_msg["id"])
    assert choice_draft["trigger"] == "GUIDED_SLOT_SELECTION", choice_draft
    assert choice_draft["model"] == "not-applicable", choice_draft
    assert "R$" in choice_draft["draft_text"], choice_draft
    assert "O valor foi pago? Responda sim ou não." in choice_draft["draft_text"], choice_draft
    assert "CPF" not in choice_draft["draft_text"], choice_draft
    assert choice_draft["draft_text"].startswith("Entendi que você escolheu:\n\n"), choice_draft
    assert choice_draft["draft_text"].endswith("Digite Voltar para escolher outro horário."), choice_draft
    operator_send(choice_draft)

    # D-035: "voltar" at the payment step re-presents the same offers.
    payment_back_msg = send_customer("quero voltar")
    payment_back_draft = draft_on(payment_back_msg["id"])
    assert payment_back_draft["trigger"] == "GUIDED_SLOT_RESELECTION", payment_back_draft
    assert "1." in payment_back_draft["draft_text"] and "2." in payment_back_draft["draft_text"], payment_back_draft
    operator_send(payment_back_draft)

    reselect_msg = send_customer("1")
    reselect_draft = draft_on(reselect_msg["id"])
    assert reselect_draft["trigger"] == "GUIDED_SLOT_SELECTION", reselect_draft
    operator_send(reselect_draft)

    # Negative payment reply re-asks, still draft-only.
    no_payment_msg = send_customer("Então, não paguei")
    no_payment_draft = draft_on(no_payment_msg["id"])
    assert no_payment_draft["draft_text"] == "O valor foi pago? Responda sim ou não.\n\nDigite Voltar para escolher outro horário.", no_payment_draft
    operator_send(no_payment_draft)

    # Affirmative reply completes the booking — same wording AA-10 itself uses.
    paid_msg = send_customer("tabom simm paguei")
    paid_draft = draft_on(paid_msg["id"])
    assert paid_draft["trigger"] == "GUIDED_BOOKING_COMPLETE", paid_draft
    assert paid_draft["draft_text"] == "Verificando pagamento. Pagamento verificado. Agendamento realizado com sucesso. Há algo mais que posso ajudar?", paid_draft
    detail_before_send = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers)
    assert detail_before_send.status_code == 200, detail_before_send.text
    operator_messages_before = [m for m in detail_before_send.json()["messages"] if m.get("author_type") == "OPERATOR"]
    assert paid_draft["draft_text"] not in [m["body"] for m in operator_messages_before], "GB output must never reach the customer without an explicit operator send"
    operator_send(paid_draft)

    # D-033 redaction (narrowed 2026-08-19, human decision): only the raw
    # CPF reply must never reach durable storage. The payment-confirmation
    # reply is deliberately kept verbatim — not sensitive the same way.
    with get_session_factory()() as db:
        bodies = [row.body for row in db.scalars(select(Message).where(Message.conversation_id == UUID(conversation_id))).all()]
        assert GB_CPF_INPUT_REDACTION in bodies, bodies
        for raw_cpf_input in ("Ah 123456a8910", "tabom 123.456..789.10"):
            assert raw_cpf_input not in bodies, bodies
        for raw_payment_input in ("Então, não paguei", "tabom simm paguei"):
            assert raw_payment_input in bodies, bodies
        # D-035/D-045: replies after the CPF step are not redacted.
        assert "quero voltar" in bodies, bodies
        assert "segunda opção" in bodies, bodies

    # Bug found 2026-08-19: after the booking flow completed, the *next*
    # customer message — even an unrelated clinical question — was still
    # matched against the same 4 old offers (latest_unconfirmed_offer_
    # generation_id never knew the set had already been acted on). Confirm
    # it now falls through to ordinary composition instead, and that the
    # clinical-question reranker (human decision, same day) then replaces
    # that ordinary answer with the fixed deflection text, since the top
    # retrieved evidence here is an unrelated scheduling Q&A entry.
    clinical_msg = send_customer("Em quanto tempo descubro se eu tenho câncer?")
    clinical_draft = draft_on(clinical_msg["id"])
    assert clinical_draft["trigger"] != "GUIDED_SLOT_SELECTION", clinical_draft
    assert clinical_draft["draft_text"] == CLINICAL_DEFLECTION_TEXT, clinical_draft

    close = client.post(f"/api/v1/operator/conversations/{conversation_id}/close", headers=headers)
    assert close.status_code == 200, close.text

    print("smoke_v5_guided_booking_ok: real price_lookup resolution, ordinal slot-choice recognition, CPF-first flow (D-045), zero LLM calls, redaction confirmed, every step draft-only, post-completion clinical deflection confirmed")


if __name__ == "__main__":
    run()
