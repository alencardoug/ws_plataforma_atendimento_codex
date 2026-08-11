import hashlib
import math
from typing import Protocol

from openai import OpenAI

from customer_care.shared.settings import get_settings


class EmbeddingProvider(Protocol):
    name: str
    model: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbeddingProvider:
    name = "openai"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for real ingestion")
        self.model = settings.ai_embedding_model
        self.dimension = settings.ai_embedding_dimension
        self.client = OpenAI(api_key=settings.openai_api_key.get_secret_value())

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(model=self.model, input=texts, dimensions=self.dimension)
        return [item.embedding for item in sorted(response.data, key=lambda item: item.index)]


class DeterministicTestEmbeddingProvider:
    """Stable local test adapter; never suitable for acceptance relevance claims."""

    name = "deterministic-test"
    model = "sha256-test-v1"

    def __init__(self, dimension: int = 1536) -> None:
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for value in texts:
            raw = hashlib.shake_256(value.encode()).digest(self.dimension * 2)
            vector = [int.from_bytes(raw[index:index + 2], "big") / 32767.5 - 1 for index in range(0, len(raw), 2)]
            norm = math.sqrt(sum(item * item for item in vector)) or 1
            vectors.append([item / norm for item in vector])
        return vectors
