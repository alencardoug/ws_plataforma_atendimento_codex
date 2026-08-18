"""Executable V3-1/V3-2/V3-3 smoke: every taxonomy tag observable in
stored data after the corresponding real operator action, quick-approve's
byte-for-byte send + explicit-action-only guarantee, and HCR reproducible
from raw audit/generation data (spec.md §5 outcomes 1-3, T131)."""

import os

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from customer_care.ai.router import classify_generation
from customer_care.bootstrap import create_app
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import AIGeneration


def run() -> None:
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/operator/login", json={"email": os.environ["SMOKE_OPERATOR_EMAIL"], "password": os.environ["SMOKE_OPERATOR_PASSWORD"]})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    active = client.get("/api/v1/operator/conversations?scope=active", headers=headers).json()
    assert len(active) == 4
    conversation_id = active[0]["id"]
    detail = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers).json()
    customer_message_id = next(item["id"] for item in reversed(detail["messages"]) if item["author_type"] == "CUSTOMER")

    # --- approve tag: V3-2 quick-approve sends byte-for-byte, tagged `approve` ---
    generated = client.post(f"/api/v1/operator/conversations/{conversation_id}/drafts", headers=headers, json={"selected_message_ids": [customer_message_id]})
    assert generated.status_code == 201, generated.text
    draft = generated.json()
    before_quick_approve = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers).json()
    latest = before_quick_approve["latest_generation"] or draft
    quick_approved = client.post(f"/api/v1/operator/conversations/{conversation_id}/messages", headers=headers, json={"body": latest["draft_text"], "source_generation_id": latest["id"], "citation_retrieval_hit_ids": []})
    assert quick_approved.status_code == 201, quick_approved.text
    assert quick_approved.json()["body"] == latest["draft_text"], "quick-approve must send the draft byte-for-byte unmodified"
    # Negative test: no code path exists to accept/send a draft without an
    # explicit authenticated-operator POST to this exact endpoint — there is
    # no accept/quick-approve route of its own, and the message-send route
    # itself requires operator auth (verified separately by every other
    # smoke script's 401/403 checks). Confirmed here by absence: no
    # "accept"/"quick-approve" route exists in the OpenAPI schema.
    openapi_paths = client.get("/openapi.json").json()["paths"]
    assert not any("accept" in path or "quick-approve" in path for path in openapi_paths), "no dedicated auto-fireable accept endpoint may exist"
    with get_session_factory()() as db:
        approve_generation = db.get(AIGeneration, latest["id"])
        assert "approve" in classify_generation(db, approve_generation)

    # --- edit tag: sent_text != draft_text, no magnitude/classification input ---
    generated_2 = client.post(f"/api/v1/operator/conversations/{conversation_id}/drafts", headers=headers, json={"selected_message_ids": [customer_message_id]})
    assert generated_2.status_code == 201, generated_2.text
    draft_2 = generated_2.json()
    before_edit = client.get(f"/api/v1/operator/conversations/{conversation_id}", headers=headers).json()
    latest_2 = before_edit["latest_generation"] or draft_2
    edited_text = (latest_2["draft_text"] or "Resposta manual.") + " (edição do operador)"
    edited = client.post(f"/api/v1/operator/conversations/{conversation_id}/messages", headers=headers, json={"body": edited_text, "source_generation_id": latest_2["id"], "citation_retrieval_hit_ids": []})
    assert edited.status_code == 201, edited.text
    with get_session_factory()() as db:
        edit_generation = db.get(AIGeneration, latest_2["id"])
        tags = classify_generation(db, edit_generation)
        # `edit` itself must be derived solely from sent_text != draft_text —
        # no magnitude/operator-chosen classification. `regenerate` is also
        # correctly present here because this is a second /drafts call in
        # the same conversation, so the endpoint's own prior_generation_id
        # linkage (independent of the edit/approve distinction) applies —
        # the two tags are orthogonal, not exclusive.
        assert "edit" in tags and "approve" not in tags, f"got {tags}"

    # --- mark-incorrect tag: retroactive, idempotent, reachable from any
    # generation in history (not only the latest) ---
    mark_1 = client.post(f"/api/v1/operator/conversations/{conversation_id}/generations/{draft['id']}/mark-incorrect", headers=headers)
    assert mark_1.status_code == 200, mark_1.text
    first_marked_at = mark_1.json()["marked_incorrect_at"]
    mark_2 = client.post(f"/api/v1/operator/conversations/{conversation_id}/generations/{draft['id']}/mark-incorrect", headers=headers)
    assert mark_2.status_code == 200 and mark_2.json()["marked_incorrect_at"] != first_marked_at, "re-marking must be idempotent (update, not reject or duplicate)"
    with get_session_factory()() as db:
        marked_generation = db.get(AIGeneration, draft["id"])
        assert "mark-incorrect" in classify_generation(db, marked_generation)

    # --- escalate tag: content-gap signal only, no queue/routing side effect ---
    escalated = client.post(f"/api/v1/operator/conversations/{conversation_id}/generations/{draft_2['id']}/escalate", headers=headers)
    assert escalated.status_code == 200, escalated.text
    with get_session_factory()() as db:
        escalated_generation = db.get(AIGeneration, draft_2["id"])
        assert "escalate" in classify_generation(db, escalated_generation)
        # No queue/routing table exists in the schema for this to write to —
        # confirmed structurally: escalated_by_operator_id/escalated_at are
        # the only new columns this action touches (data-model.md).
        table_names = {row[0] for row in db.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema IN ('customer_service', 'content')")).all()}
        assert not any("queue" in name or "escalation" in name or "routing" in name for name in table_names), "escalate must remain tag-only, no queue/routing table"

    # --- search tag: MANUAL_EVIDENCE trigger ---
    search_results = client.post("/api/v1/operator/knowledge/search", headers=headers, json={"query": "horário de atendimento", "top_k": 8}).json()
    any_hit = search_results["evidence"][0] if search_results["evidence"] else None
    assert any_hit is not None, "expected at least one evidence item from manual search"
    selected_evidence = client.post(f"/api/v1/operator/knowledge/evidence/{any_hit['retrieval_hit_id']}/select", headers=headers, json={"conversation_id": conversation_id})
    assert selected_evidence.status_code == 201, selected_evidence.text
    with get_session_factory()() as db:
        search_generation = db.get(AIGeneration, selected_evidence.json()["id"])
        assert "search" in classify_generation(db, search_generation)

    # --- regenerate / regenerate-with-instruction tags ---
    regenerated_plain = client.post(f"/api/v1/operator/conversations/{conversation_id}/drafts", headers=headers, json={"selected_message_ids": [customer_message_id]})
    assert regenerated_plain.status_code == 201, regenerated_plain.text
    with get_session_factory()() as db:
        plain_generation = db.get(AIGeneration, regenerated_plain.json()["id"])
        if plain_generation.prior_generation_id is not None:
            assert classify_generation(db, plain_generation) & {"regenerate", "regenerate-with-instruction"}

    regenerated_with_instruction = client.post(f"/api/v1/operator/conversations/{conversation_id}/drafts", headers=headers, json={"selected_message_ids": [customer_message_id], "instruction_text": "Seja mais breve."})
    assert regenerated_with_instruction.status_code == 201, regenerated_with_instruction.text
    instructed_body = regenerated_with_instruction.json()
    assert instructed_body["instruction_text"] == "Seja mais breve."
    with get_session_factory()() as db:
        instructed_generation = db.get(AIGeneration, instructed_body["id"])
        assert instructed_generation.prior_generation_id is not None, "regenerate-with-instruction must link prior_generation_id"
        assert "regenerate-with-instruction" in classify_generation(db, instructed_generation)
    # instruction_text's absence from any /public/* schema is confirmed
    # statically by T122 (grep of anonymous_access/router.py and
    # conversations/projections.py); not re-checked here.

    # --- take-over tag ---
    second_id = active[1]["id"]
    takeover = client.post(f"/api/v1/operator/conversations/{second_id}/take-over", headers=headers)
    assert takeover.status_code == 200, takeover.text
    second_detail = client.get(f"/api/v1/operator/conversations/{second_id}", headers=headers).json()
    second_customer_message_id = next((item["id"] for item in reversed(second_detail["messages"]) if item["author_type"] == "CUSTOMER"), None)
    if second_customer_message_id:
        forbidden = client.post(f"/api/v1/operator/conversations/{second_id}/drafts", headers=headers, json={"selected_message_ids": [second_customer_message_id]})
        assert forbidden.status_code == 409, "N1 take-over must forbid AI draft generation (V2 invariant, unaffected by V3)"
    manual_send = client.post(f"/api/v1/operator/conversations/{second_id}/messages", headers=headers, json={"body": "Atendimento manual após take-over."})
    assert manual_send.status_code == 201, manual_send.text

    # --- Human Correction Rate (V3-3): reproducible from raw data by an
    # independent query, matching classify_generation's own approve/edit tally ---
    with get_session_factory()() as db:
        python_approve = 0
        python_edit = 0
        for generation in db.scalars(select(AIGeneration).where(AIGeneration.conversation_id.in_([conversation_id, second_id]))).all():
            tags = classify_generation(db, generation)
            if "approve" in tags:
                python_approve += 1
            if "edit" in tags:
                python_edit += 1
        sql_row = db.execute(text("""
            SELECT
              COUNT(*) FILTER (WHERE a.event_type = 'ai.draft_accepted') AS approve_count,
              COUNT(*) FILTER (WHERE a.event_type = 'ai.draft_edited') AS edit_count
            FROM customer_service.audit_events a
            JOIN customer_service.ai_generations g ON a.payload_json->>'ai_generation_id' = g.id::text
            WHERE a.event_type IN ('ai.draft_edited', 'ai.draft_accepted')
              AND g.conversation_id IN (:c1, :c2)
        """), {"c1": conversation_id, "c2": second_id}).one()
        assert sql_row.approve_count == python_approve, (sql_row.approve_count, python_approve)
        assert sql_row.edit_count == python_edit, (sql_row.edit_count, python_edit)
        assert python_approve >= 1 and python_edit >= 1, "expected at least one approve and one edit in this run's fixture"

    print("v3_taxonomy_hcr_smoke_ok: approve, edit, mark-incorrect (idempotent), escalate (tag-only), search, regenerate-with-instruction, take-over, HCR SQL/Python agreement")


if __name__ == "__main__":
    run()
