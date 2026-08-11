import argparse

from sqlalchemy import func, select

from customer_care.auth.security import hash_password
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import OperatorUser


def main() -> None:
    parser = argparse.ArgumentParser(description="Create/update a synthetic V1 operator")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--display-name", default="Operador Demo")
    args = parser.parse_args()
    if len(args.password) < 12:
        parser.error("password must contain at least 12 characters")
    email = args.email.strip().lower()
    with get_session_factory()() as session, session.begin():
        operator = session.scalar(select(OperatorUser).where(func.lower(OperatorUser.email) == email))
        if operator:
            operator.password_hash = hash_password(args.password)
            operator.display_name = args.display_name
            operator.is_active = True
        else:
            session.add(OperatorUser(email=email, password_hash=hash_password(args.password), display_name=args.display_name))
    print(f"Seeded synthetic operator {email}")


if __name__ == "__main__":
    main()
