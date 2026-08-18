"""Executable V3-8 smoke: guided knowledge-CRUD inputs — the category
registry always reflects live data (no client-side staleness), the
dynamic-table dropdown never lists a non-allowlisted table, and column
introspection is scoped strictly to the allowlist via real
`information_schema`-backed reflection, never arbitrary schema access
(spec.md §5 outcome 9, T131)."""

import os
from uuid import uuid4

from fastapi.testclient import TestClient

from customer_care.bootstrap import create_app
from customer_care.knowledge.dynamic_binding import ALLOWLISTED_TABLES


def run() -> None:
    client = TestClient(create_app())
    login = client.post("/api/v1/auth/operator/login", json={"email": os.environ["SMOKE_OPERATOR_EMAIL"], "password": os.environ["SMOKE_OPERATOR_PASSWORD"]})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Authorization: no operator credential reaches these routes.
    anon_categories = client.get("/api/v1/operator/knowledge/categories")
    assert anon_categories.status_code == 401, anon_categories.text
    anon_tables = client.get("/api/v1/operator/knowledge/dynamic-tables")
    assert anon_tables.status_code == 401, anon_tables.text

    # --- category registry: no staleness ---
    before = client.get("/api/v1/operator/knowledge/categories", headers=headers)
    assert before.status_code == 200, before.text
    before_slugs = {item["slug"] for item in before.json()}

    new_slug = f"smoke-cat-{uuid4().hex[:8]}"
    created = client.post("/api/v1/operator/knowledge/categories", headers=headers, json={"slug": new_slug, "label": "Categoria sintética de smoke"})
    assert created.status_code == 201, created.text
    assert created.json()["slug"] == new_slug and created.json()["is_active"] is True

    duplicate = client.post("/api/v1/operator/knowledge/categories", headers=headers, json={"slug": new_slug, "label": "Duplicada"})
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "CATEGORY_EXISTS", duplicate.text

    after = client.get("/api/v1/operator/knowledge/categories", headers=headers)
    after_slugs = {item["slug"] for item in after.json()}
    assert new_slug not in before_slugs, "fixture slug must not have pre-existed"
    assert new_slug in after_slugs, "a freshly created category must be immediately visible — no caching/staleness layer"

    # The registry is genuinely shared: creating a Q&A entry with an
    # existing category and a clinical document with a cancer_type both key
    # off the same content.categories table (plan.md §3.1) — proven earlier
    # by the migration's backfill (T005) and the category_slug derivation
    # unit tests (test_category_derivation.py); not re-proven here via a
    # second live write to keep this script's fixture footprint small.

    # --- dynamic-table dropdown: never lists a non-allowlisted table ---
    tables = client.get("/api/v1/operator/knowledge/dynamic-tables", headers=headers)
    assert tables.status_code == 200, tables.text
    listed_tables = set(tables.json())
    assert listed_tables == set(ALLOWLISTED_TABLES.keys()), "dropdown must reflect ALLOWLISTED_TABLES exactly, no more no less"
    assert "audit_events" not in listed_tables and "operators" not in listed_tables, "must never list a sensitive/non-fixture table"

    # --- column introspection: allowlisted table only, real columns ---
    columns = client.get("/api/v1/operator/knowledge/dynamic-tables/knowledge_dynamic_fixture/columns", headers=headers)
    assert columns.status_code == 200, columns.text
    column_names = {item["column"] for item in columns.json()}
    assert column_names == {"id", "category", "status", "label", "ordinal"}, column_names

    # Non-allowlisted table: 404 before any introspection happens — never a
    # raw information_schema query against an arbitrary name (plan.md §11/§18).
    rejected_table = client.get("/api/v1/operator/knowledge/dynamic-tables/audit_events/columns", headers=headers)
    assert rejected_table.status_code == 404, rejected_table.text
    rejected_nonexistent = client.get("/api/v1/operator/knowledge/dynamic-tables/not_a_real_table_at_all/columns", headers=headers)
    assert rejected_nonexistent.status_code == 404, rejected_nonexistent.text

    # A Q&A entry's dynamic_binding write path already validates
    # source_table/output_columns against this exact allowlist at write time
    # (smoke_v2_knowledge_crud.py's INVALID_DYNAMIC_BINDING checks, V2-8);
    # not duplicated here.

    print("v3_knowledge_guided_smoke_ok: category registry freshness, allowlisted table dropdown, real-column introspection, non-allowlisted 404")


if __name__ == "__main__":
    run()
