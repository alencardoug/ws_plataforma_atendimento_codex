from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from customer_care.ai import router as ai_router
from customer_care.ai.router import automatic_draft_status


FAKE_IDLE_SECONDS = 8


class _FakeSession:
    """automatic_draft_status makes one `.scalar()` call (newest customer
    message id) and one `.get()` call (011: system_settings, for
    automatic_trigger_idle_seconds) — matching this suite's established
    fake-session pattern. `assigned_operator_id` is a free function, not a
    session method, so it is monkeypatched per-test instead."""

    def __init__(self, newest_customer_id: object | None = None) -> None:
        self._newest_customer_id = newest_customer_id

    def scalar(self, _statement: object) -> object | None:
        return self._newest_customer_id

    def get(self, _model: object, _pk: object) -> object:
        return SimpleNamespace(automatic_trigger_idle_seconds=FAKE_IDLE_SECONDS)


def _conversation(**overrides: object) -> Any:
    base = {
        "id": uuid4(),
        "status": "ACTIVE",
        "effective_mode": "N2",
        "last_customer_activity_at": datetime.now(UTC),
        "auto_draft_covers_through_message_id": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _assign_operator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_router, "assigned_operator_id", lambda session, conversation_id: uuid4())


def test_not_active_is_never_eligible() -> None:
    session = _FakeSession(newest_customer_id=uuid4())
    assert automatic_draft_status(session, _conversation(status="WAITING")) == (False, None)  # type: ignore[arg-type]


def test_n1_effective_mode_is_never_eligible() -> None:
    session = _FakeSession(newest_customer_id=uuid4())
    assert automatic_draft_status(session, _conversation(effective_mode="N1")) == (False, None)  # type: ignore[arg-type]


def test_no_customer_activity_yet_is_not_eligible() -> None:
    session = _FakeSession(newest_customer_id=uuid4())
    assert automatic_draft_status(session, _conversation(last_customer_activity_at=None)) == (False, None)  # type: ignore[arg-type]


def test_no_customer_message_at_all_is_not_eligible() -> None:
    session = _FakeSession(newest_customer_id=None)
    assert automatic_draft_status(session, _conversation()) == (False, None)  # type: ignore[arg-type]


def test_already_covered_activity_is_not_eligible() -> None:
    message_id = uuid4()
    session = _FakeSession(newest_customer_id=message_id)
    assert automatic_draft_status(session, _conversation(auto_draft_covers_through_message_id=message_id)) == (False, None)  # type: ignore[arg-type]


def test_no_assigned_operator_is_not_eligible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_router, "assigned_operator_id", lambda session, conversation_id: None)
    session = _FakeSession(newest_customer_id=uuid4())
    assert automatic_draft_status(session, _conversation()) == (False, None)  # type: ignore[arg-type]


def test_eligible_with_time_remaining() -> None:
    session = _FakeSession(newest_customer_id=uuid4())
    conversation = _conversation(last_customer_activity_at=datetime.now(UTC) - timedelta(seconds=3))
    eligible, remaining = automatic_draft_status(session, conversation)  # type: ignore[arg-type]
    assert eligible is True
    assert remaining == FAKE_IDLE_SECONDS - 3


def test_eligible_past_threshold_never_goes_negative() -> None:
    session = _FakeSession(newest_customer_id=uuid4())
    conversation = _conversation(last_customer_activity_at=datetime.now(UTC) - timedelta(seconds=999))
    eligible, remaining = automatic_draft_status(session, conversation)  # type: ignore[arg-type]
    assert eligible is True
    assert remaining == 0
