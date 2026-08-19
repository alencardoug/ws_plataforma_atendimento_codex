"""AA-9's one write-triggering endpoint. Not conversation/assignment-scoped
— any authenticated operator may call it (plan.md §4b/§9)."""

from fastapi import APIRouter, Request

from customer_care.audit.service import record_event
from customer_care.scheduling.seeding import ensure_seed_availability
from customer_care.shared.dependencies import CurrentOperator, DbSession

router = APIRouter(prefix="/operator/scheduling", tags=["Operator Scheduling"])


@router.post("/ensure-availability", status_code=200)
def ensure_availability(operator: CurrentOperator, session: DbSession, request: Request) -> dict:
    result = ensure_seed_availability(session)
    record_event(
        session,
        "scheduling.availability_seeded",
        "OPERATOR",
        actor_id=operator.id,
        correlation_id=request.state.request_id,
        payload={"created_d1": result.created_d1, "created_d7": result.created_d7, "already_sufficient": result.already_sufficient},
    )
    session.commit()
    if result.already_sufficient:
        message = "Já tem 4 vagas disponíveis."
    else:
        message = f"Criadas {result.created_d1 + result.created_d7} vaga(s): {result.created_d1} em D+1, {result.created_d7} em D+7."
    return {
        "created_d1": result.created_d1,
        "created_d7": result.created_d7,
        "already_sufficient": result.already_sufficient,
        "message": message,
    }
