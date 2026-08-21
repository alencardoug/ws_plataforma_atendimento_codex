"""011, tasks.md T25: this feature's own structural negative test proving
Constitution Amendment 1.3.0's N5 exception is exactly as narrow as the
amendment describes — source-level (AST) introspection, matching
test_010_governed_autonomy_containment.py's own established pattern.
N5 adds a new upstream *generation* path (generate_ungoverned_reply), not
a second Message-construction site — resolve_elapsed_autonomous_sends()
remains the only one, unchanged from feature 010.
specs/011-ungoverned-fictional-demo-autonomy-n5/plan.md §3/§4."""

import ast
import inspect

from customer_care.ai import router as ai_router
from customer_care.autonomy import service


def test_generate_ungoverned_reply_is_the_only_ungoverned_n5_provider_site() -> None:
    tree = ast.parse(inspect.getsource(ai_router))
    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for call in ast.walk(node):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "AIGeneration" and any(kw.arg == "provider" and isinstance(kw.value, ast.Constant) and kw.value.value == "ungoverned-n5" for kw in call.keywords):
                    sites.append(node.name)
    assert sites == ["generate_ungoverned_reply"], sites


def test_autonomy_service_still_has_exactly_one_operator_message_construction_site() -> None:
    """N5 does not add a second non-operator-authenticated Message-
    construction site — it only adds a second upstream generation path
    (generate_ungoverned_reply) feeding the same existing send mechanism
    resolve_elapsed_autonomous_sends() already owns (plan.md §4)."""
    tree = ast.parse(inspect.getsource(service))
    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for call in ast.walk(node):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "Message" and any(kw.arg == "author_type" and isinstance(kw.value, ast.Constant) and kw.value.value == "OPERATOR" for kw in call.keywords):
                    sites.append(node.name)
    assert sites == ["resolve_elapsed_autonomous_sends"], sites


def test_generate_ungoverned_reply_never_attaches_evidence_sources() -> None:
    """spec.md N5-2/data-model.md §4: an ungoverned generation has no
    evidence to attribute — AIGenerationSource must never be constructed
    inside this function."""
    tree = ast.parse(inspect.getsource(ai_router.generate_ungoverned_reply))
    calls = [node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    assert "AIGenerationSource" not in calls, calls
