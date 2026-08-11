# Customer Care AI — Spec-Driven Development Repository

Status: **V1 IMPLEMENTED — local acceptance gates completed**.

This repository defines a single-tenant AI-assisted customer-service platform for a Cancer Center. The long-term product evolves from manual human service to governed AI autonomy, but the currently authorized implementation scope is **V1 only**.

## Inicialização local

### Pré-requisitos

- Docker com o plugin Docker Compose (`docker compose`);
- uma chave da OpenAI para ingestão vetorial e para as capacidades N2/RAG reais.

Todo o conteúdo e todas as credenciais usados neste V1 devem ser sintéticos/de demonstração.

### 1. Configurar o ambiente

Na raiz do repositório:

```bash
cp .env.example .env
```

Edite `.env` e, no mínimo:

- substitua `POSTGRES_PASSWORD`, `ANONYMOUS_TOKEN_PEPPER` e `OPERATOR_AUTH_SECRET` por valores locais fortes e distintos;
- preencha `OPENAI_API_KEY`;
- escolha `GLOBAL_MATURITY_MODE=N1` ou `N2`;
- mantenha `OPERATOR_MAX_ACTIVE_CONVERSATIONS=4` para o cenário de aceitação.

Não versione o arquivo `.env` nem segredos reais.

### 2. Preparar banco, operador e conhecimento

```bash
docker compose up -d --build db
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python -m customer_care.auth.seed_operator \
  --email operator@example.com \
  --password 'escolha-uma-senha-local' \
  --display-name 'Operador Demo'
docker compose run --rm backend python -m customer_care.knowledge.ingest
```

A ingestão é idempotente e carrega as duas famílias de conhecimento do V1: Q&A administrativo plano e conteúdo clínico parent-child. Ela usa o provedor de embeddings configurado em `.env`.

### 3. Subir a aplicação

```bash
docker compose up -d --build
docker compose ps
```

Verifique o backend:

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/ready
```

Para acompanhar ou encerrar a execução:

```bash
docker compose logs -f backend frontend
docker compose down
```

`docker compose down` preserva o volume do PostgreSQL. Procedimentos de reset da demonstração estão em [`OPERATIONS.md`](OPERATIONS.md).

## Onde acessar e como usar

Com a stack em execução:

| Capacidade | Endereço | Como usar |
|---|---|---|
| Atendimento do cliente anônimo | <http://localhost:5173/customer> | Abra a conversa e envie mensagens; cada aba mantém seu próprio token em `sessionStorage`. |
| Área do operador | <http://localhost:5173/operator> | Entre com o e-mail e a senha fornecidos ao comando `seed_operator`; reivindique conversas manualmente. |
| Documentação interativa da API | <http://localhost:8000/docs> | Explore e execute os endpoints FastAPI. |
| Especificação OpenAPI | <http://localhost:8000/openapi.json> | Consulte o contrato servido pela implementação. |
| Health/readiness | <http://localhost:8000/health> e <http://localhost:8000/ready> | Confirme processo ativo e acesso ao banco, respectivamente. |
| PostgreSQL/pgvector | `localhost:5433` | Acesso técnico local com as credenciais de `.env`; não é uma interface da aplicação. |

Fluxo funcional recomendado:

1. abra `/operator` e autentique o operador;
2. abra `/customer` em até seis abas e inicie uma conversa em cada uma;
3. envie uma mensagem por aba;
4. no operador, reivindique até quatro conversas — as demais permanecem na fila;
5. em N2, gere um rascunho fundamentado, confira evidências, edite se necessário e envie explicitamente; o rascunho nunca é mostrado automaticamente ao cliente;
6. use `Take over` para reduzir uma conversa N2 a N1 e continuar manualmente;
7. encerre a conversa pela área do operador.

Em N1, o atendimento é manual; a busca assistiva retorna somente evidências quando `N1_ASSISTIVE_SEARCH_ENABLED=true`. Em N2, falhas de IA/RAG não impedem o envio manual. O roteiro completo da demonstração está em [`specs/001-v1-assisted-customer-service/acceptance.md`](specs/001-v1-assisted-customer-service/acceptance.md).

## Canonical engineering method

Use Spec-Driven Development (SDD) with GitHub Spec Kit conventions.

Canonical lifecycle for a feature:

1. constitution
2. specify
3. clarify when ambiguity remains
4. plan
5. tasks
6. analyze consistency
7. implement
8. converge against spec and acceptance criteria

`grill-me` / aggressive design interview is optional discovery before a future spec is frozen. It is not a second source of truth. Resolved answers must be written into the canonical spec/ADR.

## V1 product thesis

V1 proves a complete assisted-service loop:

`anonymous customer -> waiting queue -> operator -> RAG evidence -> AI draft in N2 -> explicit operator action -> customer-visible answer -> audit`

The application supports only two durable global maturity modes:

- **N1 Manual** — customer and operator converse manually. Optional assistive knowledge search can be enabled by configuration.
- **N2 Copilot** — RAG + AI can generate a grounded draft for the operator, but **AI output is never sent directly to the customer**. An operator may take over a conversation, reducing that conversation from N2 to N1 for the remainder of the session.

## V1 actors

- anonymous customer;
- authenticated operator;
- runtime configuration managed outside the UI.

Supervisor, manager, and AI Ops interfaces are future scope.

## V1 knowledge

V1 includes a usable RAG backed by PostgreSQL 17 + pgvector. The approved
knowledge corpus has already been ingested and vectorized: administrative Q&A
records are retrieved directly, while clinical child chunks are vectorized and
expanded to their parent documents during retrieval.

Two source families are supported:

1. **Administrative Q&A** — flat Q&A records; no parent-child hierarchy.
2. **Clinical knowledge** — pre-structured parent-child content; child chunks are indexed for retrieval and parent context is supplied to generation.

Ingestion is an offline/administrative command or script, **not an ingestion UI**.

Clinical source references may be exposed to the customer. Administrative Q&A source details remain operator-only.

## V1 concurrency demo

One operator can have at most **4 active conversations**. The acceptance demo creates **6 anonymous customer sessions in separate browser tabs**. The operator claims 4; 2 remain waiting. This is a functional concurrency/queue test, not a production load target.

Anonymous customer session credentials are per-tab, not account credentials. A per-conversation opaque access token is stored in browser `sessionStorage`, allowing multiple independent customers to be simulated in tabs of one browser.

## Hard invariants

1. V1 supports N1/N2 only.
2. No AI draft can become customer-visible without explicit operator send action.
3. `Take over` is an operator-controlled per-conversation downgrade from N2 to N1.
4. Customer data is synthetic/demo only in V1.
5. No chain-of-thought is persisted or shown.
6. AI generations are traceable to prompt version, model configuration, retrieval run, and source records.
7. PostgreSQL is the transactional source of truth.
8. Critical operational facts are recorded as append-only audit events.
9. Failure of AI/RAG must not prevent manual customer service.
10. Web is the only channel implemented in V1, but conversation/application services must remain channel-neutral for later Telegram support.

## Repository map

```text
.
├── .specify/memory/constitution.md
├── AGENTS.md
├── CLAUDE.md
├── PROJECT_STATE.md
├── PROMPT_START_V1.md
├── REQUIREMENTS.md
├── ARCHITECTURE.md
├── DATA_MODEL.md
├── API_SPEC.md
├── SECURITY.md
├── THREAT_MODEL.md
├── TEST_PLAN.md
├── OBSERVABILITY.md
├── DEVELOPMENT.md
├── DEPLOYMENT.md
├── OPERATIONS.md
├── ROADMAP.md
├── DECISIONS.md
├── GLOSSARY.md
├── docs/
├── adr/
├── prompts/
└── specs/001-v1-assisted-customer-service/
    ├── spec.md
    ├── plan.md
    ├── tasks.md
    ├── research.md
    ├── data-model.md
    ├── quickstart.md
    ├── acceptance.md
    ├── contracts/openapi.yaml
    └── checklists/
```

## Agent instruction

Implement **only** `specs/001-v1-assisted-customer-service/` until a human explicitly authorizes a subsequent feature/version.
