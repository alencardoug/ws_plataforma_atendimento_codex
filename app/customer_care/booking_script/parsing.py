"""Pure functions, no database, no I/O. plan.md §8b "Module"."""

import re

from pydantic import BaseModel, ValidationError, field_validator

_NON_DIGIT = re.compile(r"\D")
_AFFIRMATIVE = re.compile(r"\bsim+\b", re.IGNORECASE)
_NEGATIVE = re.compile(r"\bn[ãa]o\b", re.IGNORECASE)

# A separate, smaller vocabulary from scheduling/availability.py's
# SPECIALTY_KEYWORDS — a different question ("does this customer want to
# book?" vs. "which specialty?"), deliberately not reused from it.
BOOKING_INTENT_KEYWORDS: tuple[str, ...] = (
    "quero marcar",
    "quero agendar",
    "pode agendar",
    "pode marcar",
    "vou querer esse horário",
    "vou querer esse horario",
    "confirma esse horário",
    "confirma esse horario",
    "quero essa consulta",
    "quero essa vaga",
)


class _CPFInput(BaseModel):
    digits: str

    @field_validator("digits")
    @classmethod
    def must_be_eleven_digits(cls, value: str) -> str:
        stripped = _NON_DIGIT.sub("", value)
        if len(stripped) != 11:
            raise ValueError("must have exactly 11 digits after stripping non-digit characters")
        return stripped


def extract_cpf(text: str) -> str | None:
    """Digit-count-only validation — strips every non-digit character,
    requires exactly 11 digits remain. **Never the real Brazilian CPF
    check-digit algorithm** — any 11-digit sequence passes, matching the
    human's explicit "é uma simulação" instruction. Returns `None` on
    failure (caught here, never raised past this function — the caller
    decides what to do with "invalid"). Formats as `###.###.###-##` on
    success."""
    try:
        validated = _CPFInput(digits=text)
    except ValidationError:
        return None
    digits = validated.digits
    return f"{digits[0:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:11]}"


def extract_payment_confirmation(text: str) -> bool | None:
    """Case-insensitive, word-boundary-aware. `True` only on an
    affirmative-only match ("sim", "Sim", "SIM", "simm", ... — works
    embedded in a full sentence like "tabom simm paguei"). `False` on a
    negative-only match ("não", "nao", "Não", ...). `None` on no match or
    an ambiguous message matching both — the caller treats `False` and
    `None` identically (re-ask), this distinction exists only so a caller
    that cares can tell "explicitly no" from "didn't understand"."""
    affirmative = _AFFIRMATIVE.search(text) is not None
    negative = _NEGATIVE.search(text) is not None
    if affirmative and not negative:
        return True
    if negative and not affirmative:
        return False
    return None


def detect_booking_intent(text: str) -> bool:
    """Deterministic keyword-substring detection — only considered by the
    caller while no script is already in progress for that conversation."""
    lowered = text.lower()
    return any(keyword in lowered for keyword in BOOKING_INTENT_KEYWORDS)
