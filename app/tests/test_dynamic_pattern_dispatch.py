"""T052: regression proof for the NAMED_RESOLVERS dispatch added to
ai/router.py's dynamic_pattern_result() (plan.md §2). A QA entry whose
dynamic_resolver names something still unimplemented
(payment_simulator/insurance_lookup — price_lookup itself was added by
005/PL, specs/005-dynamic-pricing-and-guided-booking/) must abstain
exactly as it did before this feature — no accidental widening of what
resolves (acceptance outcome 8). A QA entry using the pre-existing generic
qa_dynamic_bindings mechanism (dynamic_resolver=NULL) must still resolve
exactly as before — proves the dispatch change is additive, not a
replacement. Real-database integration tests, mirroring
tests/smoke_n2.py's own RetrievalRun/RetrievalHit construction pattern."""

from uuid import uuid4

import pytest
from sqlalchemy import delete

from customer_care.ai.router import dynamic_pattern_result
from customer_care.auth.security import hash_password
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import DynamicFixtureRow, OperatorUser, QADynamicBinding, QAEntry, RetrievalHit, RetrievalRun
from customer_care.rag.service import Evidence


@pytest.fixture
def operator_id():
    session_factory = get_session_factory()
    email = f"t052-{uuid4().hex[:8]}@example.com"
    with session_factory() as db:
        operator = OperatorUser(email=email, password_hash=hash_password("irrelevant"), display_name="T052 fixture")
        db.add(operator)
        db.commit()
        oid = operator.id
    yield oid
    with session_factory() as db:
        db.execute(delete(OperatorUser).where(OperatorUser.id == oid))
        db.commit()


def _evidence_for(qa: QAEntry, retrieval_hit_id) -> Evidence:
    return Evidence(
        retrieval_hit_id=retrieval_hit_id,
        knowledge_type="ADMIN_QA",
        rank=1,
        score=1.0,
        title=qa.question,
        section=None,
        content=qa.answer_markdown,
        matched_child_excerpt=None,
        customer_citation_allowed=qa.customer_citation_allowed,
    )


def test_unimplemented_resolver_name_still_abstains(operator_id) -> None:
    session_factory = get_session_factory()
    qa_id = f"t052-insurance-{uuid4().hex[:8]}"
    with session_factory() as db:
        qa = QAEntry(qa_id=qa_id, category="smoke-fixture", question="Meu convênio cobre?", answer_markdown="Cobertura: {{coverage}}", dynamic_data_required=True, dynamic_resolver="insurance_lookup", customer_citation_allowed=False)
        db.add(qa)
        run = RetrievalRun(operator_id=operator_id, purpose="N2_MANUAL_SEARCH", query_text="t052", embedding_model="smoke", top_k=1, status="COMPLETED")
        db.add(run)
        db.flush()
        hit = RetrievalHit(retrieval_run_id=run.id, matched_kind="ADMIN_QA", matched_qa_id=qa_id, rank=1, score=1.0)
        db.add(hit)
        db.commit()
        hit_id = hit.id

    try:
        with session_factory() as db:
            qa = db.get(QAEntry, qa_id)
            outcome = dynamic_pattern_result(db, [_evidence_for(qa, hit_id)], "qualquer pergunta")

        assert outcome is not None
        result, dynamic_used, dynamic_cause, audit_extra, offered_rows = outcome
        assert result.status == "ABSTAIN"
        assert result.reason_code == "DYNAMIC_DATA_UNAVAILABLE"
        assert result.draft_text == ""
        assert dynamic_used is False
        assert dynamic_cause is not None
        assert audit_extra is None
    finally:
        with session_factory() as db:
            db.execute(delete(RetrievalHit).where(RetrievalHit.id == hit_id))
            db.execute(delete(RetrievalRun).where(RetrievalRun.operator_id == operator_id))
            db.execute(delete(QAEntry).where(QAEntry.qa_id == qa_id))
            db.commit()


def test_generic_qa_dynamic_bindings_path_still_resolves_unaffected(operator_id) -> None:
    session_factory = get_session_factory()
    qa_id = f"t052-generic-{uuid4().hex[:8]}"
    category = f"t052-{uuid4().hex[:8]}"
    with session_factory() as db:
        qa = QAEntry(qa_id=qa_id, category="smoke-fixture", question="Pergunta genérica", answer_markdown="Vaga: {{slot}}", dynamic_data_required=True, dynamic_resolver=None, customer_citation_allowed=False)
        db.add(qa)
        db.flush()
        db.add(DynamicFixtureRow(category=category, status="disponivel", ordinal=1, label="vaga-livre"))
        db.add(QADynamicBinding(qa_id=qa_id, source_table="knowledge_dynamic_fixture", filter={"category": category}, output_columns=[{"column": "label", "variable_name": "slot"}], row_limit=4))
        run = RetrievalRun(operator_id=operator_id, purpose="N2_MANUAL_SEARCH", query_text="t052", embedding_model="smoke", top_k=1, status="COMPLETED")
        db.add(run)
        db.flush()
        hit = RetrievalHit(retrieval_run_id=run.id, matched_kind="ADMIN_QA", matched_qa_id=qa_id, rank=1, score=1.0)
        db.add(hit)
        db.commit()
        hit_id = hit.id

    try:
        with session_factory() as db:
            qa = db.get(QAEntry, qa_id)
            outcome = dynamic_pattern_result(db, [_evidence_for(qa, hit_id)], "qualquer pergunta")

        assert outcome is not None
        result, dynamic_used, dynamic_cause, audit_extra, offered_rows = outcome
        assert result.status == "ANSWER"
        assert "vaga-livre" in result.draft_text
        assert dynamic_used is True
        assert dynamic_cause is None
        assert audit_extra is None  # only appointment_availability populates specialty_slug/slot_count
    finally:
        with session_factory() as db:
            db.execute(delete(RetrievalHit).where(RetrievalHit.id == hit_id))
            db.execute(delete(RetrievalRun).where(RetrievalRun.operator_id == operator_id))
            db.execute(delete(QADynamicBinding).where(QADynamicBinding.qa_id == qa_id))
            db.execute(delete(QAEntry).where(QAEntry.qa_id == qa_id))
            db.execute(delete(DynamicFixtureRow).where(DynamicFixtureRow.category == category))
            db.commit()
