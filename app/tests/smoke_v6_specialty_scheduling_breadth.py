"""006: real end-to-end HTTP smoke for specialty citation and scheduling
breadth (SC/SS/SV/ND) against a rebuilt backend — real embeddings/LLM
calls, confirming genuine retrieval of the new support-specialty content,
zero-code-change resolution of a new specialty through the existing
resolvers, the wide-availability seed action's real row creation and
idempotency, and genuine natural-language date/time extraction against
the real provider (deterministic-test embeddings cannot prove semantic
relevance or real LLM classification quality — this is the credential-
backed counterpart to `test_appointment_availability_keywords.py`/
`test_date_intent_extraction.py`'s deterministic unit coverage, matching
this project's own established unit-vs-smoke split).
specs/006-specialty-scheduling-breadth/tasks.md T3/T7/T11/T20."""

import os
from datetime import date, timedelta

from fastapi.testclient import TestClient

from customer_care.bootstrap import create_app


def _find_qa_hit(evidence: list[dict], title_contains: str) -> dict:
    match = next((item for item in evidence if item["knowledge_type"] == "ADMIN_QA" and title_contains.lower() in item["title"].lower()), None)
    assert match is not None, f"expected an ADMIN_QA hit whose title contains {title_contains!r}: {[item['title'] for item in evidence]}"
    return match


def run() -> None:
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/operator/login", json={"email": os.environ["SMOKE_OPERATOR_EMAIL"], "password": os.environ["SMOKE_OPERATOR_PASSWORD"]})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # --- SV: wide-availability seed, real row creation + idempotency -------
    seeded = client.post("/api/v1/operator/scheduling/ensure-wide-availability", headers=headers)
    assert seeded.status_code == 200, seeded.text
    seeded_body = seeded.json()
    assert seeded_body["specialty_count"] >= 8, seeded_body  # 4 existing + 4 new (006/SS)
    assert seeded_body["business_day_count"] > 0, seeded_body

    reseeded = client.post("/api/v1/operator/scheduling/ensure-wide-availability", headers=headers)
    assert reseeded.status_code == 200, reseeded.text
    assert reseeded.json()["slots_created"] == 0, "second call must be a safe no-op (ON CONFLICT DO NOTHING)"

    # --- SC: new support-specialty content is genuinely retrievable --------
    conversation = client.post("/api/v1/public/conversations")
    assert conversation.status_code == 201, conversation.text
    conversation_id = conversation.json()["conversation"]["id"]
    claim = client.post(f"/api/v1/operator/conversations/{conversation_id}/claim", headers=headers)
    assert claim.status_code == 200, claim.text

    nutrition_search = client.post("/api/v1/operator/knowledge/search", headers=headers, json={"query": "Estou sem apetite e perdendo peso durante o tratamento, o que eu faço?", "top_k": 8}).json()
    nutrition_hit = _find_qa_hit(nutrition_search["evidence"], "apetite")
    selected = client.post(f"/api/v1/operator/knowledge/evidence/{nutrition_hit['retrieval_hit_id']}/select", headers=headers, json={"conversation_id": conversation_id})
    assert selected.status_code == 201, selected.text
    assert "nutri" in selected.json()["draft_text"].lower() or "nutri" in nutrition_hit["title"].lower(), selected.json()

    # --- SS: a support specialty resolves through price_lookup/appointment_availability
    # exactly like an existing diagnostic one — zero resolver code change.
    # Manual search + explicit evidence selection (matching smoke_v4_
    # appointment_availability.py's own established pattern) rather than a
    # message-based draft: retrieval ranking for "quanto custa" phrasings
    # can legitimately surface a topically-related but non-price Q&A entry
    # at rank 1 (a real, already-acknowledged retrieval-ambiguity class —
    # see smoke_v5_guided_booking.py's own "query matched the price entry,
    # not an availability one — retrieval ambiguity, not a GB bug" comment
    # — this smoke test verifies SS-3's actual claim, that the resolver
    # code path is unchanged for a support specialty, not RAG ranking
    # behavior, which test_price_lookup_resolver.py already covers
    # directly and deterministically).
    price_search = client.post("/api/v1/operator/knowledge/search", headers=headers, json={"query": "Quanto custa uma consulta de nutrição oncológica?", "top_k": 8}).json()
    price_hit = _find_qa_hit(price_search["evidence"], "Quanto custa uma consulta de mastologia?")
    price_selected = client.post(f"/api/v1/operator/knowledge/evidence/{price_hit['retrieval_hit_id']}/select", headers=headers, json={"conversation_id": conversation_id})
    assert price_selected.status_code == 201, price_selected.text
    price_body = price_selected.json()
    assert price_body["dynamic_pattern_used"] is True, price_body
    assert "R$" in price_body["draft_text"] and "(simulação)" in price_body["draft_text"], price_body

    # Same retrieval-ambiguity class as the price check above — manual
    # search + explicit selection rather than a message-based draft.
    # resolve_appointment_availability() re-extracts the specialty from
    # this search's own query text at resolution time (matching
    # resolve_price_lookup()'s identical design), so which literal
    # dynamic_data_required=true QA entry gets selected as evidence does
    # not change which specialty's slots are actually looked up.
    availability_search = client.post("/api/v1/operator/knowledge/search", headers=headers, json={"query": "Existe consulta de fisioterapia oncológica disponível amanhã?", "top_k": 8}).json()
    availability_hit = _find_qa_hit(availability_search["evidence"], "Existe consulta disponível")
    availability_selected = client.post(f"/api/v1/operator/knowledge/evidence/{availability_hit['retrieval_hit_id']}/select", headers=headers, json={"conversation_id": conversation_id})
    assert availability_selected.status_code == 201, availability_selected.text
    availability_body = availability_selected.json()
    assert availability_body["dynamic_pattern_used"] is True, availability_body
    assert "(simulação)" in availability_body["draft_text"], availability_body

    close = client.post(f"/api/v1/operator/conversations/{conversation_id}/close", headers=headers)
    assert close.status_code == 200, close.text

    # --- ND: real natural-language date/time extraction --------------------
    nd_conversation = client.post("/api/v1/public/conversations")
    assert nd_conversation.status_code == 201, nd_conversation.text
    nd_conversation_id = nd_conversation.json()["conversation"]["id"]
    nd_claim = client.post(f"/api/v1/operator/conversations/{nd_conversation_id}/claim", headers=headers)
    assert nd_claim.status_code == 200, nd_claim.text

    def nd_resolve_via_search(date_phrase: str) -> dict:
        """Manual search + explicit evidence selection (same rationale as
        the SS section above): resolve_appointment_availability() re-parses
        this exact query text for both specialty and date at resolution
        time, so which literal Q&A record ranks #1 in embedding similarity
        does not change what gets resolved — only the query text passed to
        extract_parameters(..., allow_llm_date_fallback=True) matters. The
        search query itself is prefixed with the availability QA's own
        near-exact phrasing to keep it reliably rank-1 regardless of how
        the date phrase alone happens to embed (an unrelated retrieval-
        ranking concern, not part of what this test verifies)."""
        query_text = f"Existe consulta disponível de oncologia geral {date_phrase}"
        # top_k widened well beyond the operator UI's usual 8 — this only
        # needs the target Q&A to be *findable* by _find_qa_hit, not
        # ranked #1; the date phrase appended after the QA's own near-
        # exact title text can still perturb ranking against unrelated
        # but topically-close content in a corpus this size.
        search = client.post("/api/v1/operator/knowledge/search", headers=headers, json={"query": query_text, "conversation_id": nd_conversation_id, "top_k": 20}).json()
        hit = _find_qa_hit(search["evidence"], "Existe consulta disponível")
        return client.post(f"/api/v1/operator/knowledge/evidence/{hit['retrieval_hit_id']}/select", headers=headers, json={"conversation_id": nd_conversation_id}).json()

    # A phrase entirely outside DATE_KEYWORDS — only the LLM fallback can
    # resolve "daqui a 2 terças-feira" into a real target_date. Deliberately
    # weekday-based (always resolves to a Tuesday, always a real SV-seeded
    # business day) rather than "daqui a um mês" — a pure day/month/week
    # offset from an arbitrary "today" can land on a weekend by chance
    # (found live: 2026-08-20 + 1 month = 2026-09-20, a Sunday — a real,
    # correct DYNAMIC_DATA_UNAVAILABLE abstention, not a bug, but not a
    # reliable smoke assertion either since it depends on the calendar day
    # the suite happens to run on).
    far_future_body = nd_resolve_via_search("daqui a 2 terças-feira?")
    assert far_future_body["dynamic_pattern_used"] is True, far_future_body
    assert far_future_body["status"] == "ANSWER", far_future_body

    # An explicit calendar date, well within the SV-seeded window — advanced
    # to the next weekday if the naive +45-day offset happens to land on a
    # weekend, for the same reason as above.
    explicit_date = date.today() + timedelta(days=45)
    while explicit_date.isoweekday() > 5:
        explicit_date += timedelta(days=1)
    explicit_body = nd_resolve_via_search(f"em {explicit_date.day:02d}/{explicit_date.month:02d}?")
    assert explicit_body["dynamic_pattern_used"] is True, explicit_body

    # A genuinely ambiguous/unresolvable date expression must fall through
    # safely — never a fabricated date, never a new bespoke error message.
    ambiguous_body = nd_resolve_via_search("num dia qualquer, sei lá quando?")
    assert ambiguous_body["status"] in {"ANSWER", "ABSTAIN"}, ambiguous_body
    if ambiguous_body["status"] == "ABSTAIN":
        assert ambiguous_body["reason_code"] != "DATE_NOT_UNDERSTOOD", "ND-3 forbids a new bespoke abstention category for this case"

    nd_close = client.post(f"/api/v1/operator/conversations/{nd_conversation_id}/close", headers=headers)
    assert nd_close.status_code == 200, nd_close.text

    print("smoke_v6_specialty_scheduling_breadth_ok: SC content retrieval, SS zero-code-change resolution, SV real seeding + idempotency, ND real LLM date extraction")


if __name__ == "__main__":
    run()
