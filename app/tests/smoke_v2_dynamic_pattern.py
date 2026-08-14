"""Executable V2-6 dynamic-evidence resolver smoke: allowlist enforcement,
deterministic substitution, and every documented fallback mode.

Tests the resolver directly (not via HTTP/vector search) since the mechanism
itself — not retrieval — is what's under test here; test_ai_providers.py and
the *_router* smoke scripts already cover how evidence reaches this point.
"""

from uuid import uuid4

from sqlalchemy import delete

from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import DynamicFixtureRow, QADynamicBinding, QAEntry
from customer_care.knowledge.dynamic_binding import DynamicResolutionError, resolve_dynamic_pattern


def expect_failure(db, qa: QAEntry, needle: str) -> None:
    try:
        resolve_dynamic_pattern(db, qa)
    except DynamicResolutionError as exc:
        assert needle in exc.cause, exc.cause
    else:
        raise AssertionError(f"expected DynamicResolutionError containing {needle!r}")


def run() -> None:
    session_factory = get_session_factory()
    qa_id = f"smoke-dynamic-{uuid4().hex[:8]}"
    category = f"smoke-{uuid4().hex[:8]}"
    try:
        with session_factory() as db:
            qa = QAEntry(qa_id=qa_id, category="smoke-fixture", question="Pergunta sintética de teste", answer_markdown="Vaga: {{slot}} (status {{status}})", dynamic_data_required=True, customer_citation_allowed=False)
            db.add(qa)
            db.commit()

            # 1) No binding configured: closes the original V1 finding — must
            # never fall through to a literal/unfiltered answer.
            expect_failure(db, qa, "no dynamic binding")

            # 2) Binding present but table not in the server-side allowlist.
            db.add(QADynamicBinding(qa_id=qa_id, source_table="not_allowlisted_table", filter={}, output_columns=[{"column": "label", "variable_name": "slot"}], row_limit=4))
            db.commit()
            expect_failure(db, qa, "not in the allowlist")

            # 3) Allowlisted table, but the filter matches zero rows.
            binding = db.get(QADynamicBinding, qa_id)
            assert binding is not None
            binding.source_table = "knowledge_dynamic_fixture"
            binding.filter = {"category": "smoke-nonexistent-category"}
            binding.output_columns = [{"column": "label", "variable_name": "slot"}, {"column": "status", "variable_name": "status"}]
            db.commit()
            expect_failure(db, qa, "no row matched")

            # 4) Seed real fixture rows and point the filter at them: success,
            # multi-row substitution, no leftover {{placeholders}}.
            db.add(DynamicFixtureRow(category=category, status="disponivel", label="Dr. Fulano - Segunda 10h", ordinal=1))
            db.add(DynamicFixtureRow(category=category, status="disponivel", label="Dr. Beltrano - Terca 14h", ordinal=2))
            db.commit()
            binding = db.get(QADynamicBinding, qa_id)
            assert binding is not None
            binding.filter = {"category": category, "status": "disponivel"}
            db.commit()
            resolution = resolve_dynamic_pattern(db, qa)
            assert "Dr. Fulano - Segunda 10h" in resolution.pattern_text
            assert "Dr. Beltrano - Terca 14h" in resolution.pattern_text
            assert "{{slot}}" not in resolution.pattern_text and "{{status}}" not in resolution.pattern_text

            # 5) Binding references a column absent from the allowlisted model.
            binding = db.get(QADynamicBinding, qa_id)
            assert binding is not None
            binding.output_columns = [{"column": "not_a_real_column", "variable_name": "slot"}]
            db.commit()
            expect_failure(db, qa, "not found in table")

        print("v2_dynamic_pattern_smoke_ok: allowlist enforcement, zero-row fallback, multi-row substitution, missing-column fallback")
    finally:
        with session_factory() as db:
            db.execute(delete(QADynamicBinding).where(QADynamicBinding.qa_id == qa_id))
            db.execute(delete(QAEntry).where(QAEntry.qa_id == qa_id))
            db.execute(delete(DynamicFixtureRow).where(DynamicFixtureRow.category == category))
            db.commit()


if __name__ == "__main__":
    run()
