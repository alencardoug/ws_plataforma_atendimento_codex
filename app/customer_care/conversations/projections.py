from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from customer_care.infrastructure.models import Conversation, Message, MessageCitation


def customer_projection(session: Session, conversation: Conversation, include_generation_id: bool = False) -> dict:
    """`include_generation_id` must stay False for every /public/* caller —
    an AI generation is an internal artifact (Article III); its id is
    exposed only to the operator surface (V3-1's mark-incorrect/escalate
    need it to target the generation behind a sent message), never to the
    customer this same function also serves."""
    messages = session.scalars(select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at, Message.id)).all()
    result = []
    for message in messages:
        item = {"id": message.id, "author_type": message.author_type, "body": message.body, "created_at": message.created_at}
        if message.author_type == "OPERATOR":
            citations = session.scalars(select(MessageCitation).where(MessageCitation.message_id == message.id).order_by(MessageCitation.created_at)).all()
            item["citations"] = [{"title": c.display_title, "section": c.display_section, "url": c.display_url} for c in citations]
            if include_generation_id:
                item["source_generation_id"] = message.source_generation_id
        result.append(item)
    return {"id": conversation.id, "status": conversation.status, "messages": result, "created_at": conversation.created_at, "closed_at": conversation.closed_at}


def assigned_operator_id(session: Session, conversation_id: UUID) -> UUID | None:
    from customer_care.infrastructure.models import ConversationAssignment
    return session.scalar(select(ConversationAssignment.operator_id).where(ConversationAssignment.conversation_id == conversation_id, ConversationAssignment.released_at.is_(None)))
