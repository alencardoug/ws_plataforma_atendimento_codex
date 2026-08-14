import time
from dataclasses import dataclass, field

from customer_care.shared.errors import api_error


@dataclass
class _LimiterState:
    failures: list[float] = field(default_factory=list)
    lockout_until: float | None = None
    consecutive_lockouts: int = 0


_state: dict[tuple[str, str], _LimiterState] = {}


def _now() -> float:
    return time.monotonic()


def enforce_not_locked_out(bucket: str, key: str) -> None:
    """Raise 429 if this bucket/key is currently in a lockout window."""
    state = _state.get((bucket, key))
    if state is not None and state.lockout_until is not None and _now() < state.lockout_until:
        raise api_error(429, "RATE_LIMITED", "Too many attempts; try again later")


def record_attempt(
    bucket: str,
    key: str,
    *,
    success: bool,
    max_failures: int,
    window_seconds: float,
    base_lockout_seconds: float,
    max_lockout_seconds: float,
) -> None:
    """Record a validation outcome; escalate lockout duration on repeated failures.

    A successful attempt clears failure/lockout history for this bucket/key.
    Call `enforce_not_locked_out` before the validation attempt this records.
    """
    state = _state.setdefault((bucket, key), _LimiterState())
    now = _now()
    if success:
        state.failures.clear()
        state.lockout_until = None
        state.consecutive_lockouts = 0
        return
    state.failures = [attempt for attempt in state.failures if now - attempt < window_seconds]
    state.failures.append(now)
    if len(state.failures) >= max_failures:
        state.consecutive_lockouts += 1
        lockout = min(base_lockout_seconds * (2 ** (state.consecutive_lockouts - 1)), max_lockout_seconds)
        state.lockout_until = now + lockout
        state.failures.clear()


def reset_all() -> None:
    """Test-only: clear all limiter state."""
    _state.clear()
