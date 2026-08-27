"""012 / AC-1 — stack-startup / admin entry point for the idempotent
appointment-availability bootstrap fill.

Two invocation routes, one idempotent body
(`scheduling.seeding.run_bootstrap_seed`):

1. `python -m customer_care.scheduling.bootstrap_seed` — an explicit
   admin command, matching this project's established "administrative
   command, not a UI" pattern (README's `alembic upgrade head` /
   `python -m customer_care.knowledge.ingest` sequence). Running it is
   itself the opt-in — no env flag.
2. The env-gated FastAPI `lifespan` startup hook in `app/main.py` calls
   `maybe_run_bootstrap_seed_on_startup()` below, which does nothing
   unless `RUN_BOOTSTRAP_SEED` is truthy. This is app startup, not a
   request/query side effect — `specs/004` clarification item 6 is about
   the resolver/query path, which is untouched.

See spec.md §5 AC-1, plan.md §2, DECISIONS.md D-044.
"""

import os

from customer_care.infrastructure.database import get_session_factory
from customer_care.scheduling.seeding import run_bootstrap_seed

_TRUTHY = {"1", "true", "yes", "on"}


def _flag_enabled() -> bool:
    return os.environ.get("RUN_BOOTSTRAP_SEED", "").strip().lower() in _TRUTHY


def maybe_run_bootstrap_seed_on_startup() -> None:
    """Called from the app lifespan startup. No-op unless RUN_BOOTSTRAP_SEED
    is set — so the test process (which never sets it) never seeds, and a
    plain `uvicorn` run only seeds when the operator opted in via env."""
    if not _flag_enabled():
        return
    with get_session_factory()() as session:
        run_bootstrap_seed(session)


def main() -> None:
    """`python -m customer_care.scheduling.bootstrap_seed` — unconditional;
    invoking it is the explicit opt-in."""
    with get_session_factory()() as session:
        run_bootstrap_seed(session)


if __name__ == "__main__":
    main()
