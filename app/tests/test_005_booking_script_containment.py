"""005, tasks.md T061 (revised 2026-08-19, D-033): this feature's own
import-graph containment check — complements the pre-existing
tests/test_booking_script_containment.py (AST-based, proves no
OPERATOR-authored `Message` construction site exists outside
`booking_script/`, and that `send_scripted_message`/`advance_booking_script`
have exactly the one caller each they're supposed to — GB never adds a
second one). D-033 narrowed this feature's own containment claim: GB now
imports `booking_script.parsing`'s pure functions (`extract_cpf`,
`extract_payment_confirmation` — no DB, no I/O, no autonomous-send
coupling, reused instead of duplicating CPF/payment-format logic) to
implement its own, separate, N2-draft-only CPF/payment flow. What must
never happen is GB importing `booking_script.service` (home of
`send_scripted_message`, the one autonomous-send function) or calling
`advance_booking_script`/`send_scripted_message` by name, and
`booking_script/*` must never import from `scheduling.guided_booking`.
AST-based throughout (not raw-text search) so this stays accurate
regardless of docstring wording. specs/005-dynamic-pricing-and-guided-
booking/spec.md §8 outcome 8, plan.md §2/§10, DECISIONS.md D-033."""

import ast
import inspect
from types import ModuleType

from customer_care.booking_script import parsing, service
from customer_care.scheduling import guided_booking


def _import_module_names(module: ModuleType) -> list[str]:
    """Every dotted module name this module imports from, via `ast`
    (ignores docstrings/comments entirely, unlike a raw-text scan)."""
    tree = ast.parse(inspect.getsource(module))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return names


def _called_function_names(module: ModuleType) -> set[str]:
    tree = ast.parse(inspect.getsource(module))
    return {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}


class TestNoServiceCoupling:
    def test_guided_booking_never_imports_booking_script_service(self) -> None:
        assert not any(name.endswith("booking_script.service") or name == "customer_care.booking_script" for name in _import_module_names(guided_booking))

    def test_guided_booking_never_calls_send_scripted_message_or_advance_booking_script(self) -> None:
        called = _called_function_names(guided_booking)
        assert "send_scripted_message" not in called
        assert "advance_booking_script" not in called

    def test_booking_script_service_does_not_import_guided_booking(self) -> None:
        assert not any("guided_booking" in name for name in _import_module_names(service))

    def test_booking_script_parsing_does_not_import_guided_booking(self) -> None:
        assert not any("guided_booking" in name for name in _import_module_names(parsing))


class TestDisclosedParsingReuse:
    """The one narrow, intentional coupling this feature does have —
    verified precisely, not just "no coupling at all" (D-033 correction)."""

    def test_guided_booking_imports_only_the_pure_parsers_from_booking_script(self) -> None:
        booking_script_imports = [name for name in _import_module_names(guided_booking) if "booking_script" in name]
        assert booking_script_imports == ["customer_care.booking_script.parsing"], booking_script_imports

    def test_the_only_names_imported_from_it_are_the_two_pure_parsers(self) -> None:
        tree = ast.parse(inspect.getsource(guided_booking))
        imported_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "customer_care.booking_script.parsing":
                imported_names.extend(alias.name for alias in node.names)
        assert sorted(imported_names) == ["extract_cpf", "extract_payment_confirmation"]
