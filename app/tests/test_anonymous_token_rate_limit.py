import pytest
from fastapi import HTTPException

from customer_care.anonymous_access import rate_limit
from customer_care.anonymous_access.security import TOKEN_ALPHABET, TOKEN_LENGTH, issue_conversation_token


@pytest.fixture(autouse=True)
def _isolated_limiter_state() -> None:
    rate_limit.reset_all()


def _fake_clock(monkeypatch: pytest.MonkeyPatch, start: float = 1000.0) -> list[float]:
    clock = [start]
    monkeypatch.setattr(rate_limit, "_now", lambda: clock[0])
    return clock


def test_token_format_uses_short_ambiguity_free_alphabet() -> None:
    raw, _digest = issue_conversation_token()

    assert len(raw) == TOKEN_LENGTH == 8
    assert all(char in TOKEN_ALPHABET for char in raw)
    assert not set("0O1IL") & set(raw)


def test_rate_limiter_allows_attempts_below_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_clock(monkeypatch)

    for _ in range(4):
        rate_limit.enforce_not_locked_out("token_validation", "1.2.3.4")
        rate_limit.record_attempt(
            "token_validation", "1.2.3.4", success=False,
            max_failures=5, window_seconds=60, base_lockout_seconds=60, max_lockout_seconds=900,
        )

    rate_limit.enforce_not_locked_out("token_validation", "1.2.3.4")


def test_rate_limiter_locks_out_after_max_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_clock(monkeypatch)

    for _ in range(5):
        rate_limit.enforce_not_locked_out("token_validation", "1.2.3.4")
        rate_limit.record_attempt(
            "token_validation", "1.2.3.4", success=False,
            max_failures=5, window_seconds=60, base_lockout_seconds=60, max_lockout_seconds=900,
        )

    with pytest.raises(HTTPException) as excinfo:
        rate_limit.enforce_not_locked_out("token_validation", "1.2.3.4")
    assert excinfo.value.status_code == 429


def test_rate_limiter_lockout_expires_after_the_configured_window(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _fake_clock(monkeypatch)

    for _ in range(5):
        rate_limit.record_attempt(
            "token_validation", "1.2.3.4", success=False,
            max_failures=5, window_seconds=60, base_lockout_seconds=60, max_lockout_seconds=900,
        )
    with pytest.raises(HTTPException):
        rate_limit.enforce_not_locked_out("token_validation", "1.2.3.4")

    clock[0] += 61  # past the 60s base lockout
    rate_limit.enforce_not_locked_out("token_validation", "1.2.3.4")


def test_rate_limiter_escalates_lockout_on_repeated_offenses(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _fake_clock(monkeypatch)

    def hit_lockout() -> None:
        for _ in range(5):
            rate_limit.record_attempt(
                "token_validation", "5.5.5.5", success=False,
                max_failures=5, window_seconds=60, base_lockout_seconds=10, max_lockout_seconds=900,
            )

    hit_lockout()
    clock[0] += 11  # first lockout (10s) has expired
    rate_limit.enforce_not_locked_out("token_validation", "5.5.5.5")

    hit_lockout()
    with pytest.raises(HTTPException):
        rate_limit.enforce_not_locked_out("token_validation", "5.5.5.5")
    clock[0] += 11  # first lockout duration again is NOT enough the second time (should now be 20s)
    with pytest.raises(HTTPException):
        rate_limit.enforce_not_locked_out("token_validation", "5.5.5.5")
    clock[0] += 10  # now past the doubled 20s lockout
    rate_limit.enforce_not_locked_out("token_validation", "5.5.5.5")


def test_rate_limiter_lockout_is_capped_at_max_lockout_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _fake_clock(monkeypatch)

    def hit_lockout() -> None:
        for _ in range(5):
            rate_limit.record_attempt(
                "token_validation", "9.9.9.9", success=False,
                max_failures=5, window_seconds=60, base_lockout_seconds=100, max_lockout_seconds=150,
            )

    # Escalate consecutive_lockouts well past the point where an uncapped
    # exponential backoff (100 * 2**n) would exceed max_lockout_seconds.
    for _ in range(6):
        hit_lockout()
        clock[0] += 151  # past whatever lockout was set, so the next round's failures are fresh

    hit_lockout()  # final round: lockout must be capped at exactly 150s, not ~6400s
    with pytest.raises(HTTPException):
        rate_limit.enforce_not_locked_out("token_validation", "9.9.9.9")
    clock[0] += 149
    with pytest.raises(HTTPException):
        rate_limit.enforce_not_locked_out("token_validation", "9.9.9.9")
    clock[0] += 2
    rate_limit.enforce_not_locked_out("token_validation", "9.9.9.9")


def test_rate_limiter_success_clears_prior_failures_and_lockout_state() -> None:
    for _ in range(4):
        rate_limit.record_attempt(
            "token_validation", "8.8.8.8", success=False,
            max_failures=5, window_seconds=60, base_lockout_seconds=60, max_lockout_seconds=900,
        )
    rate_limit.record_attempt(
        "token_validation", "8.8.8.8", success=True,
        max_failures=5, window_seconds=60, base_lockout_seconds=60, max_lockout_seconds=900,
    )

    for _ in range(4):
        rate_limit.enforce_not_locked_out("token_validation", "8.8.8.8")
        rate_limit.record_attempt(
            "token_validation", "8.8.8.8", success=False,
            max_failures=5, window_seconds=60, base_lockout_seconds=60, max_lockout_seconds=900,
        )
    rate_limit.enforce_not_locked_out("token_validation", "8.8.8.8")


def test_rate_limiter_keys_are_isolated_per_source() -> None:
    for _ in range(5):
        rate_limit.record_attempt(
            "token_validation", "attacker", success=False,
            max_failures=5, window_seconds=60, base_lockout_seconds=60, max_lockout_seconds=900,
        )

    with pytest.raises(HTTPException):
        rate_limit.enforce_not_locked_out("token_validation", "attacker")
    rate_limit.enforce_not_locked_out("token_validation", "legitimate_customer")
