from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from customer_care.infrastructure.models import AIGeneration, Conversation, Message, MessageCitation


def qa_transform_prefill(session: Session, conversation: Conversation, message: Message, generation: AIGeneration) -> dict | None:
    """V3-1×V3-8 "transformar em Q&A": only for a generation classified
    `edit` (sent text differs from the draft) — pre-fill data for
    KnowledgeAdminPage's existing create-entry form. `question` uses the
    same triggering-message fallback `select_evidence` already uses for
    MANUAL_EVIDENCE/no-triggering-message generations (plan.md §11)."""
    if generation.draft_text == message.body:
        return None
    triggering: Message | None = session.get(Message, generation.triggering_message_id) if generation.triggering_message_id else None
    if not triggering:
        triggering = session.scalar(select(Message).where(Message.conversation_id == conversation.id, Message.author_type == "CUSTOMER").order_by(Message.created_at.desc()))
    return {"question": triggering.body if triggering else "", "answer": message.body, "category_slug": generation.category_slug}


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
            item["autonomous_source"] = message.autonomous_source  # AA-10: "automático" badge (frontend)
            if include_generation_id:
                item["source_generation_id"] = message.source_generation_id
                generation = session.get(AIGeneration, message.source_generation_id) if message.source_generation_id else None
                item["qa_transform"] = qa_transform_prefill(session, conversation, message, generation) if generation else None
        result.append(item)
    return {"id": conversation.id, "status": conversation.status, "messages": result, "created_at": conversation.created_at, "closed_at": conversation.closed_at}


def assigned_operator_id(session: Session, conversation_id: UUID) -> UUID | None:
    from customer_care.infrastructure.models import ConversationAssignment
    return session.scalar(select(ConversationAssignment.operator_id).where(ConversationAssignment.conversation_id == conversation_id, ConversationAssignment.released_at.is_(None)))
