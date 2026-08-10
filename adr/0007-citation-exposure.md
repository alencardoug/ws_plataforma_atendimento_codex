# ADR 0007 — Server-Side Citation Exposure Policy

Status: Accepted

## Decision

Operators can inspect all evidence. Customer-visible citations are allowed only for knowledge records explicitly marked exposable. Clinical parent/source references default to exposable; administrative Q&A defaults internal.

## Consequences

Frontend cannot leak internal evidence by simply rendering model output.
