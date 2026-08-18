from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from customer_care.ai.router import derive_category_slug
from customer_care.infrastructure.models import KnowledgeDocument, QAEntry, RetrievalHit


class _FakeSession:
    """Stands in for a real DbSession: derive_category_slug makes at most one
    `.scalar()` call (the use_order=1 AIGenerationSource lookup) and up to
    two `.get()` calls (RetrievalHit, then QAEntry or KnowledgeDocument).
    Real relational queries are exercised end-to-end via smoke_n2.py against
    a live database instead — this test isolates the derivation logic
    itself, matching test_security_and_ingestion.py's _FakeOperatorSession
    pattern rather than standing up a real DB session for a pure unit test."""

    def __init__(self, source: object | None = None, hit: object | None = None, qa: object | None = None, document: object | None = None) -> None:
        self._source = source
        self._hit = hit
        self._qa = qa
        self._document = document

    def scalar(self, _statement: object) -> object | None:
        return self._source

    def get(self, model: type, _pk: object) -> object | None:
        if model is RetrievalHit:
            return self._hit
        if model is QAEntry:
            return self._qa
        if model is KnowledgeDocument:
            return self._document
        return None


def _generation(status: str) -> Any:
    return SimpleNamespace(id=uuid4(), status=status)


def test_qa_grounded_answer_derives_category_from_qa_entry() -> None:
    hit = SimpleNamespace(matched_qa_id="qa-001", expanded_parent_document_id=None)
    source = SimpleNamespace(retrieval_hit_id=uuid4())
    qa = SimpleNamespace(category="preco")
    session = _FakeSession(source=source, hit=hit, qa=qa)

    assert derive_category_slug(session, _generation("ANSWER")) == "preco"  # type: ignore[arg-type]


def test_clinical_parent_grounded_answer_derives_category_from_document_cancer_type() -> None:
    hit = SimpleNamespace(matched_qa_id=None, expanded_parent_document_id="doc-001")
    source = SimpleNamespace(retrieval_hit_id=uuid4())
    document = SimpleNamespace(cancer_type="mama")
    session = _FakeSession(source=source, hit=hit, document=document)

    assert derive_category_slug(session, _generation("ANSWER")) == "mama"  # type: ignore[arg-type]


def test_abstain_never_derives_a_category() -> None:
    session = _FakeSession(source=SimpleNamespace(retrieval_hit_id=uuid4()), hit=SimpleNamespace(matched_qa_id="qa-001", expanded_parent_document_id=None), qa=SimpleNamespace(category="preco"))

    assert derive_category_slug(session, _generation("ABSTAIN")) is None  # type: ignore[arg-type]


def test_evidence_free_answer_derives_no_category() -> None:
    session = _FakeSession(source=None)

    assert derive_category_slug(session, _generation("ANSWER")) is None  # type: ignore[arg-type]
