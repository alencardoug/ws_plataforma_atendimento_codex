"""010, tasks.md T25: this feature's own structural negative test proving
Constitution Amendment 1.2.0's governed-autonomy send exception is
exactly as narrow as the amendment describes — source-level (AST)
introspection, matching test_booking_script_containment.py's own
established pattern for Amendment 1.1.0. Complements (not replaces) that
file's own updated allowlist check.
specs/010-governed-autonomous-response/spec.md §3 GA-3/GA-4,
plan.md §4."""

import ast
import inspect
from pathlib import Path
from types import ModuleType

import customer_care
from customer_care.autonomy import service

ROOT = Path(customer_care.__file__).parent
AUTONOMY_DIR = ROOT / "autonomy"


def _iter_source_files() -> list[Path]:
    return [path for path in ROOT.rglob("*.py") if "__pycache__" not in path.parts]


def _import_module_names(module: ModuleType) -> list[str]:
    tree = ast.parse(inspect.getsource(module))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return names


def test_autonomy_service_has_exactly_one_operator_message_construction_site() -> None:
    tree = ast.parse(inspect.getsource(service))
    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for call in ast.walk(node):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "Message" and any(kw.arg == "author_type" and isinstance(kw.value, ast.Constant) and kw.value.value == "OPERATOR" for kw in call.keywords):
                    sites.append(node.name)
    assert sites == ["resolve_elapsed_autonomous_sends"], sites


def test_resolve_elapsed_autonomous_sends_is_imported_only_from_its_authorized_callers() -> None:
    """plan.md §4 — invoked from list_conversations() and
    operator_conversation_detail() (both in operator_workspace/router.py),
    both existing lazily-evaluated poll endpoints, never from a
    write/send-triggering endpoint."""
    importing_files: list[Path] = []
    for path in _iter_source_files():
        if AUTONOMY_DIR in path.parents:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(alias.name == "resolve_elapsed_autonomous_sends" for alias in node.names):
                importing_files.append(path)
    assert importing_files == [ROOT / "operator_workspace" / "router.py"], importing_files


def test_autonomy_service_does_not_import_booking_script() -> None:
    """No coupling between the two independently authorized autonomous-
    send exceptions — mirrors test_005_booking_script_containment.py's
    own no-coupling checks for guided_booking."""
    assert not any("booking_script" in name for name in _import_module_names(service))


def test_booking_script_service_does_not_import_autonomy() -> None:
    from customer_care.booking_script import service as booking_script_service

    assert not any("autonomy" in name for name in _import_module_names(booking_script_service))
