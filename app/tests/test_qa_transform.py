from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from customer_care.conversations.projections import qa_transform_prefill


class _FakeSession:
    """qa_transform_prefill makes one `.get(Message, ...)` call (when
    triggering_message_id is set) and, on the fallback path, one
    `.scalar()` call — matching this suite's established fake-session
    pattern (test_category_derivation.py, test_taxonomy.py)."""

    def __init__(self, triggering: object | None = None, latest_customer: object | None = None) -> None:
        self._triggering = triggering
        self._latest_customer = latest_customer

    def get(self, _model: type, _pk: object) -> object | None:
        return self._triggering

    def scalar(self, _statement: object) -> object | None:
        return self._latest_customer


def _generation(**overrides: object) -> Any:
    base = {"draft_text": "resposta original", "triggering_message_id": uuid4(), "category_slug": "instituicao"}
    base.update(overrides)
    return SimpleNamespace(**base)


def test_approved_unmodified_send_has_no_qa_transform() -> None:
    session = _FakeSession()
    message = SimpleNamespace(body="resposta original", conversation_id=uuid4())
    generation = _generation()

    assert qa_transform_prefill(session, SimpleNamespace(id=message.conversation_id), message, generation) is None


def test_edited_send_prefills_from_triggering_message() -> None:
    triggering = SimpleNamespace(body="Qual o horário de atendimento?")
    session = _FakeSession(triggering=triggering)
    message = SimpleNamespace(body="resposta editada pelo operador", conversation_id=uuid4())
    generation = _generation()

    result = qa_transform_prefill(session, SimpleNamespace(id=message.conversation_id), message, generation)

    assert result == {"question": "Qual o horário de atendimento?", "answer": "resposta editada pelo operador", "category_slug": "instituicao"}


def test_edited_send_falls_back_to_latest_customer_message_when_no_triggering_message() -> None:
    latest_customer = SimpleNamespace(body="pergunta via busca manual")
    session = _FakeSession(triggering=None, latest_customer=latest_customer)
    message = SimpleNamespace(body="resposta editada", conversation_id=uuid4())
    generation = _generation(triggering_message_id=None)

    result = qa_transform_prefill(session, SimpleNamespace(id=message.conversation_id), message, generation)

    assert result is not None
    assert result["question"] == "pergunta via busca manual"


def test_no_category_slug_still_prefills_question_and_answer() -> None:
    triggering = SimpleNamespace(body="Pergunta sem categoria")
    session = _FakeSession(triggering=triggering)
    message = SimpleNamespace(body="resposta editada", conversation_id=uuid4())
    generation = _generation(category_slug=None)

    result = qa_transform_prefill(session, SimpleNamespace(id=message.conversation_id), message, generation)

    assert result == {"question": "Pergunta sem categoria", "answer": "resposta editada", "category_slug": None}
