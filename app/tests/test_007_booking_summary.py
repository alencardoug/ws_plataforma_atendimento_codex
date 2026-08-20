"""007, tasks.md T14/T9: two kinds of coverage runnable without a live
database — (1) the containment claim BS-3 makes about
`booking_script/service.py`'s diff (mirrors `test_005_booking_script_
containment.py`'s AST-based style exactly), and (2) `render_booking_
summary_line()`'s two rendering branches (BS-7) against a lightweight
fake session, matching `test_automatic_draft_status.py`'s established
fake-session pattern. Real-database coverage for `record_appointment_
booking()`/`interpret_slot_choice()`'s column set/clear round-trip
belongs in `test_guided_booking.py`'s existing real-DB-integration style
(tasks.md T13) — not duplicated here.
specs/007-completed-booking-visibility/spec.md, plan.md §6, DECISIONS.md
D-037."""

import ast
import inspect
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from customer_care.booking_script import service
from customer_care.scheduling.availability import render_booking_summary_line


def _import_module_names(module: Any) -> list[str]:
    tree = ast.parse(inspect.getsource(module))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return names


class TestBookingScriptContainmentUnaffected:
    """BS-3: the only change to booking_script/service.py is one additive
    block calling record_appointment_booking() — never a new coupling to
    scheduling.guided_booking (test_005's own containment tests already
    re-verify that boundary and stay green after this feature — see
    test_005_booking_script_containment.py, reconfirmed passing)."""

    def test_service_still_does_not_import_guided_booking(self) -> None:
        assert not any("guided_booking" in name for name in _import_module_names(service))

    def test_service_imports_exactly_these_two_names_from_availability(self) -> None:
        tree = ast.parse(inspect.getsource(service))
        imported_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "customer_care.scheduling.availability":
                imported_names.extend(alias.name for alias in node.names)
        assert sorted(imported_names) == ["format_price_brl", "record_appointment_booking"]


class _QueueSession:
    """Returns queued values from successive .scalar() calls, in order —
    matching test_automatic_draft_status.py's established fake-session
    pattern, extended for functions that make more than one .scalar()
    call."""

    def __init__(self, values: list[Any]) -> None:
        self._values = list(values)

    def scalar(self, _statement: object) -> Any:
        return self._values.pop(0)


def _booking(**overrides: object) -> Any:
    base = {"specialty_id": uuid4(), "professional_id": None, "unit_id": None, "slot_starts_at": None}
    base.update(overrides)
    return SimpleNamespace(**base)


class TestRenderBookingSummaryLine:
    def test_specialty_only_line_when_no_slot_detail(self) -> None:
        session = _QueueSession(["Oncologia geral (triagem)"])
        line = render_booking_summary_line(session, _booking())  # type: ignore[arg-type]
        assert line == "Oncologia geral (triagem) confirmada (simulação)."

    def test_full_detail_line_when_professional_unit_and_slot_are_all_present(self) -> None:
        starts_at = datetime(2026, 8, 27, 8, 0, tzinfo=UTC)
        session = _QueueSession(["Oncologia geral (triagem)", "Dra. Renata Silveira (simulação)", "Unidade Central (simulação)"])
        booking = _booking(professional_id=uuid4(), unit_id=uuid4(), slot_starts_at=starts_at)
        line = render_booking_summary_line(session, booking)  # type: ignore[arg-type]
        assert line.startswith("Oncologia geral (triagem) — Dra. Renata Silveira (simulação), Unidade Central (simulação),")
        assert "(America/São_Paulo)" in line

    def test_never_a_placeholder_time_when_only_specialty_is_known(self) -> None:
        """The honesty limit (spec.md §6): a specialty-only booking must
        never imply a specific time slot in its rendered line."""
        session = _QueueSession(["Mastologia oncológica"])
        line = render_booking_summary_line(session, _booking())  # type: ignore[arg-type]
        assert "às" not in line
        assert "/" not in line
