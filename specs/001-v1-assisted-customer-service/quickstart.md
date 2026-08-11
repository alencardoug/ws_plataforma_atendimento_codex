# V1 Quickstart Contract

The implementation must update this file with exact commands. The intended operator experience is:

## 1. Configure

Copy `.env.example` to `.env` and set required local secrets/model configuration.

Expected configuration includes:

```text
GLOBAL_MATURITY_MODE=N2
N1_ASSISTIVE_SEARCH_ENABLED=true
OPERATOR_MAX_ACTIVE_CONVERSATIONS=4
OPENAI_API_KEY=...
AI_GENERATION_MODEL=...
AI_EMBEDDING_MODEL=...
```

## 2. Start infrastructure/application

```bash
docker compose up --build
```

## 3. Apply migrations / seed operator

Apply the forward-only migration and seed a synthetic operator:

```bash
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python -m customer_care.auth.seed_operator \
  --email operator@example.com --password 'choose-a-local-demo-password' \
  --display-name 'Operador Demo'
```

When upgrading an existing PostgreSQL 16 environment, do not attach its data
directory directly to PostgreSQL 17. Back up/restore or recreate the synthetic
local volume, then run Alembic and ingestion. Compose uses the new named volume
`postgres17_data` to prevent accidental major-version reuse.

## 4. Ingest demo knowledge

Both approved families are reconciled by one idempotent command:

```bash
docker compose run --rm backend python -m customer_care.knowledge.ingest
```

This requires the configured OpenAI embedding provider. Automated local tests
may use `--deterministic-test-embeddings`; those vectors do not demonstrate
semantic retrieval quality and are forbidden as acceptance evidence.

## 5. Open application

Expected routes conceptually:

- customer: `/customer`
- operator: `/operator`

## 6. Run acceptance

Follow `acceptance.md`, including six customer tabs and operator capacity=4.
Automated browser acceptance reads credentials only from the process environment:

```bash
E2E_OPERATOR_EMAIL=operator@example.com \
E2E_OPERATOR_PASSWORD='your-local-seeded-password' \
npm --prefix frontend run test:e2e
```
