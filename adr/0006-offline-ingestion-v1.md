# ADR 0006 — Offline Ingestion in V1

Status: Accepted

## Context

Knowledge exists conceptually/in PostgreSQL preparation but is not vectorized, so retrieval cannot function without ingestion.

## Decision

V1 includes an idempotent CLI/application ingestion path and embedding generation. No ingestion UI.

## Consequences

RAG is demonstrably real while admin-console complexity remains deferred.
