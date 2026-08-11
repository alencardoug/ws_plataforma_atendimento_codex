import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PromptTemplate:
    content: str
    version: str


def load_prompt(name: str = "rag_answer.md") -> PromptTemplate:
    candidates = [Path("/workspace/prompts") / name, Path(__file__).resolve().parents[3] / "prompts" / name]
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise RuntimeError(f"Prompt not found: {name}")
    content = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(content.encode()).hexdigest()[:12]
    return PromptTemplate(content=content, version=f"{name}:{digest}")
