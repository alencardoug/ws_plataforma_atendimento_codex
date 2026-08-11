from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from customer_care.shared.settings import get_settings

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str, candidate: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, candidate)
    except (VerifyMismatchError, InvalidHashError):
        return False


def issue_operator_token(operator_id: UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(operator_id), "role": "operator", "iat": now, "exp": now + timedelta(minutes=settings.operator_auth_ttl_minutes)},
        settings.operator_auth_secret.get_secret_value(),
        algorithm="HS256",
    )


def decode_operator_token(token: str) -> UUID:
    settings = get_settings()
    payload = jwt.decode(token, settings.operator_auth_secret.get_secret_value(), algorithms=["HS256"])
    if payload.get("role") != "operator":
        raise jwt.InvalidTokenError("wrong role")
    return UUID(payload["sub"])
