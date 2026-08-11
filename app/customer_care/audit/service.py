from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from customer_care.infrastructure.models import AuditEvent


def record_event(
    session: Session,
    event_type: str,
    actor_type: str,
    *,
    actor_id: UUID | None = None,
    conversation_id: UUID | None = None,
    correlation_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        conversation_id=conversation_id,
        correlation_id=correlation_id,
        payload_json=payload or {},
    )
    session.add(event)
    return event
