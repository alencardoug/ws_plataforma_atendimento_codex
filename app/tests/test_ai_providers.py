from types import SimpleNamespace
from uuid import uuid4

from customer_care.ai.router import full_parent_draft
from customer_care.ai.providers import DeterministicTestGenerationProvider, OpenAIGenerationProvider
from customer_care.rag.service import Evidence


def evidence(content: str = "# Chunk interno\n\nTexto recuperado que não deve aparecer no rascunho.", knowledge_type: str = "CLINICAL") -> Evidence:
    return Evidence(uuid4(), knowledge_type, 1, 0.9, "Fonte interna", "Seção", content, "Trecho interno", knowledge_type == "CLINICAL")


def test_deterministic_provider_returns_a_short_customer_ready_greeting() -> None:
    result = DeterministicTestGenerationProvider().generate([{"role": "customer", "content": "Oi"}], [], "prompt versionado")

    assert result.status == "ANSWER"
    assert result.draft_text == "Oi, tudo bem? Como posso ajudar?"
    assert result.used_hit_ids == []


def test_deterministic_provider_never_copies_retrieved_chunks_into_the_draft() -> None:
    retrieved_chunk = "# Chunk interno\n\nTexto recuperado que não deve aparecer no rascunho."
    result = DeterministicTestGenerationProvider().generate([{"role": "customer", "content": "Qual é o horário?"}], [evidence(retrieved_chunk, "ADMIN_QA")], "prompt versionado")

    assert result.status == "ANSWER"
    assert result.draft_text == "Posso ajudar com sua dúvida. Pode me contar um pouco mais sobre o que precisa?"
    assert retrieved_chunk not in result.draft_text


def test_deterministic_provider_returns_a_safe_general_response_without_evidence() -> None:
    result = DeterministicTestGenerationProvider().generate([{"role": "customer", "content": "Pode me ajudar?"}], [], "prompt versionado")

    assert result.status == "ANSWER"
    assert result.draft_text == "Posso ajudar. Pode me contar um pouco mais sobre o que você precisa?"


def test_highest_ranked_clinical_evidence_makes_the_full_parent_sendable() -> None:
    parent_document = "Orientações completas do documento-pai\n\nMantenha este texto integral."
    result = full_parent_draft([evidence(parent_document)])

    assert result is not None
    assert result.status == "ANSWER"
    assert result.draft_text == parent_document


def test_administrative_evidence_does_not_bypass_llm_generation() -> None:
    assert full_parent_draft([evidence("Resposta administrativa", "ADMIN_QA")]) is None


def test_openai_provider_uses_the_versioned_prompt_without_an_artificial_output_limit() -> None:
    captured: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"status":"ANSWER","draft_text":"Oi, tudo bem?","used_hit_ids":[]}'))],
                usage=None,
            )

    provider = object.__new__(OpenAIGenerationProvider)
    provider.model = "test-model"
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    result = provider.generate([{"role": "customer", "content": "Oi"}], [evidence()], "PROMPT VERSIONADO")

    assert result.draft_text == "Oi, tudo bem?"
    assert "max_completion_tokens" not in captured
    messages = captured["messages"]
    assert isinstance(messages, list)
    assert messages[0]["content"].startswith("PROMPT VERSIONADO")
