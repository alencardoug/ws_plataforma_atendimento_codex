"""Executable PostgreSQL/API smoke for the pre-RAG V1 core."""

import os
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from customer_care.bootstrap import create_app
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import AuditEvent, Conversation, OperatorUser


def run() -> None:
    client = TestClient(create_app())
    sessions: list[tuple[str, str]] = []
    for index in range(6):
        response = client.post("/api/v1/public/conversations")
        assert response.status_code == 201, response.text
        item = response.json()
        conversation_id, token = item["conversation"]["id"], item["access_token"]
        message = client.post(
            f"/api/v1/public/conversations/{conversation_id}/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={"body": f"Mensagem sintética {index}"},
        )
        assert message.status_code == 201, message.text
        sessions.append((conversation_id, token))

    cross_access = client.get(
        f"/api/v1/public/conversations/{sessions[1][0]}",
        headers={"Authorization": f"Bearer {sessions[0][1]}"},
    )
    assert cross_access.status_code == 403

    customer_on_operator_route = client.get(
        "/api/v1/operator/conversations",
        headers={"Authorization": f"Bearer {sessions[0][1]}"},
    )
    assert customer_on_operator_route.status_code == 401

    failed_login = client.post(
        "/api/v1/auth/operator/login",
        json={"email": os.environ["SMOKE_OPERATOR_EMAIL"], "password": "definitely-wrong"},
    )
    assert failed_login.status_code == 401, failed_login.text

    login = client.post("/api/v1/auth/operator/login", json={"email": os.environ["SMOKE_OPERATOR_EMAIL"], "password": os.environ["SMOKE_OPERATOR_PASSWORD"]})
    assert login.status_code == 200, login.text
    operator_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    queue = client.get("/api/v1/operator/conversations?scope=waiting", headers=operator_headers)
    assert queue.status_code == 200 and len(queue.json()) >= 6, queue.text

    for conversation_id, _ in sessions[:4]:
        claimed = client.post(f"/api/v1/operator/conversations/{conversation_id}/claim", headers=operator_headers)
        assert claimed.status_code == 200, claimed.text
    fifth = client.post(f"/api/v1/operator/conversations/{sessions[4][0]}/claim", headers=operator_headers)
    assert fifth.status_code == 409 and fifth.json()["code"] == "CAPACITY_EXCEEDED", fifth.text

    sent = client.post(
        f"/api/v1/operator/conversations/{sessions[0][0]}/messages",
        headers=operator_headers,
        json={"body": "Resposta manual sintética."},
    )
    assert sent.status_code == 201, sent.text
    customer_read = client.get(
        f"/api/v1/public/conversations/{sessions[0][0]}",
        headers={"Authorization": f"Bearer {sessions[0][1]}"},
    )
    assert customer_read.status_code == 200
    assert customer_read.json()["messages"][-1]["body"] == "Resposta manual sintética."
    assert "latest_generation" not in customer_read.json()
    # 008/CS-2 and 007/BS-6 each added one legitimate customer-facing
    # computed field (preparing_response, booking_summary_line) — this
    # exact-set assertion is updated to include both rather than weakened
    # to a superset check, so it still catches any future unintended leak.
    assert set(customer_read.json()) == {"id", "status", "messages", "created_at", "closed_at", "preparing_response", "booking_summary_line"}
    assert all("source_generation_id" not in message for message in customer_read.json()["messages"])

    with get_session_factory()() as db:
        active = db.scalar(select(func.count()).select_from(Conversation).where(Conversation.status == "ACTIVE"))
        waiting = db.scalar(select(func.count()).select_from(Conversation).where(Conversation.status == "WAITING"))
        audits = db.scalar(select(func.count()).select_from(AuditEvent))
        persisted = db.scalars(select(Conversation).where(Conversation.id.in_([item[0] for item in sessions]))).all()
        operator = db.scalar(select(OperatorUser).where(OperatorUser.email == os.environ["SMOKE_OPERATOR_EMAIL"]))
        assert active == 4 and waiting >= 2 and audits >= 18
        assert all(row.anonymous_token_digest not in {token for _, token in sessions} for row in persisted)
        assert operator is not None and operator.password_hash.startswith("$argon2")
        assert os.environ["SMOKE_OPERATOR_PASSWORD"] not in operator.password_hash
    print("core_smoke_ok: six sessions, four active, capacity rejection, IDOR rejection, manual send")


if __name__ == "__main__":
    run()
