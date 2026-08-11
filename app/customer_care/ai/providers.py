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


class GenerationProvider(Protocol):
    name: str
    model: str

    def generate(self, history: list[dict[str, str]], evidence: list[Evidence]) -> GenerationResult: ...


class DeterministicTestGenerationProvider:
    name = "deterministic-test"
    model = "evidence-first-test-v1"

    def generate(self, history: list[dict[str, str]], evidence: list[Evidence]) -> GenerationResult:
        if not evidence:
            return GenerationResult("ABSTAIN", "Não encontrei evidência suficiente; responda manualmente.", "INSUFFICIENT_EVIDENCE", [])
        first = evidence[0]
        return GenerationResult("ANSWER", first.content[:1200], None, [str(first.retrieval_hit_id)])


class OpenAIGenerationProvider:
    name = "openai"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        self.model = settings.ai_generation_model
        self.client = OpenAI(api_key=settings.openai_api_key.get_secret_value())

    def generate(self, history: list[dict[str, str]], evidence: list[Evidence]) -> GenerationResult:
        evidence_payload = [{"retrieval_hit_id": str(item.retrieval_hit_id), "type": item.knowledge_type, "content": item.content} for item in evidence]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Gere somente um rascunho interno ao operador, fundamentado exclusivamente nas evidências. Retorne JSON com status ANSWER ou ABSTAIN, draft_text, reason_code e used_hit_ids. Nunca envie mensagem nem revele raciocínio interno."},
                {"role": "user", "content": json.dumps({"conversation": history, "evidence": evidence_payload}, ensure_ascii=False)},
            ],
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
        usage = response.usage
        return GenerationResult(status, str(payload.get("draft_text", "")), reason, used, usage.prompt_tokens if usage else None, usage.completion_tokens if usage else None)


def configured_generation_provider() -> GenerationProvider:
    return DeterministicTestGenerationProvider() if get_settings().ai_provider == "deterministic-test" else OpenAIGenerationProvider()
