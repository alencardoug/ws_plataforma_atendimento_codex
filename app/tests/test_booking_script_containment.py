"""T096: the structural negative test proving Constitution Amendment
1.1.0's autonomous-send exception has not spread beyond
booking_script/send_scripted_message(). Source-level (AST) introspection,
not behavioral — proves the *shape* of the codebase, not just that a
particular test scenario happens not to trigger a leak.
specs/004-dynamic-appointment-availability/plan.md §9/§13,
acceptance.md §O."""

import ast
from pathlib import Path

import customer_care

ROOT = Path(customer_care.__file__).parent
BOOKING_SCRIPT_DIR = ROOT / "booking_script"


def _iter_source_files() -> list[Path]:
    return [path for path in ROOT.rglob("*.py") if "__pycache__" not in path.parts]


def _is_operator_message_call(node: ast.AST) -> bool:
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Message"):
        return False
    return any(kw.arg == "author_type" and isinstance(kw.value, ast.Constant) and kw.value.value == "OPERATOR" for kw in node.keywords)


def _function_has_current_operator_param(func: ast.FunctionDef) -> bool:
    args = [*func.args.args, *func.args.kwonlyargs]
    for arg in args:
        if arg.annotation is not None and "CurrentOperator" in ast.dump(arg.annotation):
            return True
    return False


def _find_operator_message_construction_sites() -> list[tuple[Path, ast.FunctionDef]]:
    """Every enclosing function (anywhere under customer_care/) that
    contains a `Message(..., author_type="OPERATOR", ...)` call."""
    sites: list[tuple[Path, ast.FunctionDef]] = []
    for path in _iter_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for call in ast.walk(node):
                    if _is_operator_message_call(call):
                        sites.append((path, node))
    return sites


def test_every_operator_message_construction_site_outside_booking_script_requires_current_operator() -> None:
    sites = _find_operator_message_construction_sites()
    outside_booking_script = [(path, func) for path, func in sites if BOOKING_SCRIPT_DIR not in path.parents]
    assert outside_booking_script, "expected at least one OPERATOR Message construction site outside booking_script/ (operator_workspace/router.py's send_operator_message) — if this list is empty, this test itself may have broken, not the containment"
    for path, func in outside_booking_script:
        assert _function_has_current_operator_param(func), f"{path}:{func.name} constructs an OPERATOR Message without a CurrentOperator-annotated parameter — a potential second autonomous-send path"


def test_booking_script_has_exactly_one_operator_message_construction_site() -> None:
    sites = _find_operator_message_construction_sites()
    inside_booking_script = [(path, func) for path, func in sites if BOOKING_SCRIPT_DIR in path.parents]
    assert len(inside_booking_script) == 1, inside_booking_script
    path, func = inside_booking_script[0]
    assert path.name == "service.py"
    assert func.name == "send_scripted_message"


def test_send_scripted_message_is_imported_only_within_booking_script() -> None:
    importing_files: list[Path] = []
    for path in _iter_source_files():
        if BOOKING_SCRIPT_DIR in path.parents:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(alias.name == "send_scripted_message" for alias in node.names):
                importing_files.append(path)
    assert importing_files == [], f"send_scripted_message imported outside booking_script/: {importing_files}"


def test_advance_booking_script_is_called_only_from_send_customer_message() -> None:
    """plan.md §8b "Trigger" — not the typing-heartbeat endpoint, not any
    GET/poll path, not any operator-authenticated endpoint."""
    calling_functions: list[tuple[Path, str]] = []
    for path in _iter_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for call in ast.walk(node):
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "advance_booking_script":
                        calling_functions.append((path, node.name))
    assert calling_functions == [(ROOT / "anonymous_access" / "router.py", "send_customer_message")]
