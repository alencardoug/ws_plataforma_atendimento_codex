from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from customer_care.audit.service import record_event
from customer_care.infrastructure.models import EvaluationCase
from customer_care.shared.dependencies import CurrentOperator, DbSession
from customer_care.shared.errors import api_error

router = APIRouter(prefix="/operator/evaluation", tags=["Operator Evaluation"])


class CreateEvaluationCaseIn(BaseModel):
    category_slug: str | None = None
    question: str
    expected_status: str
    expected_evidence_ids: list[str] | None = None


class UpdateEvaluationCaseIn(BaseModel):
    actual_status: str | None = None
    actual_notes: str | None = None


def case_dict(case: EvaluationCase) -> dict:
    return {
        "id": case.id,
        "category_slug": case.category_slug,
        "question": case.question,
        "expected_status": case.expected_status,
        "expected_evidence_ids": case.expected_evidence_ids,
        "actual_status": case.actual_status,
        "actual_notes": case.actual_notes,
        "last_reviewed_at": case.last_reviewed_at,
        "created_by_operator_id": case.created_by_operator_id,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
    }


@router.get("/cases")
def list_cases(operator: CurrentOperator, session: DbSession, category_slug: str | None = Query(None)) -> list[dict]:
    """Not conversation-scoped by design (plan.md §2) — evaluation cases are
    reference/documentation data, never tied to a live conversation."""
    query = select(EvaluationCase)
    if category_slug:
        query = query.where(EvaluationCase.category_slug == category_slug)
    rows = session.scalars(query.order_by(EvaluationCase.created_at)).all()
    return [case_dict(row) for row in rows]


@router.post("/cases", status_code=201)
def create_case(payload: CreateEvaluationCaseIn, operator: CurrentOperator, session: DbSession) -> dict:
    if payload.expected_status not in {"ANSWER", "ABSTAIN"}:
        raise api_error(422, "INVALID_EXPECTED_STATUS", "expected_status must be ANSWER or ABSTAIN")
    case = EvaluationCase(
        id=uuid4(),
        category_slug=payload.category_slug,
        question=payload.question,
        expected_status=payload.expected_status,
        expected_evidence_ids=payload.expected_evidence_ids,
        created_by_operator_id=operator.id,
    )
    session.add(case)
    session.flush()
    record_event(session, "evaluation.case_created", "OPERATOR", actor_id=operator.id, payload={"case_id": str(case.id)})
    session.commit()
    return case_dict(case)


@router.patch("/cases/{case_id}")
def update_case(case_id: UUID, payload: UpdateEvaluationCaseIn, operator: CurrentOperator, session: DbSession) -> dict:
    """Sets actual_status/actual_notes/last_reviewed_at after a reviewer
    manually re-checks the case against the live system — no automated
    process calls this (spec.md §7, no re-run mechanism in V3)."""
    case = session.get(EvaluationCase, case_id)
    if not case:
        raise api_error(404, "NOT_FOUND", "Evaluation case not found")
    changes = payload.model_dump(exclude_unset=True)
    if "actual_status" in changes:
        if changes["actual_status"] not in {"ANSWER", "ABSTAIN"}:
            raise api_error(422, "INVALID_ACTUAL_STATUS", "actual_status must be ANSWER or ABSTAIN")
        case.actual_status = changes["actual_status"]
    if "actual_notes" in changes:
        case.actual_notes = changes["actual_notes"]
    case.last_reviewed_at = datetime.now(UTC)
    case.updated_at = datetime.now(UTC)
    record_event(session, "evaluation.case_reviewed", "OPERATOR", actor_id=operator.id, payload={"case_id": str(case.id), "actual_status": case.actual_status})
    session.commit()
    return case_dict(case)
