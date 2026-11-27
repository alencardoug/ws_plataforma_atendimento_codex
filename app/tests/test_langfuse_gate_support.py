"""Destructive acceptance helpers must never reach the everyday database."""

from types import SimpleNamespace

import pytest

import langfuse_gate_support as gates
import langfuse_pytest_fixtures as fixtures


@pytest.mark.parametrize("host,database", [("db", "oncology"), ("remote.invalid", "oncology_langfuse_test"), ("localhost", "postgres")])
def test_reset_refuses_unapproved_database_before_connecting(monkeypatch, host, database):
    def forbidden():
        raise AssertionError("must reject before executing SQL")

    monkeypatch.setattr(gates, "get_engine", lambda: SimpleNamespace(url=SimpleNamespace(host=host, database=database), connect=forbidden, begin=forbidden))
    with pytest.raises(RuntimeError, match="isolated local"):
        gates.reset(content=True)


@pytest.mark.parametrize("name,expected", [("tests.test_booking_offer_draft", 1), ("test_availability_continuity", 1), ("tests.test_appointment_seeding", 0)])
def test_legacy_agenda_setup_matches_packaged_and_unqualified_module_names(monkeypatch, name, expected):
    calls = []
    monkeypatch.setattr(fixtures, "seed_agenda", lambda: calls.append(1))
    fixtures.legacy_agenda_fixture.__wrapped__(SimpleNamespace(module=SimpleNamespace(__name__=name)))
    assert len(calls) == expected
