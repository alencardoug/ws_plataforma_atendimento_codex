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

Implementation must document one reproducible command for each.

## 4. Ingest demo knowledge

Implementation must document commands for:

- administrative Q&A;
- clinical parent-child.

## 5. Open application

Expected routes conceptually:

- customer: `/customer`
- operator: `/operator`

## 6. Run acceptance

Follow `acceptance.md`, including six customer tabs and operator capacity=4.
