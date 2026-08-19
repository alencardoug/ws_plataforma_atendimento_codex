"""Executable ingestion idempotency and changed-content re-embedding smoke."""

import json
import shutil
import tempfile
from pathlib import Path

from sqlalchemy import select

from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import QAEntry
from customer_care.knowledge.embeddings import DeterministicTestEmbeddingProvider
from customer_care.knowledge.ingest import digest, ingest


def run() -> None:
    provider = DeterministicTestEmbeddingProvider()
    with tempfile.TemporaryDirectory(prefix="v1-ingestion-") as directory:
        corpus = Path(directory) / "documents"
        shutil.copytree("/workspace/documents", corpus)
        first = ingest(corpus, provider)
        assert first["embedded"] == 658, first  # 656 + QA-087/088 (specs/004-dynamic-appointment-availability T070)
        unchanged = ingest(corpus, provider)
        assert unchanged["embedded"] == 0 and unchanged["updated"] == 0, unchanged

        catalog = corpus / "qa" / "qa-catalog.jsonl"
        rows = [json.loads(line) for line in catalog.read_text(encoding="utf-8").splitlines()]
        changed = rows[0]
        changed["answer"] = f"{changed['answer']}\n\nAtualização sintética controlada."
        catalog.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")

        reconciled = ingest(corpus, provider)
        assert reconciled["embedded"] == 1 and reconciled["updated"] == 1, reconciled
        with get_session_factory()() as db:
            qa = db.scalar(select(QAEntry).where(QAEntry.qa_id == changed["qa_id"]))
            assert qa is not None
            assert qa.answer_markdown == changed["answer"]
            assert qa.content_hash == digest(f"{changed['question']}\n{changed['answer']}")

    print("ingestion_changed_smoke_ok: idempotent unchanged run and one-record re-embedding")


if __name__ == "__main__":
    run()
