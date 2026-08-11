from pathlib import Path
from typing import cast

import pytest
from sqlalchemy.orm import Session

from customer_care.auth import seed_operator
from customer_care.anonymous_access.security import issue_conversation_token, token_digest_matches
from customer_care.auth.seed_operator import provision_operator
from customer_care.auth.security import hash_password, verify_password
from customer_care.infrastructure.models import OperatorUser
from customer_care.knowledge.ingest import parse_parent
from customer_care.shared.settings import Settings


def test_anonymous_token_is_returned_only_as_one_way_digest() -> None:
    raw, digest = issue_conversation_token()

    assert raw != digest
    assert raw not in digest
    assert len(digest) == 64
    assert token_digest_matches(raw, digest)
    assert not token_digest_matches(f"{raw}-wrong", digest)


def test_operator_password_uses_argon2_and_rejects_wrong_candidate() -> None:
    encoded = hash_password("synthetic-password-123")

    assert encoded.startswith("$argon2")
    assert "synthetic-password-123" not in encoded
    assert verify_password(encoded, "synthetic-password-123")
    assert not verify_password(encoded, "wrong-password")


class _FakeTransaction:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: object) -> None:
        return None


class _FakeOperatorSession:
    def __init__(self) -> None:
        self.operator: OperatorUser | None = None

    def __enter__(self) -> "_FakeOperatorSession":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction()

    def scalar(self, _statement: object) -> OperatorUser | None:
        return self.operator

    def add(self, operator: OperatorUser) -> None:
        self.operator = operator


def test_operator_seed_normalizes_and_updates_one_account() -> None:
    fake_session = _FakeOperatorSession()

    def factory() -> Session:
        return cast(Session, fake_session)

    first_email = provision_operator(
        email="  Operator@Example.COM ",
        password="first-synthetic-password",
        display_name="Primeiro nome",
        session_factory=factory,
    )
    first_hash = fake_session.operator.password_hash if fake_session.operator else ""
    second_email = provision_operator(
        email="operator@example.com",
        password="second-synthetic-password",
        display_name="Nome atualizado",
        session_factory=factory,
    )

    assert first_email == second_email == "operator@example.com"
    assert fake_session.operator is not None
    assert fake_session.operator.email == "operator@example.com"
    assert fake_session.operator.display_name == "Nome atualizado"
    assert fake_session.operator.is_active is True
    assert fake_session.operator.password_hash != first_hash
    assert verify_password(fake_session.operator.password_hash, "second-synthetic-password")


def test_login_operator_environment_variables_are_not_runtime_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGIN_OPERATOR_USERNAME", "ignored@example.test")
    monkeypatch.setenv("LOGIN_OPERATOR_PASSWORD", "ignored-synthetic-password")

    settings = Settings(
        _env_file=None,
        anonymous_token_pepper="synthetic-token-pepper-at-least-32-bytes",
        operator_auth_secret="synthetic-auth-secret-at-least-32-bytes",
    )

    assert not hasattr(settings, "login_operator_username")
    assert not hasattr(settings, "login_operator_password")


def test_application_factory_does_not_auto_provision_operator(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_auto_provision(**_kwargs: object) -> str:
        raise AssertionError("application startup must not provision an operator")

    monkeypatch.setattr(seed_operator, "provision_operator", reject_auto_provision)
    monkeypatch.setenv("LOGIN_OPERATOR_USERNAME", "must-not-be-provisioned@example.test")
    monkeypatch.setenv("LOGIN_OPERATOR_PASSWORD", "must-not-be-provisioned")

    from customer_care.bootstrap import create_app

    application = create_app()

    assert application.title == "Customer Care AI V1 API"


def test_clinical_document_rejects_missing_parent_identity(tmp_path: Path) -> None:
    source = tmp_path / "invalid.md"
    source.write_text("---\ndocument_id: OTHER\n---\n\n## A\n\nBody", encoding="utf-8")

    with pytest.raises(ValueError, match="document_id mismatch"):
        parse_parent(source, "EXPECTED")


def test_clinical_document_requires_ten_non_blank_children(tmp_path: Path) -> None:
    source = tmp_path / "invalid.md"
    source.write_text("---\ndocument_id: EXPECTED\n---\n\n## Only one\n\nBody", encoding="utf-8")

    with pytest.raises(ValueError, match="ten non-blank clinical child sections"):
        parse_parent(source, "EXPECTED")
