import hashlib
import hmac
import secrets

from customer_care.shared.settings import get_settings

# Uppercase letters and digits, excluding visually ambiguous characters
# (0/O, 1/I, L) — plan.md §3.1. 31 symbols, 8 characters: ~4.9e11 combinations.
TOKEN_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
TOKEN_LENGTH = 8


def issue_conversation_token() -> tuple[str, str]:
    raw = "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(TOKEN_LENGTH))
    return raw, digest_conversation_token(raw)


def digest_conversation_token(raw: str) -> str:
    pepper = get_settings().anonymous_token_pepper.get_secret_value().encode()
    return hmac.new(pepper, raw.encode(), hashlib.sha256).hexdigest()


def token_digest_matches(raw: str, expected_digest: str) -> bool:
    return hmac.compare_digest(digest_conversation_token(raw), expected_digest)
