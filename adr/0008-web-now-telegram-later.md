# ADR 0008 — Web Channel Now, Telegram Adapter Later

Status: Accepted

## Decision

V1 implements web only. Conversation/application services operate on normalized commands independent of web transport.

## Consequences

Future Telegram should map into the same engine rather than duplicate RAG/business logic.
