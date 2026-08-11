from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from customer_care.infrastructure.models import Conversation, Message, MessageCitation


def customer_projection(session: Session, conversation: Conversation) -> dict:
    messages = session.scalars(select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at, Message.id)).all()
    result = []
    for message in messages:
        item = {"id": message.id, "author_type": message.author_type, "body": message.body, "created_at": message.created_at}
        if message.author_type == "OPERATOR":
            citations = session.scalars(select(MessageCitation).where(MessageCitation.message_id == message.id).order_by(MessageCitation.created_at)).all()
            item["citations"] = [{"title": c.display_title, "section": c.display_section, "url": c.display_url} for c in citations]
        result.append(item)
    return {"id": conversation.id, "status": conversation.status, "messages": result, "created_at": conversation.created_at, "closed_at": conversation.closed_at}


def assigned_operator_id(session: Session, conversation_id: UUID) -> UUID | None:
    from customer_care.infrastructure.models import ConversationAssignment
    return session.scalar(select(ConversationAssignment.operator_id).where(ConversationAssignment.conversation_id == conversation_id, ConversationAssignment.released_at.is_(None)))
