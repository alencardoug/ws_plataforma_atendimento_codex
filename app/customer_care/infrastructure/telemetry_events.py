"""Freeze pending-send facts on the application thread; publish after commit.

The SDK/exporter receives only the returned plain snapshot, never an ORM entity
or Session. There are no writes, retries, commits or rollbacks in this module.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from customer_care.infrastructure import telemetry
from customer_care.infrastructure.models import AIGeneration, Message, PendingAutonomousSend


def pending_snapshot(session: Session, pending: PendingAutonomousSend | None, generation: AIGeneration | None = None, message: Message | None = None) -> dict[str, Any] | None:
    if telemetry._client is None or not telemetry.enabled() or pending is None:
        return None
    try:
        with session.no_autoflush:
            generation = generation or session.get(AIGeneration, pending.generation_id)
            if not generation or not generation.triggering_message_id:
                return None
            triggering = session.get(Message, generation.triggering_message_id)
            if not triggering:
                return None
            return {
                "trace_id": generation.triggering_message_id.hex,
                "session_id": str(pending.conversation_id),
                "turn_id": str(generation.triggering_message_id), "turn_created_at": triggering.created_at.astimezone(UTC).isoformat(),
                "ai_generation_id": str(generation.id),
                "prior_generation_id": str(generation.prior_generation_id) if generation.prior_generation_id else None,
                "pending_id": str(pending.id) if pending.id else None,
                "mechanism": pending.mechanism, "category": pending.category, "status": pending.status,
                "opens_at": pending.opens_at.astimezone(UTC).isoformat(), "resolves_at": pending.resolves_at.astimezone(UTC).isoformat(),
                "window_seconds": pending.window_seconds,
                "resolved_at": pending.resolved_at.astimezone(UTC).isoformat() if pending.resolved_at else None,
                "resolved_by_operator_id": str(pending.resolved_by_operator_id) if pending.resolved_by_operator_id else None,
                "message": {"message_id": str(message.id), "body": message.body, "created_at": message.created_at.astimezone(UTC).isoformat(),
                            "autonomous_source": message.autonomous_source} if message else None,
            }
    except Exception:
        return None


def publish_pending(snapshot: dict[str, Any] | None, *, committed_id: str | None = None) -> None:
    """Caller must have confirmed the existing transaction's commit first.

Pending IDs are DB defaults. For opening, all other fields are frozen before
commit; the assigned ID is supplied after commit from the unexpired entity.
No additional flush is necessary just for telemetry.
"""
    if snapshot is None:
        return
    try:
        data = {**snapshot, "pending_id": committed_id or snapshot["pending_id"]}
        status = data["status"]
        name = "autonomy.pending_opened" if status == "PENDING" else "autonomy.pending_resolved"
        identity = {"trace_id": data["trace_id"], "session_id": data["session_id"]}
        with telemetry.observe(name, lambda: {"output": data, "metadata": {"turn_id": data["turn_id"], "mechanism": data["mechanism"]}}, identity=lambda: identity):
            if data["mechanism"] == "ungoverned_n5":
                telemetry.score("n5.pending_opened" if status == "PENDING" else "n5.pending_outcome",
                                1.0 if status == "PENDING" else status, key=data["pending_id"],
                                timestamp=data["opens_at"] if status == "PENDING" else data["resolved_at"],
                                data_type="BOOLEAN" if status == "PENDING" else "CATEGORICAL")
        if status == "SENT" and data["message"]:
            message = data["message"]
            with telemetry.observe("message.sent", lambda: {"output": message, "metadata": {
                "turn_id": data["turn_id"], "pending_id": data["pending_id"], "ai_generation_id": data["ai_generation_id"],
                "mechanism": data["mechanism"],
            }}, identity=lambda: identity):
                if data["mechanism"] == "ungoverned_n5":
                    telemetry.score("n5.sent", 1.0, key=message["message_id"], timestamp=message["created_at"], data_type="BOOLEAN")
                    latency = (datetime.fromisoformat(message["created_at"]) - datetime.fromisoformat(data["turn_created_at"])).total_seconds() * 1000
                    telemetry.score("n5.response_latency_ms", latency, key=message["message_id"], timestamp=message["created_at"], data_type="NUMERIC")
    except Exception:
        pass
