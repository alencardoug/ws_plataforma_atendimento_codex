"""T071: real end-to-end HTTP smoke for dynamic appointment availability
(AA-1..AA-9) against a rebuilt backend — real embeddings retrieval, real
seed action, real resolver, zero LLM calls for a resolved generation, and
confirms unimplemented resolvers (price_lookup/payment_simulator/
insurance_lookup) still abstain exactly as before this feature.
specs/004-dynamic-appointment-availability/tasks.md T071, acceptance.md
§A/§H."""

import os

from fastapi.testclient import TestClient

from customer_care.bootstrap import create_app

# A pure-database resolution never calls a real LLM/embedding generation
# provider — real OpenAI chat-completion latency is reliably >> this, so a
# generation this fast is strong evidence no such call happened (matches
# acceptance.md §A.2's documented alternative to a provider call-spy).
MAX_DYNAMIC_RESOLUTION_MS = 1000


def _find_admin_qa_hit(evidence: list[dict], title: str) -> str:
    """`select_evidence` (V2-3 "Buscar evidências") lets a specific hit be
    chosen explicitly, unlike the message-context draft flow — used here so
    this smoke test's outcome depends on this feature's own resolver, not
    on this shared local corpus's current retrieval ranking (which other,
    unrelated test suites against the same database can and do perturb)."""
    match = next((item for item in evidence if item["knowledge_type"] == "ADMIN_QA" and item["title"] == title), None)
    assert match is not None, f"expected an ADMIN_QA hit titled {title!r} in manual search results: {evidence}"
    return match["retrieval_hit_id"]


def run() -> None:
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/operator/login", json={"email": os.environ["SMOKE_OPERATOR_EMAIL"], "password": os.environ["SMOKE_OPERATOR_PASSWORD"]})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Guarantee real data exists (Phase 4's endpoint) before asking about it.
    seeded = client.post("/api/v1/operator/scheduling/ensure-availability", headers=headers)
    assert seeded.status_code == 200, seeded.text

    conversation = client.post("/api/v1/public/conversations")
    assert conversation.status_code == 201, conversation.text
    conversation_id = conversation.json()["conversation"]["id"]
    claim = client.post(f"/api/v1/operator/conversations/{conversation_id}/claim", headers=headers)
    assert claim.status_code == 200, claim.text

    search = client.post("/api/v1/operator/knowledge/search", headers=headers, json={"query": "Existe consulta disponível amanhã?", "top_k": 8})
    assert search.status_code == 200, search.text
    hit_id = _find_admin_qa_hit(search.json()["evidence"], "Existe consulta disponível amanhã?")

    selected = client.post(f"/api/v1/operator/knowledge/evidence/{hit_id}/select", headers=headers, json={"conversation_id": conversation_id})
    assert selected.status_code == 201, selected.text
    body = selected.json()
    assert body["status"] == "ANSWER", body
    assert body["model"] == "not-applicable", body
    assert body["dynamic_pattern_used"] is True, body
    assert "(simulação)" in body["draft_text"], body
    assert "R$" in body["draft_text"], body
    for forbidden in ("schedule_slots", "scheduling.", "specialty_id"):
        assert forbidden not in body["draft_text"], body
    assert body["duration_ms"] < MAX_DYNAMIC_RESOLUTION_MS, body

    # price_lookup/payment_simulator/insurance_lookup remain unimplemented —
    # this entry still abstains exactly as before this feature (outcome 8).
    price_conversation = client.post("/api/v1/public/conversations")
    assert price_conversation.status_code == 201, price_conversation.text
    price_conversation_id = price_conversation.json()["conversation"]["id"]
    price_claim = client.post(f"/api/v1/operator/conversations/{price_conversation_id}/claim", headers=headers)
    assert price_claim.status_code == 200, price_claim.text

    price_search = client.post("/api/v1/operator/knowledge/search", headers=headers, json={"query": "Quanto custa uma consulta de mastologia?", "top_k": 8})
    assert price_search.status_code == 200, price_search.text
    price_hit_id = _find_admin_qa_hit(price_search.json()["evidence"], "Quanto custa uma consulta de mastologia?")

    price_selected = client.post(f"/api/v1/operator/knowledge/evidence/{price_hit_id}/select", headers=headers, json={"conversation_id": price_conversation_id})
    assert price_selected.status_code == 201, price_selected.text
    price_body = price_selected.json()
    assert price_body["status"] == "ABSTAIN", price_body
    assert price_body["reason_code"] == "DYNAMIC_DATA_UNAVAILABLE", price_body
    assert price_body["draft_text"] == "", price_body

    # Close both — otherwise repeated runs against the same operator/DB
    # eventually hit OPERATOR_MAX_ACTIVE_CONVERSATIONS (a real failure this
    # smoke test tripped over once already in this session).
    for cid in (conversation_id, price_conversation_id):
        closed = client.post(f"/api/v1/operator/conversations/{cid}/close", headers=headers)
        assert closed.status_code == 200, closed.text

    print("smoke_v4_appointment_availability_ok: real seed action, real resolver, zero-LLM dynamic resolution, unimplemented-resolver regression")


if __name__ == "__main__":
    run()
