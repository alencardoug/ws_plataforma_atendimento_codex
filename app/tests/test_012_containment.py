"""012, tasks.md T17: structural negative tests proving the two changes in
this cycle are exactly as narrow as spec.md / plan.md describe —
source-level (AST) introspection, matching
test_011_ungoverned_n5_containment.py's established pattern.

- 'MANUAL_BOOKING_OFFER' is constructed in exactly one function
  (generate_booking_offer_draft); maybe_open_autonomous_window()'s
  eligibility guard is unchanged, so an OB generation can never be
  autonomously sent (Constitution Amendment 1.2.0 clause (b)).
- AC's slot-creation entry points (ensure_generalist_floor /
  run_bootstrap_seed) are never imported by the query/resolver modules
  (specs/004 clarification item 6 preserved).
"""

import ast
import inspect

from customer_care.ai import router as ai_router
from customer_care.anonymous_access import router as anon_router
from customer_care.scheduling import availability as scheduling_availability


def _funcs_constructing_trigger(module, trigger_value: str) -> list[str]:
    tree = ast.parse(inspect.getsource(module))
    sites: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for call in ast.walk(node):
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id == "AIGeneration"
                    and any(kw.arg == "trigger" and isinstance(kw.value, ast.Constant) and kw.value.value == trigger_value for kw in call.keywords)
                ):
                    sites.append(node.name)
    return sites


def test_manual_booking_offer_trigger_has_one_construction_function() -> None:
    sites = _funcs_constructing_trigger(ai_router, "MANUAL_BOOKING_OFFER")
    # ANSWER/ABSTAIN happy path + the FAILED fallback are both inside the
    # one function, so the function name appears (possibly twice) but no
    # other function.
    assert set(sites) == {"generate_booking_offer_draft"}, sites


def test_manual_booking_offer_is_not_autonomous_eligible() -> None:
    """maybe_open_autonomous_window()'s early-return guard must still key
    only on 'AUTOMATIC' and the GB flow triggers — never
    'MANUAL_BOOKING_OFFER'."""
    src = inspect.getsource(ai_router.maybe_open_autonomous_window)
    assert "MANUAL_BOOKING_OFFER" not in src
    assert 'generation.trigger != "AUTOMATIC"' in src


def test_ac_seed_entrypoints_not_imported_by_query_or_anonymous_modules() -> None:
    """ensure_generalist_floor / run_bootstrap_seed create slots; they must
    never be reachable from a customer/operator *query* path
    (resolve_appointment_availability lives in scheduling.availability;
    the customer message path lives in anonymous_access.router)."""
    for module in (scheduling_availability, anon_router):
        src = inspect.getsource(module)
        assert "ensure_generalist_floor" not in src, module.__name__
        assert "run_bootstrap_seed" not in src, module.__name__
        assert "bootstrap_seed" not in src, module.__name__


def test_ai_router_does_not_create_slots() -> None:
    """ai/router.py (draft generation, OB) must not import or call any
    slot-creation seeding function."""
    src = inspect.getsource(ai_router)
    for forbidden in ("ensure_generalist_floor", "ensure_seed_availability", "ensure_wide_availability", "run_bootstrap_seed", "create_slots_on"):
        assert forbidden not in src, forbidden
