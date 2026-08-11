import argparse
from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from customer_care.auth.security import hash_password
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import OperatorUser


def provision_operator(
    *,
    email: str,
    password: str,
    display_name: str = "Operador Demo",
    session_factory: Callable[[], Session] | None = None,
) -> str:
    """Explicitly create or update one synthetic operator by normalized email."""
    if len(password) < 12:
        raise ValueError("password must contain at least 12 characters")
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise ValueError("email must not be blank")

    factory = session_factory or get_session_factory()
    with factory() as session, session.begin():
        operator = session.scalar(select(OperatorUser).where(func.lower(OperatorUser.email) == normalized_email))
        if operator:
            operator.password_hash = hash_password(password)
            operator.display_name = display_name
            operator.is_active = True
        else:
            session.add(OperatorUser(email=normalized_email, password_hash=hash_password(password), display_name=display_name))
    return normalized_email


def main() -> None:
    parser = argparse.ArgumentParser(description="Create/update a synthetic V1 operator")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--display-name", default="Operador Demo")
    args = parser.parse_args()
    try:
        email = provision_operator(email=args.email, password=args.password, display_name=args.display_name)
    except ValueError as exc:
        parser.error(str(exc))
    print(f"Seeded synthetic operator {email}")


if __name__ == "__main__":
    main()
