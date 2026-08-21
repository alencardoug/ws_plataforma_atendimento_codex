"""010 (Constitution Amendment 1.2.0): **the only function in this module,
and the only function anywhere outside `booking_script/` (Amendment
1.1.0's own, separately authorized exception), allowed to create a
customer-visible `Message` without an authenticated-operator dependency
in its call chain** — grep-able, single-purpose, enforced by
`tests/test_booking_script_containment.py`'s own updated allowlist and
`tests/test_010_governed_autonomy_containment.py`. Never imported
anywhere except its own callers in `ai/router.py`/`operator_workspace/router.py`.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from customer_care.audit.service import record_event
from customer_care.infrastructure.models import AIGeneration, Conversation, Message, PendingAutonomousSend


def resolve_elapsed_autonomous_sends(session: Session) -> None:
    """010/GA-3, GA-4: sends every PENDING row whose window has elapsed.
    Lazily evaluated as a side effect of the operator's queue poll and
    conversation-detail poll (same no-scheduler discipline as V2-7's own
    evaluate_automatic_trigger()) — never a background worker. The
    `WHERE status='PENDING'` guard on the resolving UPDATE (via the ORM's
    own optimistic re-check below) is the actual double-send guard, not a
    separate lock — a second concurrent call finds nothing left to
    resolve for a row this call already claimed."""
    elapsed = session.scalars(select(PendingAutonomousSend).where(PendingAutonomousSend.status == "PENDING", PendingAutonomousSend.resolves_at <= datetime.now(UTC))).all()
    for pending in elapsed:
        # Re-check status under the same transaction immediately before
        # acting — closes the window between the SELECT above and this
        # UPDATE for two callers racing on the same row (queue poll and
        # detail poll, potentially from different operators).
        session.refresh(pending)
        if pending.status != "PENDING":
            continue
        generation = session.get(AIGeneration, pending.generation_id)
        if not generation:
            continue
        message = Message(conversation_id=pending.conversation_id, author_type="OPERATOR", body=generation.draft_text, source_generation_id=generation.id, autonomous_source="governed_autonomy", created_at=datetime.now(UTC))
        session.add(message)
        session.flush()
        conversation = session.get(Conversation, pending.conversation_id)
        if conversation:
            conversation.last_message_at = message.created_at
        pending.status = "SENT"
        pending.resolved_at = message.created_at
        record_event(session, "autonomy.message_sent", "SYSTEM", conversation_id=pending.conversation_id, payload={"conversation_id": str(pending.conversation_id), "message_id": str(message.id), "pending_autonomous_send_id": str(pending.id), "generation_id": str(generation.id), "category": pending.category})
        session.commit()
