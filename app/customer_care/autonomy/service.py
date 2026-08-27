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
    double-send guard is a `SELECT ... FOR UPDATE SKIP LOCKED` row lock:
    a second concurrent caller cannot even see a row this call has
    claimed, so it never re-sends it. (An earlier version relied only on
    an optimistic `session.refresh()` re-check — under READ COMMITTED that
    does not serialize N callers who all read `status='PENDING'` in the
    same instant, and a burst of piled-up polls then sent the same draft
    several times. Found on prod, 2026-08-27 — see DECISIONS.md D-044.)"""
    elapsed = session.scalars(
        select(PendingAutonomousSend)
        .where(PendingAutonomousSend.status == "PENDING", PendingAutonomousSend.resolves_at <= datetime.now(UTC))
        .with_for_update(skip_locked=True)
    ).all()
    for pending in elapsed:
        # Belt-and-braces re-check (the row lock above is the real guard).
        session.refresh(pending)
        if pending.status != "PENDING":
            continue
        generation = session.get(AIGeneration, pending.generation_id)
        if not generation:
            continue
        # 011: mechanism carries the value stamped at window-open time
        # (maybe_open_autonomous_window(), plan.md §4) — 'governed_autonomy'
        # (Amendment 1.2.0) or 'ungoverned_n5' (Amendment 1.3.0).
        message = Message(conversation_id=pending.conversation_id, author_type="OPERATOR", body=generation.draft_text, source_generation_id=generation.id, autonomous_source=pending.mechanism, created_at=datetime.now(UTC))
        session.add(message)
        session.flush()
        conversation = session.get(Conversation, pending.conversation_id)
        if conversation:
            conversation.last_message_at = message.created_at
        pending.status = "SENT"
        pending.resolved_at = message.created_at
        record_event(session, "autonomy.message_sent", "SYSTEM", conversation_id=pending.conversation_id, payload={"conversation_id": str(pending.conversation_id), "message_id": str(message.id), "pending_autonomous_send_id": str(pending.id), "generation_id": str(generation.id), "category": pending.category, "mechanism": pending.mechanism})
        session.commit()
