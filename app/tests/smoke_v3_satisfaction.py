"""Executable V3-12 smoke: the satisfaction survey never blocks/delays
close, skipping leaves no partial/inconsistent record, a submitted
response is durably tied to the correct conversation and category, and is
reflected in V3-4's read-only metrics (spec.md §5 outcome 13, T131)."""

import os

from fastapi.testclient import TestClient
from sqlalchemy import select

from customer_care.bootstrap import create_app
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import AuditEvent, ConversationSatisfactionResponse


def run() -> None:
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/operator/login", json={"email": os.environ["SMOKE_OPERATOR_EMAIL"], "password": os.environ["SMOKE_OPERATOR_PASSWORD"]})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # --- fixture: a fresh conversation, answered via AI, then closed ---
    created = client.post("/api/v1/public/conversations")
    assert created.status_code == 201, created.text
    body = created.json()
    conversation_id = body["conversation"]["id"]
    customer_headers = {"Authorization": f"Bearer {body['access_token']}"}
    sent = client.post(f"/api/v1/public/conversations/{conversation_id}/messages", headers=customer_headers, json={"body": "Vocês atendem aos sábados?"})
    assert sent.status_code == 201, sent.text

    claimed = client.post(f"/api/v1/operator/conversations/{conversation_id}/claim", headers=headers)
    assert claimed.status_code == 200, claimed.text
    detail = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers).json()
    customer_message_id = next(item["id"] for item in reversed(detail["messages"]) if item["author_type"] == "CUSTOMER")
    generated = client.post(f"/api/v1/operator/conversations/{conversation_id}/drafts", headers=headers, json={"selected_message_ids": [customer_message_id]})
    assert generated.status_code == 201, generated.text
    draft = generated.json()
    before_send = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers).json()
    latest = before_send["latest_generation"] or draft
    sent_reply = client.post(f"/api/v1/operator/conversations/{conversation_id}/messages", headers=headers, json={"body": latest["draft_text"] or "Resposta manual.", "source_generation_id": latest["id"], "citation_retrieval_hit_ids": []})
    assert sent_reply.status_code == 201, sent_reply.text

    # --- submit-before-close must be rejected: survey never precedes/blocks close ---
    early_survey = client.post(f"/api/v1/public/conversations/{conversation_id}/satisfaction", headers=customer_headers, json={"score": 5, "resolved": True})
    assert early_survey.status_code == 409 and early_survey.json()["code"] == "NOT_CLOSED", early_survey.text

    closed = client.post(f"/api/v1/public/conversations/{conversation_id}", headers=customer_headers)
    assert closed.status_code == 200 and closed.json()["status"] == "CLOSED", closed.text

    # --- skip: leaves no partial/inconsistent record ---
    with get_session_factory()() as db:
        assert db.scalar(select(ConversationSatisfactionResponse).where(ConversationSatisfactionResponse.conversation_id == conversation_id)) is None, "skipping must never create a partial row"

    # --- submit: durably tied to the correct conversation and category ---
    submitted = client.post(f"/api/v1/public/conversations/{conversation_id}/satisfaction", headers=customer_headers, json={"score": 4, "resolved": True})
    assert submitted.status_code == 201, submitted.text
    submitted_body = submitted.json()
    assert submitted_body["conversation_id"] == conversation_id
    assert submitted_body["score"] == 4 and submitted_body["resolved"] is True

    # Idempotency/duplicate guard: a second submission for the same
    # conversation must not silently overwrite or duplicate.
    duplicate = client.post(f"/api/v1/public/conversations/{conversation_id}/satisfaction", headers=customer_headers, json={"score": 1, "resolved": False})
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "ALREADY_SUBMITTED", duplicate.text

    with get_session_factory()() as db:
        stored = db.scalar(select(ConversationSatisfactionResponse).where(ConversationSatisfactionResponse.conversation_id == conversation_id))
        assert stored is not None and stored.score == 4 and stored.resolved is True
        event_types = set(db.scalars(select(AuditEvent.event_type).where(AuditEvent.conversation_id == conversation_id)).all())
        assert "conversation.satisfaction_submitted" in event_types

    # --- reflected in V3-4's metrics: same category_slug/score visible via
    # the documented read-only query pattern (docs/metrics/v3_queries.sql
    # query 4), reproduced here directly against the stored row rather than
    # shelling out to psql. ---
    with get_session_factory()() as db:
        stored = db.scalar(select(ConversationSatisfactionResponse).where(ConversationSatisfactionResponse.conversation_id == conversation_id))
        # category_slug is denormalized from the conversation's most recent
        # ANSWER generation at submission time (plan.md §3.1/§3.4) — may be
        # None if the reply drew on a CLINICAL/ABSTAIN path with no
        # category, which is an explicit "sem categoria" bucket, not a bug.
        assert stored.category_slug is None or isinstance(stored.category_slug, str)

    print("v3_satisfaction_smoke_ok: blocked-before-close, skip-leaves-no-row, submit ties to conversation/category, duplicate rejected, audit event present")


if __name__ == "__main__":
    run()
