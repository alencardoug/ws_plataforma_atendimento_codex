"""005: real end-to-end HTTP smoke for dynamic pricing (PL) and guided
booking selection (GB) against a rebuilt backend — real embeddings, zero
LLM calls for any resolved/guided generation, confirms genuine paraphrase
and ordinal-choice recognition (not just exact-text match, which the
deterministic-provider unit tests in test_guided_booking.py already
cover), the full direct-to-CPF/payment flow (D-033), the "Voltar"
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

    availability_msg = send_customer("Existe consulta disponível essa semana?")
    availability_draft = draft_on(availability_msg["id"])
    assert availability_draft["dynamic_pattern_used"] is True, availability_draft
    assert "(simulação)" in availability_draft["draft_text"], availability_draft
    assert availability_draft["evidence"][0]["title"] != "Quanto custa uma consulta de mastologia?", "query matched the price entry, not an availability one — retrieval ambiguity, not a GB bug"
    operator_send(availability_draft)

    # D-043 (2026-08-21) regression: a generic booking-intent phrase
    # replying to the offers themselves — never picking a specific slot —
    # must NOT let AA-10's booking_script hijack the flow ahead of GB's
    # own slot-choice interpretation. This is the exact bug report this
    # fix closes: "Quero agendar uma primeira consulta" produced an
    # autonomous "Agendamento realizado" completely out of flow, before
    # any slot had been chosen. It's still routed to GB's own drafting
    # path (real embedding similarity may or may not read this generic
    # reply as picking a specific offer — that ambiguity is GB's existing,
    # pre-011 design tolerance, always paired with "Digite Voltar", not
    # part of this fix) — only never to AA-10's own unconditional script.
    hijack_probe_msg = send_customer("Quero agendar uma primeira consulta")
    detail_after_probe = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers).json()
    assert not any(m.get("autonomous_source") == "booking_script" for m in detail_after_probe["messages"]), detail_after_probe["messages"]
    draft_on(hijack_probe_msg["id"])
    # Never sent (like GB-3's own unrelated_draft below) — drafting it is
    # enough to prove no booking_script side effect happened; sending it
    # would pollute the offer set the ordinal-choice steps below rely on.

    # GB-3 first: an unrelated reply must NOT be misread as a slot choice.
    unrelated_msg = send_customer("Vocês têm estacionamento no local?")
    unrelated_draft = draft_on(unrelated_msg["id"])
    assert unrelated_draft["trigger"] != "GUIDED_SLOT_SELECTION", unrelated_draft

    # GB-2 (D-033): an ordinal reference — "segunda opção" shares no
    # semantic content with any offer's own specialty/day/time text, so
    # only the deterministic ordinal parser (not embedding similarity)
    # can resolve this, regardless of threshold. This is the exact bug
    # report that produced D-033.
    choice_msg = send_customer("segunda opção")
    choice_draft = draft_on(choice_msg["id"])
    assert choice_draft["trigger"] == "GUIDED_SLOT_SELECTION", choice_draft
    assert choice_draft["model"] == "not-applicable", choice_draft
    assert "Informe seu CPF" in choice_draft["draft_text"], choice_draft
    assert "R$" in choice_draft["draft_text"], choice_draft
    # D-033: no separate "Deseja que eu confirme?" gate — details (offer +
    # price) and the CPF request arrive together, one message.
    assert "Deseja que eu confirme" not in choice_draft["draft_text"], choice_draft
    # D-035: new multi-line format, ending with the "Voltar" hint.
    assert choice_draft["draft_text"].startswith("Entendi que você escolheu:\n\n"), choice_draft
    assert choice_draft["draft_text"].endswith("Digite Voltar para escolher outro horário."), choice_draft
    operator_send(choice_draft)

    # GB-4-back (D-035): "voltar" during the CPF step re-presents the same
    # original offers instead of being parsed as an (invalid) CPF.
    back_msg = send_customer("na verdade quero voltar")
    back_draft = draft_on(back_msg["id"])
    assert back_draft["trigger"] == "GUIDED_SLOT_RESELECTION", back_draft
    assert "CPF inválido" not in back_draft["draft_text"], back_draft
    assert "1." in back_draft["draft_text"] and "2." in back_draft["draft_text"], back_draft
    operator_send(back_draft)

    # A fresh ordinal choice against the same original offer set resolves
    # normally — the whole point of "voltar".
    reselect_msg = send_customer("primeira opção")
    reselect_draft = draft_on(reselect_msg["id"])
    assert reselect_draft["trigger"] == "GUIDED_SLOT_SELECTION", reselect_draft
    assert "Informe seu CPF" in reselect_draft["draft_text"], reselect_draft
    operator_send(reselect_draft)

    # GB-4 (D-033): invalid CPF re-asks (still requires operator send).
    bad_cpf_msg = send_customer("Ah 123456a8910")
    bad_cpf_draft = draft_on(bad_cpf_msg["id"])
    assert bad_cpf_draft["draft_text"] == "CPF inválido. Informe um número válido de 11 dígitos.", bad_cpf_draft
    operator_send(bad_cpf_draft)

    # A valid CPF confirms and asks about payment, in one message — the
    # real point of D-033: no independent "quero marcar" phrase needed.
    cpf_msg = send_customer("tabom 123.456..789.10")
    cpf_draft = draft_on(cpf_msg["id"])
    assert cpf_draft["trigger"] == "GUIDED_CPF_CONFIRMED", cpf_draft
    assert cpf_draft["draft_text"] == "CPF 123.456.789-10 confirmado.\n\nO valor foi pago? Responda sim ou não.\n\nDigite Voltar para escolher outro horário.", cpf_draft
    operator_send(cpf_draft)

    # GB-4-back (D-035): "voltar" also works at the *payment* step, not
    # just the CPF step — re-presents the same original offers again.
    payment_back_msg = send_customer("quero voltar")
    payment_back_draft = draft_on(payment_back_msg["id"])
    assert payment_back_draft["trigger"] == "GUIDED_SLOT_RESELECTION", payment_back_draft
    assert "1." in payment_back_draft["draft_text"] and "2." in payment_back_draft["draft_text"], payment_back_draft
    operator_send(payment_back_draft)

    # Walk the flow forward again to reach the payment step once more, so
    # the rest of this smoke test continues from a real GUIDED_CPF_CONFIRMED
    # state.
    reselect_again_msg = send_customer("1")
    reselect_again_draft = draft_on(reselect_again_msg["id"])
    assert reselect_again_draft["trigger"] == "GUIDED_SLOT_SELECTION", reselect_again_draft
    operator_send(reselect_again_draft)
    cpf_again_msg = send_customer("123.456.789-10")
    cpf_again_draft = draft_on(cpf_again_msg["id"])
    assert cpf_again_draft["trigger"] == "GUIDED_CPF_CONFIRMED", cpf_again_draft
    operator_send(cpf_again_draft)

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
        for raw_cpf_input in ("Ah 123456a8910", "tabom 123.456..789.10", "123.456.789-10"):
            assert raw_cpf_input not in bodies, bodies
        for raw_payment_input in ("Então, não paguei", "tabom simm paguei"):
            assert raw_payment_input in bodies, bodies
        # D-035: "voltar" during the payment step is not itself a CPF
        # reply, so it is deliberately not redacted.
        assert "quero voltar" in bodies, bodies

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

    print("smoke_v5_guided_booking_ok: real price_lookup resolution, ordinal slot-choice recognition, full direct-to-CPF/payment flow (D-033), zero LLM calls, redaction confirmed, every step draft-only, post-completion clinical deflection confirmed")


if __name__ == "__main__":
    run()
