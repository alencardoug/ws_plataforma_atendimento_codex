"""005 (GB): guided slot-choice and confirmation-intent interpretation,
embedding-assisted, always producing an ordinary internal draft — never an
autonomous send. See specs/005-dynamic-pricing-and-guided-booking/
{spec,plan,data-model}.md. Deliberately does not import from, and is not
imported by, `booking_script/*` (spec.md GB-5 / plan.md §2/§10)."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from customer_care.infrastructure.models import AIGeneration, AppointmentOfferPresentation, Conversation, Message
from customer_care.knowledge.embeddings import EmbeddingProvider

# cosine_distance (lower = more similar). Calibrated 2026-08-19 against
# real text-embedding-3-small output (tasks.md T044, spec.md §8 outcomes
# 4/5), not a guessed constant — measured distances for genuine paraphrases
# of an offer description ranged 0.42-0.66 (a generic "the morning one,
# whichever you have first" scored 0.64; a specific "Thursday morning with
# Dr. Eduardo" scored 0.42), while an unrelated message ("do you have
# parking?") scored 0.70-0.71. 0.68 sits inside that ~0.04-0.06 gap,
# closer to the unrelated side since GB-3's fallback (ordinary RAG
# composition) is always safe — this only ever affects which draft an
# operator is shown, never an autonomous send.
SLOT_CHOICE_DISTANCE_THRESHOLD = 0.68

# GB-4 cannot use the same absolute-threshold approach: measured against
# real embeddings, affirmative and negative reference phrases are not far
# apart from each other (both are short phrases about the same topic —
# confirming or not confirming an appointment), so a clear affirmative
# reply routinely scores under threshold against *both* groups (e.g. "Pode
# confirmar sim" measured 0.154 to the affirmative group but also 0.382 to
# the negative group). Classification is therefore by which group is
# closer, gated by a minimum *margin* between the two best distances —
# measured genuine cases had margins of 0.13-0.23; an unrelated message
# had a margin of only 0.03. 0.08 sits safely between those two populations.
CONFIRMATION_MARGIN_THRESHOLD = 0.08

AFFIRMATIVE_REFERENCE_PHRASES: tuple[str, ...] = ("sim", "pode confirmar", "confirmo", "isso mesmo", "quero sim")
NEGATIVE_REFERENCE_PHRASES: tuple[str, ...] = ("não", "nao quero", "ainda não", "deixa pra depois", "não confirma")

_reference_cache: dict[str, tuple[list[list[float]], list[list[float]]]] = {}


def _offer_description(specialty_display_name: str, professional_display_name: str, weekday: str, day_month: str, hour_minute: str) -> str:
    """One-line, embedding-friendly summary of a single offer — distinct
    from `availability._render_offers`'s multi-line customer-facing block
    (`plan.md` §5.1)."""
    return f"{specialty_display_name} com {professional_display_name}, {weekday} {day_month} às {hour_minute}"


def persist_presented_offers(session: Session, provider: EmbeddingProvider, ai_generation_id: UUID, rows: Sequence[Any]) -> None:
    """GB-1: persists exactly the offers a resolved `appointment_availability`
    generation showed the customer, so a later reply can be matched against
    them without re-running the (possibly now-different) live query.
    `rows` are the `_SlotRow`-shaped tuples `resolve_appointment_availability`
    already returns — imported loosely as `Any` here to avoid a circular
    import with `scheduling.availability`, which itself does not depend on
    this module."""
    from customer_care.scheduling.availability import SAO_PAULO, _WEEKDAY_PT

    descriptions = []
    for slot, specialty, professional, _professional_specialty, _unit in rows:
        local_start = slot.starts_at.astimezone(SAO_PAULO)
        descriptions.append(
            _offer_description(
                specialty.display_name,
                professional.display_name,
                _WEEKDAY_PT[local_start.weekday()],
                f"{local_start:%d/%m}",
                f"{local_start:%H:%M}",
            )
        )
    vectors = provider.embed(descriptions)
    for order, ((slot, *_rest), description, vector) in enumerate(zip(rows, descriptions, vectors, strict=True), 1):
        session.add(AppointmentOfferPresentation(ai_generation_id=ai_generation_id, slot_id=slot.slot_id, display_order=order, description=description, embedding=vector))


def latest_unconfirmed_offer_generation_id(session: Session, conversation: Conversation) -> UUID | None:
    """005/GB-2: the most recent `appointment_availability` resolution's
    offer set for this conversation, unless AA-10's own booking script has
    already taken over (`conversation.booking_script_step is not None`) —
    at that point guided selection stops offering branches entirely
    (`data-model.md` §2)."""
    if conversation.booking_script_step is not None:
        return None
    return session.scalar(
        select(AppointmentOfferPresentation.ai_generation_id)
        .join(AIGeneration, AIGeneration.id == AppointmentOfferPresentation.ai_generation_id)
        .where(AIGeneration.conversation_id == conversation.id)
        .order_by(AIGeneration.created_at.desc())
        .limit(1)
    )


def interpret_slot_choice(session: Session, provider: EmbeddingProvider, conversation: Conversation, customer_text: str) -> AppointmentOfferPresentation | None:
    """005/GB-2/GB-3: classification against a small, closed, already-known
    candidate set — embedding-similarity only, no LLM call (`plan.md`
    §5.2). Returns `None` on no pending offer set or a below-confidence
    match, letting the caller fall through to ordinary RAG composition
    (GB-3) by construction."""
    generation_id = latest_unconfirmed_offer_generation_id(session, conversation)
    if generation_id is None:
        return None
    [vector] = provider.embed([customer_text])
    best = session.execute(
        select(AppointmentOfferPresentation, AppointmentOfferPresentation.embedding.cosine_distance(vector).label("distance"))
        .where(AppointmentOfferPresentation.ai_generation_id == generation_id)
        .order_by("distance")
        .limit(1)
    ).first()
    if best is None or best.distance > SLOT_CHOICE_DISTANCE_THRESHOLD:
        return None
    return best[0]


def _reference_vectors(provider: EmbeddingProvider) -> tuple[list[list[float]], list[list[float]]]:
    """Reference-phrase vectors computed once per configured embedding
    model (`plan.md` §5.3), not per call."""
    cached = _reference_cache.get(provider.model)
    if cached is not None:
        return cached
    affirmative = provider.embed(list(AFFIRMATIVE_REFERENCE_PHRASES))
    negative = provider.embed(list(NEGATIVE_REFERENCE_PHRASES))
    _reference_cache[provider.model] = (affirmative, negative)
    return affirmative, negative


def _cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return 1.0 - (dot / (norm_a * norm_b))


def interpret_confirmation_intent(provider: EmbeddingProvider, customer_text: str) -> bool | None:
    """005/GB-4: classifies affirmative/negative/unclear by
    embedding-similarity against a small, fixed reference-phrase set — the
    one piece of GB interpretation that genuinely benefits from
    embeddings' generalization over free phrasing (`plan.md` §5.3), unlike
    GB-2's closed 4-candidate set. Classifies by whichever reference group
    is closer, gated by a minimum margin between the two best distances
    (`CONFIRMATION_MARGIN_THRESHOLD` — an absolute per-group threshold does
    not work here, see that constant's comment). `None` covers both "no
    match" and "ambiguous" (margin too small to tell) — the caller re-asks
    identically for either (spec.md GB-4)."""
    affirmative_vectors, negative_vectors = _reference_vectors(provider)
    [vector] = provider.embed([customer_text])
    best_affirmative = min(_cosine_distance(vector, ref) for ref in affirmative_vectors)
    best_negative = min(_cosine_distance(vector, ref) for ref in negative_vectors)
    if abs(best_affirmative - best_negative) < CONFIRMATION_MARGIN_THRESHOLD:
        return None
    return best_affirmative < best_negative


def preceding_confirmation_question_generation_id(session: Session, conversation: Conversation) -> UUID | None:
    """005/GB-4 trigger condition: the conversation's most recent
    `OPERATOR` message must have been sent from a `GUIDED_SLOT_SELECTION`
    generation, with at least one customer message after it. Reuses
    `Message.source_generation_id` — an existing FK, no new lookup
    mechanism (`data-model.md` §3, corrected during this feature's
    pre-implementation cross-artifact review)."""
    latest_operator_message = session.scalar(
        select(Message).where(Message.conversation_id == conversation.id, Message.author_type == "OPERATOR").order_by(Message.created_at.desc()).limit(1)
    )
    if latest_operator_message is None or latest_operator_message.source_generation_id is None:
        return None
    has_customer_reply_after = session.scalar(
        select(Message.id)
        .where(Message.conversation_id == conversation.id, Message.author_type == "CUSTOMER", Message.created_at > latest_operator_message.created_at)
        .limit(1)
    )
    if has_customer_reply_after is None:
        return None
    generation = session.get(AIGeneration, latest_operator_message.source_generation_id)
    if generation is None or generation.trigger != "GUIDED_SLOT_SELECTION":
        return None
    return generation.id
