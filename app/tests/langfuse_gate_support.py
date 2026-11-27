"""Administrative helpers for LF-5. Refuse every non-isolated database."""

import argparse
import importlib
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select, text

from customer_care.auth.seed_operator import provision_operator
from customer_care.infrastructure import telemetry
from customer_care.infrastructure.database import get_engine, get_session_factory

TEST_DATABASE = "oncology_langfuse_test"


def require_isolated_database() -> None:
    engine = get_engine()
    if engine.url.database != TEST_DATABASE or engine.url.host not in {"db", "127.0.0.1", "localhost"}:
        raise RuntimeError("Validation requires the isolated local database")
    with engine.connect() as connection:
        if connection.scalar(text("SELECT current_database()")) != TEST_DATABASE:
            raise RuntimeError("Connected database differs from the isolated target")


def reset(*, content: bool = False, agenda: bool = True) -> None:
    require_isolated_database()
    with get_engine().begin() as connection:
        names = connection.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='customer_service' AND tablename NOT IN ('operator_users','system_settings') ORDER BY tablename")).all()
        preparer = connection.dialect.identifier_preparer
        connection.execute(text("TRUNCATE " + ", ".join("customer_service." + preparer.quote(name) for name in names) + " CASCADE"))
        connection.execute(text("UPDATE customer_service.system_settings SET n5_kill_switch_enabled=false, autonomy_kill_switch_enabled=false, autonomy_window_seconds=30, automatic_trigger_idle_seconds=8, availability_floor_checked_at=NULL"))
        if agenda:
            connection.execute(text("TRUNCATE scheduling.schedule_slots CASCADE"))
        if content:
            names = connection.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='content' ORDER BY tablename")).all()
            preparer = connection.dialect.identifier_preparer
            connection.execute(text("TRUNCATE " + ", ".join("content." + preparer.quote(name) for name in names) + " CASCADE"))
        else:
            connection.execute(text("UPDATE content.categories SET autonomy_enabled=false"))


def seed_operator() -> None:
    require_isolated_database()
    provision_operator(email=os.environ["SMOKE_OPERATOR_EMAIL"], password=os.environ["SMOKE_OPERATOR_PASSWORD"], display_name="Validação LF-5")


def seed_agenda() -> None:
    """Minimal explicit fixture required by the legacy integration tests."""
    from customer_care.scheduling.models import Specialty
    from customer_care.scheduling.seeding import create_slots_on, next_business_day_sql

    require_isolated_database()
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    with get_session_factory()() as session:
        for specialty_id in session.scalars(select(Specialty.specialty_id)):
            for offset in (1, 7):
                create_slots_on(session, next_business_day_sql(session, today + timedelta(days=offset)), 4, specialty_id)
        session.commit()


def smoke(name: str) -> None:
    require_isolated_database()
    if not name.startswith("smoke_") or "/" in name or not (Path("tests") / f"{name}.py").is_file():
        raise ValueError("Unknown local smoke module")
    # Most legacy smoke scripts use TestClient without its lifespan. Give
    # each standalone process the same explicit telemetry lifecycle as API.
    telemetry.initialize()
    try:
        importlib.import_module(name).run()
    finally:
        telemetry.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["check", "reset", "reset-content", "seed-operator", "seed-agenda", "smoke"])
    parser.add_argument("name", nargs="?")
    args = parser.parse_args()
    if args.action == "check":
        require_isolated_database()
    elif args.action.startswith("reset"):
        reset(content=args.action == "reset-content")
    elif args.action == "seed-operator":
        seed_operator()
    elif args.action == "seed-agenda":
        seed_agenda()
    elif args.action == "smoke":
        smoke(args.name or "")
