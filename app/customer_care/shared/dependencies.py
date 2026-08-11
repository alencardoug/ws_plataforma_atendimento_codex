from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from customer_care.auth.security import decode_operator_token
from customer_care.infrastructure.database import session_scope
from customer_care.infrastructure.models import OperatorUser
from customer_care.shared.errors import api_error

operator_bearer = HTTPBearer(auto_error=False, scheme_name="operatorBearer")
customer_bearer = HTTPBearer(auto_error=False, scheme_name="customerConversationToken")
DbSession = Annotated[Session, Depends(session_scope)]


def current_operator(
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(operator_bearer)],
) -> OperatorUser:
    if not credentials:
        raise api_error(401, "UNAUTHORIZED", "Operator authentication required")
    try:
        operator_id: UUID = decode_operator_token(credentials.credentials)
    except (jwt.InvalidTokenError, ValueError):
        raise api_error(401, "UNAUTHORIZED", "Invalid operator credential") from None
    operator = session.get(OperatorUser, operator_id)
    if not operator or not operator.is_active:
        raise api_error(401, "UNAUTHORIZED", "Invalid operator credential")
    return operator


CurrentOperator = Annotated[OperatorUser, Depends(current_operator)]
