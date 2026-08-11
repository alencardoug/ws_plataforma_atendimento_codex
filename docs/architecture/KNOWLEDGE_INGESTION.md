# Knowledge Ingestion — V1

## Goal

Turn the existing non-vectorized knowledge assets into a deterministic, traceable PostgreSQL/pgvector corpus suitable for V1 RAG.

Ingestion is **offline/administrative**, not part of the customer/operator UI.

## Canonical knowledge families

### 1. Administrative Q&A

Flat records. No parent-child hierarchy.

Canonical input fields:

- `external_id`
- `question`
- `answer`
- `category` (optional but recommended)
- `title` or source label
- `source_uri` or source reference if available
- `version` / updated-at metadata when available
- `active`

Index text:

`question + normalized answer`

Grounding context:

`answer` plus concise source metadata.

Customer citation exposure:

`false` by default.

### 2. Clinical parent-child

Content is already physically structured as `content.documents` parents and
`content.chunks` children linked by `parent_document_id`.

Canonical parent fields:

- `document_id` / `external_id`
- `content` loaded from the Markdown path in `documents/catalog.jsonl`
- `title`
- `section/path`
- source/version metadata

Canonical child fields:

- `external_id`
- `parent_document_id`
- `content`
- section/path metadata

Index:

- child content is embedded and vector indexed;
- parent need not be vector indexed in V1 unless implementation evidence proves value.

Do not synthesize a duplicate PARENT chunk. Ingestion validates that catalog,
Markdown front matter, existing document row, and every child agree on the
stable parent ID, then persists the parent-body snapshot/hash on the document.

Retrieval:

`query -> child hits -> parent expansion -> dedupe parents -> generation context`

Customer citation exposure:

`true` for the approved parent source projection by default.

## Idempotency

Re-running ingestion with unchanged `external_id + source version/content hash` must not create duplicates.

Recommended behavior:

- calculate content hash;
- upsert document/chunks;
- embed only new/changed searchable records;
- mark removed/deactivated source records inactive rather than silently reusing stale text;
- record ingestion run audit events.

## Embedding metadata

Store at minimum:

- embedding provider;
- embedding model identifier;
- dimension;
- embedded timestamp;
- source content hash.

If embedding model/dimension changes, do not mix incompatible vectors in the same indexed representation without an explicit migration/re-embedding strategy.

## Ingestion command

Implementation should expose a CLI/application entry point, e.g. conceptually:

```bash
poetry run python -m app.knowledge.ingest --source admin-qna --path ...
poetry run python -m app.knowledge.ingest --source clinical-parent-child --path ...
```

Exact syntax is implementation detail. It must be documented in the quickstart.

## Validation failures

Reject or quarantine records with:

- missing external IDs;
- blank searchable content;
- child referencing missing parent;
- duplicate external IDs with conflicting hierarchy;
- invalid source exposure metadata.

Do not silently truncate or invent content.
