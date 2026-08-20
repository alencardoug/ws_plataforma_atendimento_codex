from typing import Any

import pytest

from customer_care.anonymous_access import router as anonymous_router
from customer_care.anonymous_access.router import customer_draft_status


def _conversation() -> Any:
    return object()


def test_eligible_maps_to_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """008/CS-1: reuses automatic_draft_status() verbatim; only the
    boolean crosses into the response."""
    monkeypatch.setattr(anonymous_router, "automatic_draft_status", lambda session, conversation: (True, 3))
    assert customer_draft_status(None, _conversation()) == {"preparing_response": True}  # type: ignore[arg-type]


def test_ineligible_maps_to_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(anonymous_router, "automatic_draft_status", lambda session, conversation: (False, None))
    assert customer_draft_status(None, _conversation()) == {"preparing_response": False}  # type: ignore[arg-type]


def test_seconds_remaining_never_crosses_into_the_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """008/CS-3: the countdown number itself must never reach a /public/*
    response — this asserts it structurally, by checking the whole
    returned dict's only key, not just that a specific key is absent."""
    monkeypatch.setattr(anonymous_router, "automatic_draft_status", lambda session, conversation: (True, 5))
    result = customer_draft_status(None, _conversation())  # type: ignore[arg-type]
    assert set(result.keys()) == {"preparing_response"}
    assert 5 not in result.values()
