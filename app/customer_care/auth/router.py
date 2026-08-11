from fastapi import APIRouter, Request
from sqlalchemy import func, select

from customer_care.audit.service import record_event
from customer_care.auth.security import issue_operator_token, verify_password
from customer_care.infrastructure.models import OperatorUser
from customer_care.shared.dependencies import CurrentOperator, DbSession
from customer_care.shared.errors import api_error
from customer_care.shared.schemas import OperatorLoginIn, OperatorLoginOut, OperatorOut

router = APIRouter(tags=["Operator Auth"])


@router.post("/auth/operator/login", response_model=OperatorLoginOut)
def login(payload: OperatorLoginIn, session: DbSession, request: Request) -> dict:
    email = str(payload.email).strip().lower()
    operator = session.scalar(select(OperatorUser).where(func.lower(OperatorUser.email) == email))
    if not operator or not operator.is_active or not verify_password(operator.password_hash, payload.password):
        record_event(session, "auth.login_failed", "SYSTEM", correlation_id=request.state.request_id)
        session.commit()
        raise api_error(401, "INVALID_CREDENTIALS", "Invalid credentials")
    record_event(session, "auth.login_succeeded", "OPERATOR", actor_id=operator.id, correlation_id=request.state.request_id)
    session.commit()
    return {"access_token": issue_operator_token(operator.id), "operator": operator}


@router.get("/operator/me", response_model=OperatorOut)
def me(operator: CurrentOperator) -> OperatorUser:
    return operator
