import hashlib
import hmac
import secrets

from customer_care.shared.settings import get_settings


def issue_conversation_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, digest_conversation_token(raw)


def digest_conversation_token(raw: str) -> str:
    pepper = get_settings().anonymous_token_pepper.get_secret_value().encode()
    return hmac.new(pepper, raw.encode(), hashlib.sha256).hexdigest()


def token_digest_matches(raw: str, expected_digest: str) -> bool:
    return hmac.compare_digest(digest_conversation_token(raw), expected_digest)
