import json
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI

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


class GenerationProvider(Protocol):
    name: str
    model: str

    def generate(self, history: list[dict[str, str]], evidence: list[Evidence], system_prompt: str) -> GenerationResult: ...


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


def configured_generation_provider() -> GenerationProvider:
    return DeterministicTestGenerationProvider() if get_settings().ai_provider == "deterministic-test" else OpenAIGenerationProvider()
