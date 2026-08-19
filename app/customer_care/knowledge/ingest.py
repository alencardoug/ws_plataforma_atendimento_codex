import argparse
import hashlib
import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from customer_care.audit.service import record_event
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import KnowledgeChunk, KnowledgeDocument, QAEntry
from customer_care.knowledge.embeddings import DeterministicTestEmbeddingProvider, EmbeddingProvider, OpenAIEmbeddingProvider

FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
SECTION = re.compile(r"^## (.+?)\n\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)


def digest(value: str) -> str:
    return hashlib.sha256(value.strip().encode()).hexdigest()


def qa_content_hash(question: str, answer: str) -> str:
    return digest(f"{question}\n{answer}")


def chunk_content_hash(heading: str, content: str) -> str:
    return digest(f"{heading}\n{content}")


def needs_reembedding(record: QAEntry | KnowledgeChunk, content_hash: str, provider: EmbeddingProvider) -> bool:
    return record.content_hash != content_hash or record.embedding_model != provider.model


def apply_embedding(record: QAEntry | KnowledgeChunk, provider: EmbeddingProvider, content_hash: str, vector: list[float]) -> None:
    """Shared by the batch ingest CLI and V2-8's CRUD service (plan.md §10) —
    the only place embedding metadata fields are set, so both paths stay
    consistent by construction rather than by convention."""
    record.content_hash = content_hash
    record.embedding = vector
    record.embedding_provider = provider.name
    record.embedding_model = provider.model
    record.embedding_dimension = provider.dimension
    record.embedded_at = datetime.now(UTC)


def parse_parent(path: Path, expected_id: str) -> tuple[dict[str, str], str, list[tuple[str, str]]]:
    raw = path.read_text(encoding="utf-8")
    match = FRONT_MATTER.match(raw)
    if not match:
        raise ValueError(f"missing front matter: {path}")
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if separator:
            metadata[key.strip()] = value.strip().strip('"')
    if metadata.get("document_id") != expected_id:
        raise ValueError(f"document_id mismatch: {path}")
    body = raw[match.end():].strip()
    sections = [(heading.strip(), content.strip()) for heading, content in SECTION.findall(body)]
    clinical_sections = sections[:10]
    if len(clinical_sections) != 10 or any(not content for _, content in clinical_sections):
        raise ValueError(f"expected ten non-blank clinical child sections: {path}")
    return metadata, body, clinical_sections


def ingest(corpus_root: Path, provider: EmbeddingProvider) -> dict[str, int]:
    if provider.dimension != 1536:
        raise ValueError("V1 schema requires exactly 1536 embedding dimensions")
    run_id = str(uuid4())
    counts = {"inserted": 0, "updated": 0, "embedded": 0, "skipped": 0}
    session_factory = get_session_factory()
    with session_factory() as session:
        record_event(session, "knowledge.ingestion_started", "SYSTEM", payload={"ingestion_run_id": run_id, "source_type": "ADMIN_QA+CLINICAL"})
        session.commit()
        try:
            catalog_path = corpus_root / "catalog.jsonl"
            catalog_sources = [json.loads(line) for line in catalog_path.read_text(encoding="utf-8").splitlines()]
            qa_path = corpus_root / "qa" / "qa-catalog.jsonl"
            qa_sources = [json.loads(line) for line in qa_path.read_text(encoding="utf-8").splitlines()]
            pending_texts: list[str] = []
            for source in catalog_sources:
                source_path = corpus_root.parent / source["path"]
                if not source_path.exists():
                    source_path = corpus_root.parent / Path(source["path"]).relative_to("documents")
                _, _, sections = parse_parent(source_path, source["document_id"])
                for ordinal, (heading, content) in enumerate(sections, 1):
                    value = f"{heading}\n{content}"
                    current_chunk = session.get(KnowledgeChunk, f"{source['document_id']}-C{ordinal:02d}")
                    if not current_chunk or current_chunk.content_hash != digest(value) or current_chunk.embedding_model != provider.model:
                        pending_texts.append(value)
            for source in qa_sources:
                value = f"{source['question']}\n{source['answer']}"
                current_qa = session.get(QAEntry, source["qa_id"])
                if not current_qa or current_qa.content_hash != digest(value) or current_qa.embedding_model != provider.model:
                    pending_texts.append(value)
            embedding_cache: dict[str, list[float]] = {}
            batch_size = 100
            for offset in range(0, len(pending_texts), batch_size):
                batch = pending_texts[offset:offset + batch_size]
                embedding_cache.update(zip(batch, provider.embed(batch), strict=True))
            for source in catalog_sources:
                source_path = corpus_root.parent / source["path"] if source["path"].startswith("documents/") else corpus_root / source["path"]
                if not source_path.exists():
                    source_path = corpus_root.parent / Path(source["path"]).relative_to("documents")
                front, body, sections = parse_parent(source_path, source["document_id"])
                parent_hash = digest(body)
                document = session.get(KnowledgeDocument, source["document_id"])
                if not document:
                    document = KnowledgeDocument(
                        document_id=source["document_id"], title=source["title"], document_type="orientacao_clinica",
                        cancer_type=source["metadata"].get("cancer_type"), care_phase=source["metadata"].get("care_phase"),
                        procedure_slug=source["metadata"].get("procedure_slug"), audience=["paciente", "familiar"], language="pt-BR",
                        responsible_physician=source["responsible_physician"], version=source["version"], status="published",
                        created_at=date.fromisoformat(front["created_at"]), last_reviewed_at=date.fromisoformat(front["last_reviewed_at"]),
                        next_review_at=date.fromisoformat(front["next_review_at"]), patient_markdown_path=source["path"],
                        content_markdown=body, content_hash=parent_hash, customer_citation_allowed=True, is_active=True,
                        dynamic_data_required=False, metadata_json=source["metadata"],
                    )
                    session.add(document)
                    counts["inserted"] += 1
                elif document.content_hash != parent_hash:
                    document.content_markdown = body
                    document.content_hash = parent_hash
                    document.updated_at = datetime.now(UTC)
                    counts["updated"] += 1
                else:
                    counts["skipped"] += 1
                for ordinal, (heading, content) in enumerate(sections, 1):
                    chunk_id = f"{source['document_id']}-C{ordinal:02d}"
                    content_hash = chunk_content_hash(heading, content)
                    chunk = session.get(KnowledgeChunk, chunk_id)
                    needs_embedding = not chunk or needs_reembedding(chunk, content_hash, provider)
                    vector = embedding_cache[f"{heading}\n{content}"] if needs_embedding else None
                    if not chunk:
                        chunk = KnowledgeChunk(chunk_id=chunk_id, parent_document_id=source["document_id"], ordinal=ordinal, heading=heading, content_markdown=content, retrieval_intents=[], symptoms=[], urgency="emergencia" if heading == "Quando procurar emergência" else "contato_no_mesmo_dia" if heading == "Quando falar com a equipe no mesmo dia" else "educativo", metadata_json={**source["metadata"], "section": heading})
                        session.add(chunk)
                        counts["inserted"] += 1
                    elif chunk.content_hash != content_hash:
                        chunk.ordinal = ordinal
                        chunk.heading = heading
                        chunk.content_markdown = content
                        chunk.metadata_json = {**source["metadata"], "section": heading}
                        chunk.updated_at = datetime.now(UTC)
                        counts["updated"] += 1
                    if needs_embedding:
                        assert vector is not None
                        apply_embedding(chunk, provider, content_hash, vector)
                        counts["embedded"] += 1
            for source in qa_sources:
                content_hash = qa_content_hash(source["question"], source["answer"])
                qa = session.get(QAEntry, source["qa_id"])
                needs_embedding = not qa or needs_reembedding(qa, content_hash, provider)
                vector = embedding_cache[f"{source['question']}\n{source['answer']}"] if needs_embedding else None
                if not qa:
                    qa = QAEntry(qa_id=source["qa_id"], category=source["category"], question=source["question"], answer_markdown=source["answer"], retrieval_intents=[], dynamic_data_required=source["dynamic_data_required"], dynamic_resolver=source["dynamic_resolver"], metadata_json=source["metadata"], customer_citation_allowed=False)
                    session.add(qa)
                    counts["inserted"] += 1
                elif (
                    qa.content_hash != content_hash
                    or qa.category != source["category"]
                    or qa.dynamic_data_required != source["dynamic_data_required"]
                    or qa.dynamic_resolver != source["dynamic_resolver"]
                    or qa.metadata_json != source["metadata"]
                ):
                    # Correction (2026-08-19, found while re-configuring
                    # QA-014/015/019/020's dynamic_resolver for spec 004):
                    # this branch previously keyed only on content_hash
                    # (question+answer text), so a source edit that changed
                    # only dynamic_data_required/dynamic_resolver/category/
                    # metadata — with question/answer text left untouched —
                    # was silently never applied on re-ingest.
                    qa.category = source["category"]
                    qa.question = source["question"]
                    qa.answer_markdown = source["answer"]
                    qa.dynamic_data_required = source["dynamic_data_required"]
                    qa.dynamic_resolver = source["dynamic_resolver"]
                    qa.metadata_json = source["metadata"]
                    qa.updated_at = datetime.now(UTC)
                    counts["updated"] += 1
                if needs_embedding:
                    assert vector is not None
                    apply_embedding(qa, provider, content_hash, vector)
                    counts["embedded"] += 1
                else:
                    counts["skipped"] += 1
            record_event(session, "knowledge.ingestion_completed", "SYSTEM", payload={"ingestion_run_id": run_id, **counts})
            session.commit()
            return counts
        except Exception as exc:
            session.rollback()
            record_event(session, "knowledge.ingestion_failed", "SYSTEM", payload={"ingestion_run_id": run_id, "error_class": type(exc).__name__})
            session.commit()
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest the approved synthetic V1 corpus")
    parser.add_argument("--corpus-root", type=Path, default=Path("/workspace/documents"))
    parser.add_argument("--deterministic-test-embeddings", action="store_true")
    args = parser.parse_args()
    provider: EmbeddingProvider = DeterministicTestEmbeddingProvider() if args.deterministic_test_embeddings else OpenAIEmbeddingProvider()
    print(json.dumps(ingest(args.corpus_root, provider), sort_keys=True))


if __name__ == "__main__":
    main()
