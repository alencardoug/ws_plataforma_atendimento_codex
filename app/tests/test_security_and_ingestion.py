from pathlib import Path

import pytest

from customer_care.anonymous_access.security import issue_conversation_token, token_digest_matches
from customer_care.auth.security import hash_password, verify_password
from customer_care.knowledge.ingest import parse_parent


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
