# Development

## Local-first acceptance

The entire V1 must run locally via Docker Compose.

Expected developer commands (exact names may be implemented as Makefile/task aliases):

```bash
docker compose up --build
# migrations
# seed operator
# ingest demo knowledge
# run tests
```

## Repository target shape

```text
app/
    auth/
    anonymous_access/
    conversations/
    autonomy/
    knowledge/
    rag/
    ai/
    operator_workspace/
    audit/
    shared/
  tests/
  alembic/
  requirements*.txt
frontend/
  src/
    api/
    customer/
    operator/
    shared/
  tests/
infra/
  demo-data/
  scripts/
docker-compose.yml
.env.example
```

## Quality gates

Backend:

- formatter/linter;
- type checking at a pragmatic strictness;
- pytest unit/integration.

Frontend:

- ESLint;
- TypeScript type check;
- component tests;
- E2E test runner.

## Dependency policy

Prefer mature direct dependencies. Do not add LangChain/LlamaIndex merely to wrap one embedding and one generation call in V1 unless the plan documents a concrete benefit. Keep RAG orchestration simple and inspectable.
