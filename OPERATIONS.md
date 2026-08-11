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

All V1 data is synthetic. To reset only service interactions while preserving
operators, migrations, and the knowledge corpus:

```bash
docker compose exec db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "TRUNCATE customer_service.audit_events,
            customer_service.message_citations,
            customer_service.ai_generation_sources,
            customer_service.ai_generations,
            customer_service.retrieval_hits,
            customer_service.retrieval_runs,
            customer_service.messages,
            customer_service.conversation_assignments,
            customer_service.conversations CASCADE;"'
```

This is destructive and appropriate only for the local synthetic demo. Re-seed
an operator with a password supplied at invocation time:

```bash
docker compose run --rm backend python -m customer_care.auth.seed_operator \
  --email operator@example.com --password 'choose-a-local-password' \
  --display-name 'Operador Demo'
```

Reconcile/re-embed the approved corpus idempotently:

```bash
docker compose run --rm backend python -m customer_care.knowledge.ingest
```

For a completely fresh local PostgreSQL 17 database, explicitly remove the
Compose volume, start `db`, apply `alembic upgrade head`, seed, and ingest. Never
attach a PostgreSQL 16 data directory directly to PostgreSQL 17.
