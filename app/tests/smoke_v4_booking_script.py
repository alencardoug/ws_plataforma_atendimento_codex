"""T097: real end-to-end HTTP smoke for the AA-10 booking script —
Constitution Amendment 1.1.0's one exception. Real availability
resolution, a real customer booking-intent message, the script's
messages appear with zero operator action, the full CPF/payment happy
path (including both retry branches) via real customer message posts,
confirms the exact final message, and confirms no
identity.*/billing.*/scheduling.appointments row was ever created — those
schemas/tables were never even created by this feature's own migrations
(D-024, still dormant), so their absence is structural, not just
behavioral. specs/004-dynamic-appointment-availability/tasks.md T097,
acceptance.md §L/§N/§O."""

import os
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import ProgrammingError

from customer_care.bootstrap import create_app
from customer_care.booking_script.service import CPF_INPUT_REDACTION, PAYMENT_INPUT_REDACTION
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import AuditEvent, Message


def _table_confirmed_empty_or_absent(schema: str, table: str) -> None:
    session_factory = get_session_factory()
    with session_factory() as db:
        try:
            count = db.scalar(text(f"SELECT count(*) FROM {schema}.{table}"))
        except ProgrammingError:
            db.rollback()
            return  # the table does not exist at all — the strongest possible proof
        assert count == 0, f"{schema}.{table} has {count} row(s) — AA-10 must never write here"


def run() -> None:
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/operator/login", json={"email": os.environ["SMOKE_OPERATOR_EMAIL"], "password": os.environ["SMOKE_OPERATOR_PASSWORD"]})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    seeded = client.post("/api/v1/operator/scheduling/ensure-availability", headers=headers)
    assert seeded.status_code == 200, seeded.text

    conversation = client.post("/api/v1/public/conversations")
    assert conversation.status_code == 201, conversation.text
    conversation_id = conversation.json()["conversation"]["id"]
    customer_headers = {"Authorization": f"Bearer {conversation.json()['access_token']}"}

    claim = client.post(f"/api/v1/operator/conversations/{conversation_id}/claim", headers=headers)
    assert claim.status_code == 200, claim.text

    search = client.post("/api/v1/operator/knowledge/search", headers=headers, json={"query": "Existe consulta disponível amanhã?", "top_k": 8})
    assert search.status_code == 200, search.text
    hit = next(item for item in search.json()["evidence"] if item["knowledge_type"] == "ADMIN_QA" and item["title"] == "Existe consulta disponível amanhã?")
    resolved = client.post(f"/api/v1/operator/knowledge/evidence/{hit['retrieval_hit_id']}/select", headers=headers, json={"conversation_id": conversation_id})
    assert resolved.status_code == 201, resolved.text
    assert resolved.json()["dynamic_pattern_used"] is True, resolved.json()

    def send_customer(body: str) -> dict:
        response = client.post(f"/api/v1/public/conversations/{conversation_id}/messages", headers=customer_headers, json={"body": body})
        assert response.status_code == 201, response.text
        return response.json()

    def latest_operator_bodies(count: int) -> list[str]:
        detail = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers)
        assert detail.status_code == 200, detail.text
        autonomous = [m for m in detail.json()["messages"] if m.get("author_type") == "OPERATOR"]
        return [m["body"] for m in autonomous[-count:]]

    send_customer("Quero marcar essa consulta")
    assert latest_operator_bodies(2) == [
        "Agendamento realizado",
        "Informe seu CPF - é uma simulação, informe qualquer número de 11 dígitos",
    ]

    send_customer("Ah 123456a8910")
    assert latest_operator_bodies(1) == ["CPF inválido. Informe um número válido de 11 dígitos"]

    send_customer("tabom 123.456..789.10")
    cpf_confirmed_onward = latest_operator_bodies(3)
    assert cpf_confirmed_onward[0] == "CPF 123.456.789-10 confirmado"
    assert cpf_confirmed_onward[1].startswith("O valor da consulta é R$")
    assert cpf_confirmed_onward[2] == "O valor foi pago? Responda sim ou não"

    send_customer("Então, não paguei")
    assert latest_operator_bodies(1) == ["O valor foi pago? Responda sim ou não"]

    send_customer("tabom simm paguei")
    assert latest_operator_bodies(3) == [
        "Verificando pagamento",
        "Pagamento verificado",
        "Agendamento realizado com sucesso. Há algo mais que posso ajudar?",
    ]

    detail = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers)
    autonomous_ids = {m["id"] for m in detail.json()["messages"] if m.get("author_type") == "OPERATOR"}
    # 10 autonomous sends total across the whole script: 2 (start) + 1
    # (invalid-CPF retry) + 3 (CPF confirmed/price/payment prompt) + 1
    # (não retry) + 3 (verificando/verificado/final) — select_evidence
    # above created no Message, only an AIGeneration.
    assert len(autonomous_ids) == 10

    # Outcome 13: CPF/payment inputs remain request-local. The formatted CPF
    # in the fixed confirmation output is deliberate; submitted strings are
    # replaced with fixed disclosure markers before Message persistence.
    with get_session_factory()() as db:
        conversation_uuid = UUID(conversation_id)
        message_bodies = [row.body for row in db.scalars(select(Message).where(Message.conversation_id == conversation_uuid)).all()]
        assert CPF_INPUT_REDACTION in message_bodies
        assert PAYMENT_INPUT_REDACTION in message_bodies
        for raw_input in ("Ah 123456a8910", "tabom 123.456..789.10", "Então, não paguei", "tabom simm paguei"):
            assert raw_input not in message_bodies
        payloads = [str(row.payload_json) for row in db.scalars(select(AuditEvent).where(AuditEvent.conversation_id == conversation_uuid)).all()]
        for raw_fragment in ("123456a8910", "123.456..789.10", "não paguei", "simm paguei"):
            assert all(raw_fragment not in payload for payload in payloads)

    for schema, table in (("identity", "patients"), ("billing", "payments"), ("scheduling", "appointments"), ("scheduling", "appointment_events")):
        _table_confirmed_empty_or_absent(schema, table)

    closed = client.post(f"/api/v1/operator/conversations/{conversation_id}/close", headers=headers)
    assert closed.status_code == 200, closed.text

    print("smoke_v4_booking_script_ok: real availability resolution, full scripted flow (both retry branches), zero operator clicks, no identity/billing/appointments row created")


if __name__ == "__main__":
    run()
