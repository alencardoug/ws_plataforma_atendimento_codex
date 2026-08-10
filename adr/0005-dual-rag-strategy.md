# ADR 0005 — Dual RAG Strategy

Status: Accepted

## Decision

Administrative knowledge is indexed as flat Q&A records. Clinical knowledge uses child embeddings with parent context expansion.

## Consequences

One canonical knowledge model carries `knowledge_type`, hierarchy, and exposure metadata; retrieval remains explainable without forcing parent-child onto administrative content.
