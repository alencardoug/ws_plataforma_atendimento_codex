# PROCESSO_RAG.md — Como gerenciar (CRUD) as informações do RAG

Guia prático para **criar, atualizar, desativar e reindexar** cada tipo de
informação que alimenta o RAG desta plataforma. Primeiro o **processo local**
(Docker Compose), depois o **processo em produção** (Cloud Run + Firebase +
Neon).

Conferido contra o código em 2026-08-21 (`knowledge/ingest.py`,
`knowledge/router.py`, `rag/service.py`, `scheduling/*`, `deploy/*`).

---

## 1. Os quatro tipos de informação (e o que cada um vira no banco)

| # | Tipo | Fonte-arquivo | Tabela(s) | É vetorizado? | Passa por LLM na resposta? |
|---|---|---|---|---|---|
| 1 | **Q&A administrativo estático** | `documents/qa/qa-catalog.jsonl` | `content.qa_entries` | Sim (`pergunta\nresposta`) | Sim — `prompts/rag_answer.md` compõe o texto |
| 2 | **Q&A administrativo dinâmico** | idem, com `dynamic_data_required=true` + `dynamic_resolver` **ou** vínculo `qa_dynamic_bindings` | `content.qa_entries` (+ `content.qa_dynamic_bindings`) | Sim (o texto-gatilho) | **Não** — resolvedor determinístico substitui `{{variáveis}}` |
| 3 | **Conhecimento clínico pai + filhos** | `documents/catalog.jsonl` + `documents/clinical/**/**.md` | `content.documents` (pai) + `content.chunks` (filhos) | **Só os filhos** | **Não** quando é a evidência nº 1 — devolve o documento-pai inteiro |
| 4 | **Dados de agenda (agendamento)** | migrações Alembic (referência) + ações do operador (vagas) | `scheduling.*` | Não (não é "conhecimento") | **Não** — resolvedores `appointment_availability` / `price_lookup` leem SQL |

> **"Chunk" ≠ "Q&A".** Um Q&A é **um registro plano** — ele já é a unidade
> recuperável, não tem pai/filho. "Chunk" só existe no conhecimento clínico:
> é a **seção-filha** de um documento-pai. Só os chunks têm `embedding`.

### Conceitos comuns a todos

- **Embedding**: `text-embedding-3-small`, 1536 dimensões, distância de cosseno,
  índice HNSW. Gerado na hora em cada criação/edição (tela ou API) e em lote
  pela ingestão.
- **`content_hash`**: SHA-256 do conteúdo. A ingestão só re-embeda quando o
  hash **ou** o `embedding_model` mudou → reingestão é idempotente e barata.
- **Soft delete**: "Desativar" seta `is_active=false`; a linha continua no
  banco, mas `retrieve()` filtra `is_active IS TRUE`. Não há hard delete pela
  aplicação.
- **Categoria é FK**: `qa_entries.category` e `documents.cancer_type` apontam
  para `content.categories(slug)`. Um valor de categoria novo **precisa existir
  como linha em `content.categories` antes** (senão a ingestão falha com
  violação de FK). Crie pela aba Registros ("Criar nova categoria") ou por SQL.

---

## 2. PROCESSO LOCAL (Docker Compose)

### 2.1 Pré-requisitos

```bash
cp .env.example .env          # ajuste POSTGRES_PASSWORD, *_SECRET, *_PEPPER
# preencha OPENAI_API_KEY (embeddings reais); ou use AI_PROVIDER=deterministic-test
docker compose up -d --build db
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend python -m customer_care.auth.seed_operator \
  --email operator@example.com --password 'senha-local' --display-name 'Operador Demo'
docker compose run --rm backend python -m customer_care.knowledge.ingest
docker compose up -d --build
```

Há **duas formas** de mexer no conhecimento: **(A) em lote pelos arquivos-fonte
+ ingestão** (forma canônica, versionada em Git) e **(B) interativa pela aba
Registros / API** (mudança pontual, grava direto no banco). Use (A) para
conteúdo que deve ficar no repositório; (B) para ajustes rápidos de demo.

---

### 2.2 Tipo 1 — Q&A administrativo estático

**Forma A (lote):** edite `documents/qa/qa-catalog.jsonl` — uma linha JSON por
entrada:

```json
{"qa_id": "QA-101", "category": "instituicao", "question": "Vocês têm estacionamento?", "answer": "Sim, há estacionamento no local (simulação).", "dynamic_data_required": false, "dynamic_resolver": null, "metadata": {"language": "pt-BR", "reading_level": "linguagem_simples", "simulated": true}}
```

Campos: `qa_id` (PK, estável — não reutilize), `category` (slug existente em
`content.categories`), `question`, `answer`, `dynamic_data_required`,
`dynamic_resolver` (`null` aqui), `metadata` (objeto livre).

Depois:

```bash
docker compose run --rm backend python -m customer_care.knowledge.ingest
```

- Linha nova → INSERT + embedding.
- `question`/`answer` alterados → UPDATE + re-embedding.
- `category`/`dynamic_*`/`metadata` alterados (texto igual) → UPDATE **sem**
  re-embedding (corrigido em 2026-08-19; antes era ignorado).
- Nada mudou → skip.
- **Não há remoção por ausência**: tirar a linha do arquivo **não** desativa a
  entrada. Para desativar, use a aba Registros ou
  `DELETE /operator/knowledge/qa/{qa_id}`.

**Forma B (aba Registros → "Perguntas e respostas"):** escolha/crie a
**Categoria**, escreva **Pergunta** e **Resposta**, deixe "Vínculo dinâmico" em
**"Nenhuma"**, clique **"Adicionar pergunta e resposta"**. Isso cria um
`QAEntry` com `qa_id = qa-<hex12>`, embeda na hora, `customer_citation_allowed=false`.
Editar/desativar: pela lista da própria tela (ou `PATCH`/`DELETE
/operator/knowledge/qa/{qa_id}`).

---

### 2.3 Tipo 2 — Q&A administrativo dinâmico

Há **dois submecanismos** diferentes:

#### 2.3a Resolvedor nomeado (`appointment_availability`, `price_lookup`)

É o que responde preço e vagas de agenda com dados reais do schema `scheduling`.
**Só é configurável pela forma A (JSONL + ingestão).** A aba Registros **não**
escreve o campo `qa_entries.dynamic_resolver`.

```json
{"qa_id": "QA-011", "category": "agenda", "question": "Quero marcar minha primeira consulta. Como faço?", "answer": "Informe a especialidade e a preferência de dia/período. Apresento até quatro vagas reais...", "dynamic_data_required": true, "dynamic_resolver": "appointment_availability", "metadata": {"simulated": true}}
{"qa_id": "QA-025", "category": "preco", "question": "Quanto custa uma consulta de mastologia?", "answer": "O valor fixo é consultado na tabela scheduling.professional_specialties e exibido com (simulação).", "dynamic_data_required": true, "dynamic_resolver": "price_lookup", "metadata": {"simulated": true}}
```

- `dynamic_resolver` só aceita `appointment_availability` ou `price_lookup`
  (allowlist `NAMED_RESOLVERS` em `ai/router.py`). Qualquer outro valor
  (`payment_simulator`, `insurance_lookup`, …) cai no caminho genérico abaixo e,
  sem vínculo configurado, **abstém** de forma segura.
- Reingira depois de editar. O `answer` funciona como um *fallback* textual —
  o resolvedor gera o texto real na hora da resposta.

#### 2.3b Vínculo genérico (`qa_dynamic_bindings`)

Mecanismo de demonstração (V2-6). A aba Registros expõe **só** a tabela
`knowledge_dynamic_fixture` (fixture; nenhuma Q&A de produção usa isso).

Aba Registros → "Perguntas e respostas" → em **"Vínculo dinâmico (opcional)"**
escolha a tabela, adicione **filtro** (coluna = valor) e **colunas de saída**
mapeadas para `{{nome_da_variável}}` que aparecem no texto da resposta. Isso
grava `dynamic_data_required=true` + uma linha em `content.qa_dynamic_bindings`.
Colunas/tabelas são validadas contra a allowlist no momento da gravação (erro
422 se houver typo).

---

### 2.4 Tipo 3 — Conhecimento clínico (pai + chunks)

#### Forma A (lote) — recomendada

1. **Crie o Markdown do pai** em `documents/clinical/<sítio>/<slug>.md` com
   *front matter* YAML e **pelo menos 10 seções `##`** (a ingestão usa as **10
   primeiras** como chunks; um `#` de título e seções extras são ignorados):

   ```markdown
   ---
   document_id: "MAMA-NOVO_TEMA-001"
   title: "Título do documento"
   version: "0.1.0"
   responsible_physician: "Dra. Fulana (simulação)"
   created_at: "2026-08-21"
   last_reviewed_at: "2026-08-21"
   next_review_at: "2027-02-21"
   information_status: "simulação"
   ---

   # Título do documento

   ## Para que serve este documento
   ...
   ## Orientação específica
   ...
   ## Quando falar com a equipe no mesmo dia
   ...
   ## Quando procurar emergência
   ...
   (as 10 primeiras seções `##` viram os chunks C01..C10)
   ```

   > Os cabeçalhos `## Quando falar com a equipe no mesmo dia` e
   > `## Quando procurar emergência` recebem `urgency` especial
   > (`contato_no_mesmo_dia` / `emergencia`); os demais ficam `educativo`.

2. **Registre no catálogo** `documents/catalog.jsonl` — uma linha:

   ```json
   {"document_id": "MAMA-NOVO_TEMA-001", "title": "Título do documento", "path": "documents/clinical/mama/novo-tema.md", "responsible_physician": "Dra. Fulana (simulação)", "version": "0.1.0", "metadata": {"cancer_type": "mama", "care_phase": "cirurgia", "procedure_slug": "novo-tema", "reading_level": "linguagem_simples", "simulated": true}}
   ```

   - `document_id` do JSONL **precisa bater** com o do *front matter*.
   - `metadata.cancer_type` é a **categoria** (FK `content.categories`) — crie
     antes se for nova.

3. Reingira:

   ```bash
   docker compose run --rm backend python -m customer_care.knowledge.ingest
   ```

   O pai vira `content.documents` (com `content_markdown` inteiro, **sem
   embedding**); cada seção vira `content.chunks` `"<document_id>-C01".."-C10"`,
   **com embedding** de `heading\nconteúdo`. Editar o `.md` e reingerir
   re-embeda só os chunks cujo hash mudou.

#### Forma B (aba Registros / API) — parcial

- **Pai:** aba Registros → "Documentos clínicos" → Título + Conteúdo (markdown)
  → "Adicionar documento". Cria `content.documents` (`doc-<hex12>`) **sem chunks
  e sem embedding** → sozinho **não é recuperável**.
- **Chunks:** ⚠️ **a aba não tem formulário para criar chunk** (só "Ver
  seções" e "Desativar"). Crie via API, um por ordinal:

  ```bash
  curl -X POST http://localhost:8000/api/v1/operator/knowledge/clinical-documents/<doc_id>/chunks \
    -H "Authorization: Bearer <token_operador>" -H "Content-Type: application/json" \
    -d '{"ordinal": 1, "heading": "Para que serve este documento", "content_markdown": "..."}'
  ```

  Cada POST cria `"<doc_id>-C0N"` e embeda na hora. Use `PATCH`/`DELETE` no
  mesmo caminho para editar/desativar.

> Regra prática: **conteúdo clínico novo entra pela Forma A** (é o único jeito
> de ter os 10 chunks de forma consistente e versionada). A Forma B serve para
> desativar um documento, corrigir texto do pai, ou emendar um chunk pontual.

---

### 2.5 Tipo 4 — Dados de agenda (agendamento)

**Não passam pela aba Registros.** Dividem-se em:

| Sub-tipo | Como gerenciar | Onde |
|---|---|---|
| Especialidades, profissionais, preços (`professional_specialties.fixed_price_cents`), duração, feriados | **Migração Alembic** nova (ver `20260819_0002` / `20260820_0004` como modelo: `INSERT ... ON CONFLICT DO NOTHING`) | `app/alembic/versions/` |
| **Vagas** (`scheduling.schedule_slots`) | Botões na barra lateral do **Operador**: "Garantir disponibilidade (D+1/D+7)" (`POST /operator/scheduling/ensure-availability`) e "Preencher agenda ampla (até 30/12/2026)" (`POST /operator/scheduling/ensure-wide-availability`) | UI Operador |
| Palavras-chave que mapeiam texto do cliente → especialidade | Constante `SPECIALTY_KEYWORDS` em `scheduling/availability.py` | código |

Depois de adicionar especialidade/preço por migração:

```bash
docker compose run --rm backend alembic upgrade head
```

Nenhuma reingestão é necessária — os resolvedores leem `scheduling.*` em tempo
real. Só garanta que exista uma **Q&A com `dynamic_resolver`** apontando o
assunto (ver 2.3a) e **vagas** criadas pelos botões.

---

### 2.6 Verificar o resultado (local)

- Aba **Operador** → abrir conversa → **"Buscar evidências"** com um texto que
  deva casar; confira `rank`, `score`, e o `matched_child_excerpt` (clínico).
- Conferir embeddings no banco (via cliente SQL na porta `5433`):

  ```sql
  SELECT embedding_model, count(*) FROM content.qa_entries  GROUP BY 1;
  SELECT embedding_model, count(*) FROM content.chunks       GROUP BY 1;
  SELECT count(*) FROM content.documents;   -- pais
  ```

  Se aparecer `sha256-test-v1`, os embeddings estão no modo determinístico
  (teste), não reais.

> ⚠️ **Armadilha conhecida:** rodar `app/tests/... smoke_ingestion_changed.py`
> (ou qualquer coisa que ingira com `--deterministic-test-embeddings`) **reverte
> todos os embeddings do catálogo para hashes de teste**, sem aviso. Se a
> recuperação começar a devolver resultados aleatórios, cheque o
> `embedding_model` acima e reingira com o provedor OpenAI.

---

## 3. PROCESSO EM PRODUÇÃO (Cloud Run + Firebase + Neon)

### 3.1 O que muda em relação ao local

- O banco é **Neon** (Postgres serverless), acessado pela internet com
  `sslmode=require`. A `DATABASE_URL` de produção vive no **Secret Manager**
  (`database-url`).
- O backend no **Cloud Run** escala a zero e **não tem shell interativo**
  prático. Migração e ingestão **não rodam dentro do Cloud Run** —
  `deploy/init-database.sh` roda **na sua máquina**, apontando para a
  `DATABASE_URL` do Neon.
- O frontend é estático no Firebase Hosting; `/api/**` é reescrito para o Cloud
  Run (mesma origem).
- Dado continua **sintético/demonstração** (Constituição, Art. VI).

### 3.2 Caminho recomendado — conteúdo em lote (Tipos 1, 2a, 3, e migrações do 4)

1. Edite os arquivos-fonte no repositório (`documents/qa/qa-catalog.jsonl`,
   `documents/catalog.jsonl`, `documents/clinical/**`, e/ou uma nova migração
   em `app/alembic/versions/`).
2. Faça commit (mantém o repositório como fonte de verdade).
3. Rode a ingestão/migração **local, apontando para o Neon**:

   ```bash
   export DATABASE_URL='postgresql+psycopg://USER:PASS@HOST/neondb?sslmode=require'   # do Secret Manager / painel Neon
   export OPENAI_API_KEY='sk-...'          # embeddings reais
   export ANONYMOUS_TOKEN_PEPPER='...'; export OPERATOR_AUTH_SECRET='...'  # exigidos pelo script
   ./deploy/init-database.sh
   ```

   O script faz, nesta ordem: `alembic upgrade head` → `python -m
   customer_care.knowledge.ingest`. É idempotente (seguro reexecutar).

4. **Se você adicionou/alterou código** (novo resolvedor, mudança de prompt,
   etc.), redeploy do backend:

   ```bash
   ./deploy/deploy-backend.sh          # Cloud Build a partir do Dockerfile da raiz
   ```

   (Só editar JSONL/Markdown **não** exige redeploy — o conteúdo está no banco,
   não na imagem. A **exceção** é `prompts/`, que é copiado para a imagem: mudar
   um prompt exige redeploy.)

5. **Valide com uma chamada real de geração** (não só `/health`/`/ready` — foi
   exatamente o que falhou no primeiro deploy): abra a app de produção, gere um
   rascunho para uma pergunta que use o conteúdo novo.

6. Limpe conversas de validação criadas no teste (ver `DEPLOYMENT.md` passo 5).

### 3.3 Caminho alternativo — ajuste pontual pela UI de produção (Tipos 1, 2b, 3-pai, categorias, desativações)

A app de produção **é a mesma app**. Logado como operador em
`https://<seu-host>.web.app/operator/knowledge`, você pode:

- criar/editar/desativar **Q&A estático**;
- criar **categorias** e ligar/desligar **autonomia por categoria**;
- criar/editar/desativar **documento clínico-pai**;
- configurar **vínculo dinâmico genérico** (só `knowledge_dynamic_fixture`);
- ajustar **janela de veto**, **interruptor geral**, **interruptor N5**,
  `automatic_trigger_idle_seconds`.

Cada ação grava **direto no Neon** e **gera o embedding na hora** (a chave
OpenAI está no ambiente do Cloud Run). Bom para 1–2 correções; ruim para lotes
(sem histórico em Git).

O que a UI de produção **não** faz: criar **chunks clínicos** (sem formulário),
setar `dynamic_resolver` nomeado, e mexer em `scheduling.*`. Para esses:

- **chunks**: `curl` no endpoint `.../clinical-documents/{id}/chunks` contra a
  URL de produção, autenticado — **ou**, melhor, use o caminho em lote (3.2);
- **`dynamic_resolver` / especialidades / preços**: caminho em lote (3.2),
  editando o JSONL / criando migração.

### 3.4 SQL direto no Neon — último recurso

Só quando a UI e a ingestão não cobrem o caso. **Cuidado:** um `INSERT` manual
em `content.chunks`/`qa_entries` **não gera embedding** — a linha fica
inrecuperável até você rodar a ingestão (que re-embeda pelo `content_hash`) ou
preencher `embedding` manualmente. Prefira sempre `./deploy/init-database.sh`.

### 3.5 Ordem segura e cadência

1. `alembic upgrade head` (Neon) → 2. `ingest` (Neon) → 3. redeploy backend
**se** houve mudança de código/prompt → 4. redeploy frontend **se** houve
mudança de UI (`./deploy/deploy-frontend.sh`) → 5. validar com geração real →
6. limpar conversas de teste.

- **Agrupe** mudanças e faça deploy no fim de uma fase de refino — não redeploy
  reativo a cada correção.
- **Reporte o tamanho da imagem** após um deploy de backend (referência atual
  ≈ 89,4 MB).
- `smoke_ingestion_changed.py` **nunca** deve ser rodado contra o Neon de
  produção (reverteria os embeddings para hash de teste).

---

## 4. Referência rápida — endpoints de CRUD do conhecimento

Base: `/api/v1/operator/knowledge` — todos exigem `Authorization: Bearer
<token de operador>`.

| Recurso | Métodos |
|---|---|
| `/qa`, `/qa/{id}` | `GET` (lista, `?include_inactive=`), `POST`, `GET`, `PATCH`, `DELETE` (soft) |
| `/clinical-documents`, `/clinical-documents/{id}` | `GET`, `POST`, `GET`, `PATCH`, `DELETE` (soft) |
| `/clinical-documents/{id}/chunks`, `/…/chunks/{chunk_id}` | `GET`, `POST`, `PATCH`, `DELETE` (soft) — **sem UI** |
| `/categories`, `/categories/{slug}/autonomy` | `GET`, `POST`, `POST` (liga autonomia N3/N4) |
| `/dynamic-tables`, `/dynamic-tables/{t}/columns` | `GET` (allowlist + introspecção) |
| `/autonomy-settings` | `GET`, `POST` (janela, interruptores, idle) |

Ingestão em lote: `python -m customer_care.knowledge.ingest
[--corpus-root PATH] [--deterministic-test-embeddings]`.
