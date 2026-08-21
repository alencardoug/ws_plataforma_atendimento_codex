"""T097: real end-to-end HTTP smoke for the AA-10 booking script —
Constitution Amendment 1.1.0's one exception.

**Reachability change (D-043, 2026-08-21):** `resolve_appointment_availability()`
has unconditionally returned its offered rows since 005/GB-1, and every
caller that resolves it (`select_evidence()`, `generate_draft()`) has
always persisted them (`persist_presented_offers()`) since then. D-043
also fixed a real bug where AA-10's own generic booking-intent matcher
(`detect_booking_intent()`) raced ahead of and pre-empted GB's own
slot-choice interpretation — a customer replying with a generic "quero
agendar" to the 4 offers GB had just shown got an immediate, unconfirmed
"Agendamento realizado" instead of being asked which of the 4 they meant
(`PROJECT_STATE.md`/`DECISIONS.md` D-043). The fix: AA-10's own trigger
now defers whenever GB has a pending, unconfirmed offer set.

Structurally, that means AA-10's `advance_booking_script()` initial branch
(`booking_script_step is None`) is no longer reachable through any real
HTTP path: a fresh availability resolution always leaves a pending GB
offer set (blocking AA-10 directly), and once GB's own flow progresses at
all, its own generations (dynamic_pattern_used=True, no
AIGenerationSource — GB never attributes evidence) become the
conversation's most recent dynamic-pattern generation, which independently
makes `has_recent_resolved_availability()` false too (unrelated to D-043,
a pre-existing property of that function once any GB generation exists).
Both paths were checked directly against this rebuilt stack while fixing
D-043 — neither reaches AA-10's script anymore. This is accepted as
correct, intentional behavior (human decision, 2026-08-21): GB is the only
real product path to a completed booking now; AA-10's fixed simulation
remains exactly as Constitution Amendment 1.1.0 authorized it — untouched,
structurally contained, its own scripted messages/redaction/audit logic
still fully proven correct by `test_booking_script_flow.py` (which calls
`advance_booking_script()` directly, independent of HTTP reachability) —
it is simply never invoked by a real customer message anymore.

This smoke test's remaining job: confirm real HTTP traffic through a real
availability resolution never reaches AA-10's script (the D-043
regression itself) and that AA-10's own dormant tables
(`identity.*`/`billing.*`/`scheduling.appointments`/`scheduling.appointment_events`)
stay empty/absent exactly as before — both still meaningful, both no
longer provable by unit tests alone since they depend on the real router
call chain. specs/004-dynamic-appointment-availability/tasks.md T097,
acceptance.md §L/§N/§O; specs/011-.../DECISIONS.md D-043."""

import os
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import ProgrammingError

from customer_care.bootstrap import create_app
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import Message


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

    # D-043 regression: a generic booking-intent phrase right after a real
    # availability resolution — exactly AA-10's own historical trigger —
    # must never produce an autonomous booking_script message. GB's own
    # pending offer set now always wins.
    response = client.post(f"/api/v1/public/conversations/{conversation_id}/messages", headers=customer_headers, json={"body": "Quero marcar essa consulta"})
    assert response.status_code == 201, response.text

    detail = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert not any(m.get("autonomous_source") == "booking_script" for m in detail.json()["messages"]), detail.json()["messages"]

    with get_session_factory()() as db:
        conversation_uuid = UUID(conversation_id)
        message_bodies = [row.body for row in db.scalars(select(Message).where(Message.conversation_id == conversation_uuid)).all()]
        assert "Agendamento realizado" not in message_bodies

    for schema, table in (("identity", "patients"), ("billing", "payments"), ("scheduling", "appointments"), ("scheduling", "appointment_events")):
        _table_confirmed_empty_or_absent(schema, table)

    closed = client.post(f"/api/v1/operator/conversations/{conversation_id}/close", headers=headers)
    assert closed.status_code == 200, closed.text

    print("smoke_v4_booking_script_ok: AA-10's own trigger no longer reachable via real HTTP post-D-043 (GB always wins), no identity/billing/appointments row ever created — booking_script's own scripted-message/redaction/audit correctness remains proven by test_booking_script_flow.py")


if __name__ == "__main__":
    run()
