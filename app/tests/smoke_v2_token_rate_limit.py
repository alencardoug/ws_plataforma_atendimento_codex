"""Executable V2-2 token-brute-force-mitigation smoke: repeated failed token
validations against a real conversation lock out the source, the locked-out
attempt is rejected with 429, and the fix for the previously-undocumented-and-
unimplemented `anonymous_access.token_validation_rate_limited` audit event
(plan.md §14, closed during Phase 10) is actually emitted.

Run with a low ANONYMOUS_TOKEN_RATE_LIMIT_MAX_FAILURES so the lockout
triggers quickly; this script does not depend on the value, it reads it from
the environment/settings so it works regardless of how it is invoked.
"""

from fastapi.testclient import TestClient
from sqlalchemy import select

from customer_care.anonymous_access import rate_limit
from customer_care.bootstrap import create_app
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import AuditEvent
from customer_care.shared.settings import get_settings


def run() -> None:
    rate_limit.reset_all()
    client = TestClient(create_app())
    created = client.post("/api/v1/public/conversations").json()
    conversation_id = created["conversation"]["id"]

    with get_session_factory()() as db:
        before = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "anonymous_access.token_validation_rate_limited").order_by(AuditEvent.occurred_at.desc()))
        before_id = before.id if before else None

    max_failures = get_settings().anonymous_token_rate_limit_max_failures
    for _ in range(max_failures):
        rejected = client.get(f"/api/v1/public/conversations/{conversation_id}", headers={"Authorization": "Bearer WRONGTOK"})
        assert rejected.status_code == 403, rejected.text

    locked_out = client.get(f"/api/v1/public/conversations/{conversation_id}", headers={"Authorization": "Bearer WRONGTOK"})
    assert locked_out.status_code == 429, locked_out.text
    assert locked_out.json()["code"] == "RATE_LIMITED", locked_out.text

    # A correct token is rejected identically while locked out (the lockout
    # is IP-keyed, not token-keyed — this is deliberate, not a side effect).
    still_locked = client.get(f"/api/v1/public/conversations/{conversation_id}", headers={"Authorization": f"Bearer {created['access_token']}"})
    assert still_locked.status_code == 429, still_locked.text

    with get_session_factory()() as db:
        latest = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "anonymous_access.token_validation_rate_limited").order_by(AuditEvent.occurred_at.desc()))
        assert latest is not None and latest.id != before_id, "lockout must emit anonymous_access.token_validation_rate_limited"
        assert latest.conversation_id is None, "the attempted conversation_id must never be trusted as this event's FK-constrained conversation_id"
        assert "WRONGTOK" not in str(latest.payload_json) and "Bearer" not in str(latest.payload_json), "the payload must never carry the attempted token"

    rate_limit.reset_all()
    print("v2_token_rate_limit_smoke_ok: lockout after max_failures, 429 on both wrong and correct tokens while locked out, audit event emitted without leaking the token or a fabricated conversation_id")


if __name__ == "__main__":
    run()
