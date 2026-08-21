import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from openai import OpenAI

from customer_care.ai.prompts import load_prompt
from customer_care.rag.service import Evidence
from customer_care.shared.settings import get_settings


@dataclass(frozen=True)
class GenerationResult:
    status: str
    draft_text: str
    reason_code: str | None
    used_hit_ids: list[str]
    input_tokens: int | None = None
    output_tokens: int | None = None
    request_messages: list[dict[str, str]] | None = None


@dataclass(frozen=True)
class StructuredDateIntent:
    """006/ND-1: the LLM classifies only these fields from a customer's
    free-text date/time expression — it never computes, states, or
    outputs a date or weekday name itself. Every field is independently
    optional; `scheduling/availability.py`'s deterministic arithmetic
    (`_resolve_date_intent`) is the only code that turns this into an
    actual `date`."""

    relative_unit: str | None  # "day" | "week" | "month"
    relative_count: int | None
    weekday: int | None  # 0=Monday..6=Sunday
    nth_weekday_of_month: int | None  # 1-5
    month: int | None  # 1-12
    day: int | None  # explicit day-of-month
    time_range_start: int | None  # hour, 0-23
    time_range_end: int | None  # hour, 0-23 (exclusive)


class GenerationProvider(Protocol):
    name: str
    model: str

    def generate(self, history: list[dict[str, str]], evidence: list[Evidence], system_prompt: str) -> GenerationResult: ...
    def rerank_clinical(self, customer_text: str, candidate_text: str) -> bool: ...
    def extract_date_intent(self, customer_text: str, reference_date: date) -> StructuredDateIntent | None: ...
    def generate_ungoverned(self, history: list[dict[str, str]], system_prompt: str) -> str: ...


CLINICAL_DEFLECTION_TEXT = "Essa é uma pergunta de natureza clínica — recomendo conversar sobre isso com o profissional de saúde responsável durante a consulta. Posso ajudar com outra dúvida?"

# 011 (Constitution Amendment 1.3.0, N5): deliberately its own small
# prompt, not rag_answer.md — that file's contract is built entirely
# around evidence grounding and an ABSTAIN option, both of which N5
# explicitly has neither of. Reusing it verbatim would instruct the model
# to abstain and to only claim evidence-backed facts, directly
# contradicting generate_ungoverned's own purpose (plan.md §2 is corrected
# by this comment — see analysis.md for this implementation-time
# refinement). Keeps the same warm, concise, Brazilian Portuguese
# customer-service voice; explicitly forbids revealing that this is an AI/
# a demo (the frontend disclaimer banner already discloses that) and
# forbids inventing hyper-specific identifying details (doctor names,
# exact prices) it has no basis for, while still always answering.
UNGOVERNED_N5_SYSTEM_PROMPT = (
    "Você é um atendente cordial de uma clínica oncológica fictícia, "
    "respondendo em português brasileiro, de forma breve e natural (uma a "
    "três frases, salvo necessidade real de mais).\n\n"
    "Sempre dê ao cliente uma resposta útil e no personagem — nunca recuse, "
    "nunca diga que falta informação, nunca abstenha-se. Se não tiver um "
    "fato específico (nome de profissional, preço exato, horário exato), "
    "responda de forma geral e ofereça encaminhar a dúvida, em vez de "
    "inventar um dado específico como se fosse real.\n\n"
    "Nunca revele que você é uma IA, um modelo de linguagem, ou que esta é "
    "uma simulação/demonstração — mantenha o personagem do atendente. Nunca "
    "inclua explicações de processo, instruções para um operador, "
    "citações, ou qualquer texto além da resposta que seria enviada "
    "diretamente ao cliente."
)
# Article V (traceability): a real, content-derived version marker, same
# technique load_prompt() uses for the file-backed evidence-gated prompt —
# this one is source-controlled as a Python constant instead of a file, but
# still deserves a version that changes if the text ever does.
UNGOVERNED_N5_PROMPT_VERSION = f"ungoverned_n5_prompt:{hashlib.sha256(UNGOVERNED_N5_SYSTEM_PROMPT.encode()).hexdigest()[:12]}"

_RERANK_SYSTEM_PROMPT_TEMPLATE = (
    "Você compara duas respostas candidatas para a mensagem mais recente de um "
    "cliente de um serviço de atendimento oncológico e escolhe qual é mais "
    "apropriada.\n\n"
    "CANDIDATA A: {candidate_text}\n\n"
    "CANDIDATA B: {deflection_text}\n\n"
    "Prefira sempre a CANDIDATA A quando ela responder de forma adequada à "
    "mensagem do cliente, mesmo que de forma simples ou genérica. Só prefira "
    "a CANDIDATA B quando a mensagem do cliente for claramente uma pergunta "
    "de natureza clínica ou de saúde (sintomas, diagnóstico, prognóstico, "
    "tratamento, prazos de exames, efeitos colaterais, etc.) que a CANDIDATA "
    "A claramente não responde.\n\n"
    'Retorne um objeto JSON válido com exatamente um campo: {{"chosen": "A"}} ou {{"chosen": "B"}}.'
)


FORMAT_INSTRUCTION = "Retorne um objeto JSON válido com exatamente estes campos: status (ANSWER ou ABSTAIN), draft_text, reason_code e used_hit_ids. Para ANSWER, draft_text deve conter somente a resposta final, curta e natural para o cliente. Não inclua explicações do processo, instruções ao operador, citações, metadados ou trechos de evidência. Nunca envie mensagem nem revele raciocínio interno."


def build_request_messages(history: list[dict[str, str]], evidence: list[Evidence], system_prompt: str) -> list[dict[str, str]]:
    """The exact `messages` array sent to (or, for the deterministic test
    provider, that would be sent to) the generation model — kept as one
    shared builder so the operator-facing debug view (operator-only,
    revealed via an explicit button/pop-up, never customer-facing) always
    matches what OpenAIGenerationProvider.generate actually transmits."""
    evidence_payload = [{"retrieval_hit_id": str(item.retrieval_hit_id), "type": item.knowledge_type, "content": item.content} for item in evidence]
    return [
        {"role": "system", "content": f"{system_prompt}\n\n{FORMAT_INSTRUCTION}"},
        {"role": "user", "content": json.dumps({"conversation": history, "evidence": evidence_payload}, ensure_ascii=False)},
    ]


class DeterministicTestGenerationProvider:
    name = "deterministic-test"
    model = "evidence-first-test-v1"

    def generate(self, history: list[dict[str, str]], evidence: list[Evidence], system_prompt: str) -> GenerationResult:
        request_messages = build_request_messages(history, evidence, system_prompt)
        latest_customer_message = next((item["content"] for item in reversed(history) if item["role"] == "customer"), "")
        if latest_customer_message.strip().casefold() in {"oi", "olá", "ola", "oi!", "olá!", "ola!"}:
            return GenerationResult("ANSWER", "Oi, tudo bem? Como posso ajudar?", None, [str(evidence[0].retrieval_hit_id)] if evidence else [], request_messages=request_messages)
        if not evidence:
            return GenerationResult("ANSWER", "Posso ajudar. Pode me contar um pouco mais sobre o que você precisa?", None, [], request_messages=request_messages)
        first = evidence[0]
        return GenerationResult("ANSWER", "Posso ajudar com sua dúvida. Pode me contar um pouco mais sobre o que precisa?", None, [str(first.retrieval_hit_id)], request_messages=request_messages)

    def rerank_clinical(self, customer_text: str, candidate_text: str) -> bool:
        # Deterministic test provider has no real semantic judgment — always
        # keeps the RAG/dynamic candidate, matching its own conservative
        # stand-in behavior elsewhere. Genuine reranking quality is smoke-
        # tested against the real provider only (same split this codebase
        # already uses for every other embedding/LLM-judgment feature).
        return False

    def extract_date_intent(self, customer_text: str, reference_date: date) -> StructuredDateIntent | None:
        # 006/ND: same conservative stand-in precedent as rerank_clinical
        # above — no real semantic judgment, always "found nothing", so
        # extract_parameters()'s LLM fallback is inert under the
        # deterministic-test provider and every existing pure test keeps
        # its exact current behavior. Genuine extraction quality is
        # smoke-tested against the real provider only.
        return None

    def generate_ungoverned(self, history: list[dict[str, str]], system_prompt: str) -> str:
        # 011: fixed deterministic text, same stand-in precedent as the
        # methods above — real-quality ungoverned output is smoke-tested
        # against the real provider only.
        return "Posso ajudar com isso — pode me contar um pouco mais sobre o que você precisa?"


class OpenAIGenerationProvider:
    name = "openai"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        self.model = settings.ai_generation_model
        self.client = OpenAI(api_key=settings.openai_api_key.get_secret_value())

    def generate(self, history: list[dict[str, str]], evidence: list[Evidence], system_prompt: str) -> GenerationResult:
        request_messages = build_request_messages(history, evidence, system_prompt)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=request_messages,  # type: ignore[call-overload]
            response_format={"type": "json_object"},
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        status = payload.get("status")
        if status not in {"ANSWER", "ABSTAIN"}:
            raise ValueError("provider returned invalid status")
        reason = payload.get("reason_code")
        allowed_reasons = {"INSUFFICIENT_EVIDENCE", "CONFLICTING_EVIDENCE", "OUT_OF_SCOPE", "RETRIEVAL_FAILURE"}
        if status == "ABSTAIN" and reason not in allowed_reasons:
            reason = "INSUFFICIENT_EVIDENCE"
        if status == "ANSWER":
            reason = None
        allowed_ids = {str(item.retrieval_hit_id) for item in evidence}
        used = [value for value in payload.get("used_hit_ids", []) if value in allowed_ids]
        draft_text = str(payload.get("draft_text", "")).strip()
        if status == "ANSWER" and not draft_text:
            raise ValueError("provider returned empty answer draft")
        usage = response.usage
        return GenerationResult(status, draft_text, reason, used, usage.prompt_tokens if usage else None, usage.completion_tokens if usage else None, request_messages=request_messages)

    def rerank_clinical(self, customer_text: str, candidate_text: str) -> bool:
        """Human decision, 2026-08-19: a clinical-deflection candidate
        participates as one more option, reranked against whatever answer
        the normal pipeline produced — the RAG/dynamic candidate wins
        whenever it's adequate; the deflection wins only when the message
        is a genuinely uncovered clinical question. Real LLM judgment call
        (open-ended clinical-topic detection, not a closed candidate set —
        unlike GB-2's ordinal/embedding matching, this is not something a
        deterministic parser can reliably do)."""
        system_prompt = _RERANK_SYSTEM_PROMPT_TEMPLATE.format(candidate_text=candidate_text, deflection_text=CLINICAL_DEFLECTION_TEXT)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": customer_text}],
            response_format={"type": "json_object"},
        )
        payload = json.loads(response.choices[0].message.content or "{}")
        return payload.get("chosen") == "B"

    def generate_ungoverned(self, history: list[dict[str, str]], system_prompt: str) -> str:
        """011 (Constitution Amendment 1.3.0, N5): a plain chat completion —
        no evidence payload, no JSON response_format, no ABSTAIN option.
        The model always returns free text, which the caller sends to the
        customer as-is (plan.md §2)."""
        messages = [{"role": "system", "content": system_prompt}, *[{"role": "user" if item["role"] == "customer" else "assistant", "content": item["content"]} for item in history]]
        response = self.client.chat.completions.create(model=self.model, messages=messages)  # type: ignore[arg-type]
        text = (response.choices[0].message.content or "").strip()
        return text or "Posso ajudar com isso — pode me contar um pouco mais sobre o que você precisa?"

    def extract_date_intent(self, customer_text: str, reference_date: date) -> StructuredDateIntent | None:
        """006/ND-1: classifies only the 8 structured fields — never
        computes or states a date itself (the prompt states this as a
        hard constraint). Defensive parsing: any missing/invalid field
        defaults to `None` rather than raising, matching this provider's
        general style (`rerank_clinical`'s own `.get("chosen") == "B"`
        never raises on a malformed response either). Returns `None` only
        on a hard parse failure — a well-formed response with every field
        `None` is a valid, distinct result, still returned (ND-1's own
        `plan.md` §5.1 rationale: keeps "provider failed" and "provider
        understood nothing" distinguishable for a future caller, even
        though both fall through identically today)."""
        prompt = load_prompt("date_intent.md")
        user_content = json.dumps({"customer_text": customer_text, "reference_date": reference_date.isoformat()}, ensure_ascii=False)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": prompt.content}, {"role": "user", "content": user_content}],
                response_format={"type": "json_object"},
            )
            payload = json.loads(response.choices[0].message.content or "{}")
        except (json.JSONDecodeError, OSError):
            return None

        def _int_or_none(value: object) -> int | None:
            return value if isinstance(value, int) else None

        def _str_or_none(value: object) -> str | None:
            return value if isinstance(value, str) else None

        return StructuredDateIntent(
            relative_unit=_str_or_none(payload.get("relative_unit")),
            relative_count=_int_or_none(payload.get("relative_count")),
            weekday=_int_or_none(payload.get("weekday")),
            nth_weekday_of_month=_int_or_none(payload.get("nth_weekday_of_month")),
            month=_int_or_none(payload.get("month")),
            day=_int_or_none(payload.get("day")),
            time_range_start=_int_or_none(payload.get("time_range_start")),
            time_range_end=_int_or_none(payload.get("time_range_end")),
        )


def configured_generation_provider() -> GenerationProvider:
    return DeterministicTestGenerationProvider() if get_settings().ai_provider == "deterministic-test" else OpenAIGenerationProvider()
