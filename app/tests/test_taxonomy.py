from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from customer_care.ai.router import classify_generation
from customer_care.infrastructure.models import Conversation


class _FakeSession:
    """classify_generation makes one `.scalars()` call (send-event-type
    lookup) and one `.get(Conversation, ...)` call — matching
    test_category_derivation.py's fake-session convention rather than a
    real DB session for a pure unit test."""

    def __init__(self, send_event_types: tuple[str, ...] = (), conversation: object | None = None) -> None:
        self._send_event_types = list(send_event_types)
        self._conversation = conversation

    def scalars(self, _statement: object) -> Any:
        return SimpleNamespace(all=lambda: self._send_event_types)

    def get(self, model: type, _pk: object) -> object | None:
        if model is Conversation:
            return self._conversation
        return None


def _generation(**overrides: object) -> Any:
    base = {"id": uuid4(), "conversation_id": uuid4(), "trigger": "MANUAL_DRAFT", "prior_generation_id": None, "instruction_text": None, "marked_incorrect_at": None, "escalated_at": None}
    base.update(overrides)
    return SimpleNamespace(**base)


def test_approve_tag_from_draft_accepted_audit_event() -> None:
    session = _FakeSession(send_event_types=("ai.draft_accepted",))
    assert classify_generation(session, _generation()) == {"approve"}  # type: ignore[arg-type]


def test_edit_tag_from_draft_edited_audit_event() -> None:
    session = _FakeSession(send_event_types=("ai.draft_edited",))
    assert classify_generation(session, _generation()) == {"edit"}  # type: ignore[arg-type]


def test_search_tag_from_manual_evidence_trigger() -> None:
    session = _FakeSession()
    assert classify_generation(session, _generation(trigger="MANUAL_EVIDENCE")) == {"search"}  # type: ignore[arg-type]


def test_take_over_tag_from_conversation_taken_over_at() -> None:
    session = _FakeSession(conversation=SimpleNamespace(taken_over_at=datetime.now(UTC)))
    assert classify_generation(session, _generation()) == {"take-over"}  # type: ignore[arg-type]


def test_regenerate_tag_without_instruction_text() -> None:
    session = _FakeSession()
    assert classify_generation(session, _generation(prior_generation_id=uuid4())) == {"regenerate"}  # type: ignore[arg-type]


def test_regenerate_with_instruction_tag_when_instruction_text_present() -> None:
    session = _FakeSession()
    assert classify_generation(session, _generation(prior_generation_id=uuid4(), instruction_text="seja mais formal")) == {"regenerate-with-instruction"}  # type: ignore[arg-type]


def test_mark_incorrect_tag_from_marked_incorrect_at() -> None:
    session = _FakeSession()
    assert classify_generation(session, _generation(marked_incorrect_at=datetime.now(UTC))) == {"mark-incorrect"}  # type: ignore[arg-type]


def test_escalate_tag_from_escalated_at() -> None:
    session = _FakeSession()
    assert classify_generation(session, _generation(escalated_at=datetime.now(UTC))) == {"escalate"}  # type: ignore[arg-type]


def test_edit_and_mark_incorrect_are_independent_non_exclusive_tags() -> None:
    session = _FakeSession(send_event_types=("ai.draft_edited",))
    generation = _generation(marked_incorrect_at=datetime.now(UTC))
    assert classify_generation(session, generation) == {"edit", "mark-incorrect"}  # type: ignore[arg-type]
