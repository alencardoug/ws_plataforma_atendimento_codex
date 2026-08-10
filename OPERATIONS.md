# Operations — V1 Demo

## Startup

1. configure `.env`;
2. start PostgreSQL/backend/frontend;
3. apply migrations;
4. seed at least one operator;
5. ingest administrative + clinical demo knowledge;
6. verify health endpoints.

## Mode configuration

V1 mode is durable for the running deployment and configured outside the product UI:

- `GLOBAL_MATURITY_MODE=N1|N2`
- `N1_ASSISTIVE_SEARCH_ENABLED=true|false`
- `OPERATOR_MAX_ACTIVE_CONVERSATIONS=4`

UI displays the current effective/global mode to the operator but cannot raise it.

## Failure modes

AI provider unavailable:

- show operator a non-fatal draft-generation error;
- manual send remains available.

Vector search unavailable:

- show knowledge/RAG error;
- N1 manual service remains available.

Database unavailable:

- service is unavailable; do not fake persistence.

## Demo reset

Provide a documented way to delete/reseed synthetic conversations and re-ingest demo knowledge without manually editing database tables.
