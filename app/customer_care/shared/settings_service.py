"""011: get_system_settings(), moved here (verbatim) from
operator_workspace/router.py so ai/router.py can also read it —
operator_workspace/router.py already imports from ai/router.py, so
importing the other way around would be circular. That module re-imports
this function for its own existing call sites; its behavior is unchanged."""

from customer_care.infrastructure.models import SystemSettings
from customer_care.shared.dependencies import DbSession
from customer_care.shared.errors import api_error


def get_system_settings(session: DbSession) -> SystemSettings:
    """The migration that creates `system_settings` also seeds its one
    singleton row — a missing row here means that migration never ran,
    not a legitimate empty-settings state."""
    settings = session.get(SystemSettings, True)
    if not settings:
        raise api_error(500, "SETTINGS_MISSING", "system_settings singleton row is missing")
    return settings
