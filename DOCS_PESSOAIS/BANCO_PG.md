# BANCO_PG.md — Referência completa do banco PostgreSQL

Todas as tabelas e colunas **realmente presentes** no banco (local Docker
Compose e Neon em produção), reconstruídas a partir das **28 migrações
Alembic** (`app/alembic/versions/`), que são a única fonte de verdade do
schema, cruzadas com os modelos ORM (`app/customer_care/infrastructure/models.py`,
`app/customer_care/scheduling/models.py`).

Conferido em 2026-08-21. Migração-cabeça: `20260821_0005`.

---

## 0. Visão geral

- **SGBD:** PostgreSQL 17 (imagem `pgvector/pgvector:pg17` local; Neon 17 em
  produção).
- **Extensões:** `vector` (pgvector) e `pgcrypto` (`gen_random_uuid()`).
- **Schemas:** `content`, `customer_service`, `scheduling` (+ `public` só com
  `alembic_version`).
- **Tipo enum:** `scheduling.slot_status` = `('available','held','booked','blocked')`.
- **Função:** `scheduling.next_business_day(date) → date` (pula domingos e
  feriados não úteis).
- **Chaves:** UUID `gen_random_uuid()` na maioria; `text` em `content.*`
  (ids legíveis como `QA-011`, `MAMA-…-001`, `MAMA-…-001-C03`).
- **Timestamps:** `timestamptz`, default `now()`.
- Toda coluna `*_at` de evento é UTC; horários de agenda são convertidos para
  `America/Sao_Paulo` na aplicação.

> ⚠️ **`db/init/001_schema.sql` / `002_seed_and_schedule.sql` são legado e NÃO
> são aplicados** (não há mount de `initdb.d` nem script que os rode — ver o
> docstring de `20260819_0001`). Por isso os schemas `identity`, `billing`,
> `governance` e as tabelas `scheduling.slot_offers`, `scheduling.appointments`,
> `scheduling.appointment_events`, `scheduling.payments`,
> `content.document_sources` **não existem** no banco real. O que existe é só o
> descrito abaixo.

---

## 1. Schema `content` — base de conhecimento (RAG)

### 1.1 `content.documents` — documento clínico **pai**

Corpo Markdown completo de um tema clínico. **Não tem embedding** — só os filhos
(`content.chunks`) são vetorizados; o pai é expandido como contexto de
*grounding* quando um filho seu é recuperado.

| Coluna | Tipo | Notas |
|---|---|---|
| `document_id` | `text` PK | Ex.: `MAMA-CIRURGIA_CONSERVADORA-001`. Vindo do catálogo/front matter (lote) ou `doc-<hex12>` (CRUD). |
| `title` | `text` NOT NULL | |
| `document_type` | `text` NOT NULL | Default `'orientacao_clinica'`. |
| `cancer_type` | `text` NULL | **FK → `content.categories(slug)`**. É a "categoria" clínica (sítio). |
| `care_phase` | `text` NULL | Ex.: `cirurgia`, `quimioterapia`. |
| `procedure_slug` | `text` NULL | |
| `audience` | `text[]` NOT NULL | Default `{paciente,familiar}`. |
| `language` | `text` NOT NULL | Default `'pt-BR'`. |
| `responsible_physician` | `text` NOT NULL | Default `'Não informado'`. |
| `version` | `text` NOT NULL | |
| `status` | `text` NOT NULL | Default `'published'` (`draft`/`published`/`retired` por convenção). |
| `created_at` | `date` NOT NULL | Default `CURRENT_DATE`. |
| `last_reviewed_at` | `date` NOT NULL | Default `CURRENT_DATE`. |
| `next_review_at` | `date` NOT NULL | Default `CURRENT_DATE`. |
| `patient_markdown_path` | `text` NOT NULL | Caminho do `.md` fonte, ou `crud:<id>` quando criado pela UI. |
| `dynamic_data_required` | `boolean` NOT NULL | Default `false`. |
| `dynamic_resolver` | `text` NULL | (não usado em documentos hoje). |
| `metadata` | `jsonb` NOT NULL | Default `{}`. Mapeado no ORM como `metadata_json`. |
| `content_markdown` | `text` NULL | **Corpo inteiro do pai** — é o que vira o rascunho quando é a evidência nº 1. |
| `content_hash` | `text` NULL | SHA-256 do corpo; controla reingestão. |
| `customer_citation_allowed` | `boolean` NOT NULL | Default **`true`** — fonte clínica pode ser citada ao cliente. |
| `is_active` | `boolean` NOT NULL | Default `true`. Soft delete. |
| `updated_at` | `timestamptz` NOT NULL | Default `now()`. |

### 1.2 `content.chunks` — seção **filha** de um documento clínico

Unidade **vetorizada** do conhecimento clínico. Uma linha por seção `##` (as 10
primeiras do documento).

| Coluna | Tipo | Notas |
|---|---|---|
| `chunk_id` | `text` PK | `"<document_id>-C01"` … `"-C10"`. |
| `parent_document_id` | `text` NOT NULL | **FK → `content.documents(document_id)` ON DELETE CASCADE**. |
| `ordinal` | `integer` NOT NULL | `CHECK (ordinal > 0)`. `UNIQUE(parent_document_id, ordinal)`. |
| `heading` | `text` NOT NULL | Cabeçalho da seção. |
| `content_markdown` | `text` NOT NULL | Texto da seção. |
| `retrieval_intents` | `text[]` NOT NULL | Default `{}`. |
| `symptoms` | `text[]` NOT NULL | Default `{}`. |
| `urgency` | `text` NOT NULL | Default `'educativo'`; `'contato_no_mesmo_dia'` / `'emergencia'` derivados do heading. |
| `metadata` | `jsonb` NOT NULL | Default `{}`. ORM: `metadata_json`. Inclui `section`. |
| `embedding` | `vector(1536)` NULL | Embedding de `heading\nconteúdo`. Índice **HNSW** `chunks_embedding_hnsw_idx` (`vector_cosine_ops`). |
| `embedding_provider` | `text` NULL | `openai` / `deterministic-test`. |
| `embedding_model` | `text` NULL | `text-embedding-3-small` / `sha256-test-v1`. |
| `embedding_dimension` | `integer` NULL | `1536`. |
| `embedded_at` | `timestamptz` NULL | |
| `content_hash` | `text` NULL | Controla re-embedding. |
| `is_active` | `boolean` NOT NULL | Default `true`. Soft delete; `retrieve()` filtra. |
| `created_at` / `updated_at` | `timestamptz` NOT NULL | Default `now()`. |

### 1.3 `content.qa_entries` — Q&A administrativo **plano**

Registro achatado (sem pai/filho). **É** a unidade recuperável; vetorizado por
`pergunta\nresposta`.

| Coluna | Tipo | Notas |
|---|---|---|
| `qa_id` | `text` PK | `QA-011` (lote) ou `qa-<hex12>` (CRUD). |
| `category` | `text` NOT NULL | **FK → `content.categories(slug)`**. |
| `question` | `text` NOT NULL | |
| `answer_markdown` | `text` NOT NULL | Conteúdo de *grounding*; em Q&A dinâmico contém `{{variáveis}}` / serve de fallback. |
| `retrieval_intents` | `text[]` NOT NULL | Default `{}`. |
| `dynamic_data_required` | `boolean` NOT NULL | Default `false`. `true` = não passa por LLM, resolve determinístico. |
| `dynamic_resolver` | `text` NULL | `appointment_availability` / `price_lookup` (allowlist `NAMED_RESOLVERS`) ou `NULL`. **Só setável via ingestão**, não pela UI. |
| `metadata` | `jsonb` NOT NULL | Default `{}`. ORM: `metadata_json`. |
| `embedding` | `vector(1536)` NULL | Índice **HNSW** `qa_embedding_hnsw_idx`. |
| `embedding_provider` / `embedding_model` / `embedding_dimension` / `embedded_at` | | Metadados de embedding (iguais aos de `chunks`). |
| `content_hash` | `text` NULL | Controla re-embedding. |
| `customer_citation_allowed` | `boolean` NOT NULL | Default **`false`** — fonte administrativa não vira citação ao cliente. |
| `is_active` | `boolean` NOT NULL | Default `true`. Soft delete. |
| `created_at` / `updated_at` | `timestamptz` NOT NULL | Default `now()`. |

### 1.4 `content.categories` — registro único de categorias (V3-8)

Compartilhado por `qa_entries.category` (temas administrativos) e
`documents.cancer_type` (sítios clínicos).

| Coluna | Tipo | Notas |
|---|---|---|
| `slug` | `text` PK | Ex.: `instituicao`, `agenda`, `preco`, `mama`, `nutricao_oncologica`. |
| `label` | `text` NOT NULL | Rótulo exibível. |
| `is_active` | `boolean` NOT NULL | Default `true`. |
| `created_at` | `timestamptz` NOT NULL | Default `now()`. |
| `autonomy_enabled` | `boolean` NOT NULL | Default **`false`** — política de autonomia governada (N3/N4) por categoria (migração `20260820_0005`). |

### 1.5 `content.qa_dynamic_bindings` — vínculo dinâmico genérico (V2-6)

Liga uma Q&A a uma tabela/filtro/colunas para substituir `{{variáveis}}`. Só o
mecanismo de demonstração usa isso (allowlist = só `knowledge_dynamic_fixture`).

| Coluna | Tipo | Notas |
|---|---|---|
| `qa_id` | `text` PK | **FK → `content.qa_entries(qa_id)`**. |
| `source_table` | `text` NOT NULL | Precisa estar na `ALLOWLISTED_TABLES` (`knowledge/dynamic_binding.py`). |
| `filter` | `jsonb` NOT NULL | Default `{}`. Pares coluna→valor (igualdade). |
| `output_columns` | `jsonb` NOT NULL | Lista `{column, variable_name}`. |
| `row_limit` | `integer` NOT NULL | Default `4`, `CHECK (row_limit > 0)`. |
| `created_at` / `updated_at` | `timestamptz` NOT NULL | Default `now()`. |

### 1.6 `content.knowledge_dynamic_fixture` — *fixture* de demonstração (V2-6)

Prova o mecanismo dinâmico contra uma tabela real. **Nenhuma Q&A de produção
aponta para ela.**

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | `gen_random_uuid()`. |
| `category` | `text` NOT NULL | |
| `status` | `text` NOT NULL | |
| `label` | `text` NOT NULL | |
| `ordinal` | `integer` NOT NULL | Ordenação estável. |

### 1.7 `content.evaluation_cases` — casos de avaliação (V3-5)

Armazenamento apenas — **sem** re-execução automática e **sem** FK para
conversas/gerações (isolamento estrutural das métricas).

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | |
| `category_slug` | `text` NULL | FK → `content.categories(slug)`. |
| `question` | `text` NOT NULL | |
| `expected_status` | `text` NOT NULL | `CHECK IN ('ANSWER','ABSTAIN')`. |
| `expected_evidence_ids` | `jsonb` NULL | |
| `actual_status` | `text` NULL | `CHECK IN ('ANSWER','ABSTAIN')`. Preenchido só por revisão manual. |
| `actual_notes` | `text` NULL | |
| `last_reviewed_at` | `timestamptz` NULL | |
| `created_by_operator_id` | `uuid` NOT NULL | FK → `customer_service.operator_users(id)`. |
| `created_at` / `updated_at` | `timestamptz` NOT NULL | Default `now()`. |

---

## 2. Schema `customer_service` — atendimento, IA e auditoria

### 2.1 `customer_service.operator_users` — operadores

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | `gen_random_uuid()`. |
| `email` | `text` NOT NULL **UNIQUE** | |
| `password_hash` | `text` NOT NULL | **Argon2**. Só criado por `seed_operator`. |
| `display_name` | `text` NOT NULL | |
| `is_active` | `boolean` NOT NULL | Default `true`. |
| `created_at` / `updated_at` | `timestamptz` NOT NULL | Default `now()`. |

### 2.2 `customer_service.conversations` — conversas

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | |
| `channel` | `text` NOT NULL | Default `'WEB'`, `CHECK (channel='WEB')`. |
| `status` | `text` NOT NULL | Default `'WAITING'`, `CHECK IN ('WAITING','ACTIVE','CLOSED')`. |
| `anonymous_token_digest` | `text` NOT NULL **UNIQUE** | Digest **HMAC-SHA256** do token do cliente (nunca o valor bruto). |
| `initial_mode` | `text` NOT NULL | `CHECK IN ('N1','N2')`. |
| `effective_mode` | `text` NOT NULL | `CHECK IN ('N1','N2')`. Cai para `N1` em "Assumir controle". |
| `taken_over_at` | `timestamptz` NULL | Marca o "Assumir controle". |
| `created_at` | `timestamptz` NOT NULL | Default `now()`. |
| `closed_at` | `timestamptz` NULL | |
| `last_message_at` | `timestamptz` NULL | |
| `last_customer_activity_at` | `timestamptz` NULL | Base do debounce do rascunho automático (`20260814_0001`). |
| `last_customer_typing_at` | `timestamptz` NULL | Heartbeat de digitação. |
| `auto_draft_covers_through_message_id` | `uuid` NULL | FK → `messages(id)`. Última mensagem já coberta por um rascunho automático. |
| `booking_script_step` | `text` NULL | `CHECK NULL OR IN ('AWAITING_CPF','AWAITING_PAYMENT')` (`20260819_0003`). Marcador de posição do script AA-10 — **nunca** guarda CPF/pagamento. |
| `guided_booking_pending_text` | `text` NULL | Resultado **já interpretado** de uma resposta de CPF/pagamento do fluxo guiado GB (nunca o valor bruto); consumido/limpo no próximo rascunho (`20260819_0007`). |
| `guided_booking_pending_trigger` | `text` NULL | `trigger` a aplicar ao consumir o campo acima. |
| `guided_booking_selected_offer_id` | `uuid` NULL | FK → `appointment_offer_presentations(id)`. Oferta que o GB identificou, carregada até a confirmação de pagamento (`20260820_0002`). |

Índice: `conversations_queue_idx (status, last_message_at, created_at)`.

### 2.3 `customer_service.conversation_assignments` — atribuição operador↔conversa

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | |
| `conversation_id` | `uuid` NOT NULL | FK → `conversations(id)`. |
| `operator_id` | `uuid` NOT NULL | FK → `operator_users(id)`. |
| `claimed_at` | `timestamptz` NOT NULL | Default `now()`. |
| `released_at` | `timestamptz` NULL | `NULL` = atribuição ativa. |
| `release_reason` | `text` NULL | |

Índices: `one_active_assignment_per_conversation` UNIQUE `(conversation_id) WHERE
released_at IS NULL` (1 operador ativo por conversa); `active_assignments_by_operator`
`(operator_id) WHERE released_at IS NULL` (apoia o limite de 4 ativas).

### 2.4 `customer_service.messages` — mensagens

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | |
| `conversation_id` | `uuid` NOT NULL | FK → `conversations(id)`. |
| `author_type` | `text` NOT NULL | `CHECK IN ('CUSTOMER','OPERATOR')`. |
| `operator_id` | `uuid` NULL | FK → `operator_users(id)`. |
| `body` | `text` NOT NULL | `CHECK (length(body) > 0)`. |
| `source_generation_id` | `uuid` NULL | FK → `ai_generations(id)`. Proveniência quando a mensagem veio de um rascunho. |
| `created_at` | `timestamptz` NOT NULL | Default `now()`. |
| `autonomous_source` | `text` NULL | `CHECK NULL OR IN ('booking_script','governed_autonomy','ungoverned_n5')` — contenção estrutural das 3 exceções de autonomia (`20260819_0003`, ampliado em `20260820_0010`, `20260821_0004`). |

`messages_check` (evoluído até `20260821_0005`):
`(CUSTOMER e operator_id NULL) OR (OPERATOR e operator_id NOT NULL) OR (OPERATOR
e operator_id NULL e autonomous_source IN ('booking_script','governed_autonomy','ungoverned_n5'))`
— uma mensagem de operador só pode ter `operator_id` nulo se for um dos três
envios autônomos autorizados.

### 2.5 `customer_service.retrieval_runs` — rodada de recuperação (RAG)

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | |
| `conversation_id` | `uuid` NULL | FK → `conversations(id)`. |
| `triggering_message_id` | `uuid` NULL | FK → `messages(id)`. |
| `operator_id` | `uuid` NULL | FK → `operator_users(id)`. Nullable desde `20260820_0009` (gatilho autônomo sem operador). |
| `purpose` | `text` NOT NULL | `CHECK IN ('N2_DRAFT','N1_MANUAL_SEARCH','N2_MANUAL_SEARCH')`. |
| `query_text` | `text` NOT NULL | Consulta embedada. |
| `embedding_model` | `text` NOT NULL | Modelo usado. |
| `top_k` | `integer` NOT NULL | `CHECK (top_k > 0)`. Normalmente 8. |
| `status` | `text` NOT NULL | `CHECK IN ('STARTED','COMPLETED','FAILED')`. |
| `duration_ms` | `integer` NULL | |
| `error_code` | `text` NULL | |
| `created_at` | `timestamptz` NOT NULL | Default `now()`. |
| `completed_at` | `timestamptz` NULL | |

### 2.6 `customer_service.retrieval_hits` — acerto de recuperação

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | |
| `retrieval_run_id` | `uuid` NOT NULL | FK → `retrieval_runs(id)`. |
| `matched_kind` | `text` NOT NULL | `CHECK IN ('ADMIN_QA','CLINICAL_CHILD')`. |
| `matched_qa_id` | `text` NULL | FK → `content.qa_entries(qa_id)`. |
| `matched_chunk_id` | `text` NULL | FK → `content.chunks(chunk_id)`. |
| `expanded_parent_document_id` | `text` NULL | FK → `content.documents(document_id)`. |
| `rank` | `integer` NOT NULL | `CHECK (rank > 0)`. `UNIQUE(retrieval_run_id, rank)`. |
| `score` | `double precision` NOT NULL | `1 - distância_cosseno`. |
| `created_at` | `timestamptz` NOT NULL | Default `now()`. |

`CHECK`: `ADMIN_QA` ⇒ só `matched_qa_id`; `CLINICAL_CHILD` ⇒ `matched_chunk_id`
+ `expanded_parent_document_id`, sem `matched_qa_id`.

### 2.7 `customer_service.ai_generations` — rascunho de IA (≠ mensagem)

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | |
| `conversation_id` | `uuid` NOT NULL | FK → `conversations(id)`. |
| `triggering_message_id` | `uuid` NULL | FK → `messages(id)`. Nullable desde `20260814_0001`. |
| `retrieval_run_id` | `uuid` NOT NULL | FK → `retrieval_runs(id)`. |
| `prior_generation_id` | `uuid` NULL | FK → `ai_generations(id)`. Encadeia regenerações / N5. |
| `operator_id` | `uuid` NULL | FK → `operator_users(id)`. Nullable desde `20260820_0008` (gatilho autônomo sem operador). |
| `status` | `text` NOT NULL | `CHECK IN ('ANSWER','ABSTAIN','FAILED')`. |
| `draft_text` | `text` NOT NULL | Só o texto ao cliente. |
| `abstention_reason` | `text` NULL | `INSUFFICIENT_EVIDENCE`, `DYNAMIC_DATA_UNAVAILABLE`, `PROVIDER_FAILURE`, … |
| `provider` | `text` NOT NULL | `openai`, `clinical-parent-document`, `dynamic-pattern-resolver`, `guided-booking`, `clinical-deflection-rerank`, `ungoverned-n5`, `unavailable`. |
| `model` | `text` NOT NULL | Ex.: `gpt-5-mini` ou `not-applicable`. |
| `prompt_version` | `text` NOT NULL | `nome:sha256[:12]` do prompt (ou `not-applicable`). |
| `input_tokens` / `output_tokens` | `integer` NULL | Do `usage` do provedor. |
| `duration_ms` | `integer` NULL | |
| `created_at` | `timestamptz` NOT NULL | Default `now()`. |
| `trigger` | `text` NOT NULL | `CHECK IN ('AUTOMATIC','MANUAL_DRAFT','MANUAL_EVIDENCE','GUIDED_SLOT_SELECTION','GUIDED_CONFIRMATION','GUIDED_CPF_CONFIRMED','GUIDED_BOOKING_COMPLETE','GUIDED_SLOT_RESELECTION')` (ampliado em `20260814_0001` → `…_0006/0008/0009`). `GUIDED_CONFIRMATION` está aposentado (sem código que o produza). |
| `manual_search_text` | `text` NULL | Texto de busca manual, se houve. |
| `dynamic_pattern_used` | `boolean` NOT NULL | Default `false`. |
| `instruction_text` | `text` NULL | Instrução do operador ("regenerar com instrução"). |
| `category_slug` | `text` NULL | FK → `content.categories(slug)`. Derivado da evidência `use_order=1`. |
| `marked_incorrect_at` | `timestamptz` NULL | Ação "Marcar como incorreto". |
| `marked_incorrect_by_operator_id` | `uuid` NULL | FK → `operator_users(id)`. |
| `escalated_at` | `timestamptz` NULL | Ação "Sinalizar lacuna de conteúdo". |
| `escalated_by_operator_id` | `uuid` NULL | FK → `operator_users(id)`. |

### 2.8 `customer_service.ai_generation_sources` — evidências usadas por geração

| Coluna | Tipo | Notas |
|---|---|---|
| `ai_generation_id` | `uuid` NOT NULL | FK → `ai_generations(id)`. |
| `retrieval_hit_id` | `uuid` NOT NULL | FK → `retrieval_hits(id)`. |
| `use_order` | `integer` NOT NULL | Ordem de uso. |
| — | | PK `(ai_generation_id, retrieval_hit_id)`; `UNIQUE(ai_generation_id, use_order)`. |

### 2.9 `customer_service.message_selections` — contexto escolhido pelo operador

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | |
| `ai_generation_id` | `uuid` NOT NULL | FK → `ai_generations(id)`. |
| `message_id` | `uuid` NOT NULL | FK → `messages(id)`. |
| `created_at` | `timestamptz` NOT NULL | Default `now()`. |
| — | | `UNIQUE(ai_generation_id, message_id)`. |

### 2.10 `customer_service.message_citations` — citações anexadas a uma mensagem enviada

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | |
| `message_id` | `uuid` NOT NULL | FK → `messages(id)`. |
| `knowledge_document_id` | `text` NOT NULL | FK → `content.documents(document_id)`. |
| `knowledge_chunk_id` | `text` NULL | FK → `content.chunks(chunk_id)`. |
| `display_title` | `text` NOT NULL | Título exibido ao cliente. |
| `display_section` | `text` NULL | Seção exibida. |
| `display_url` | `text` NULL | |
| `created_at` | `timestamptz` NOT NULL | Default `now()`. |

### 2.11 `customer_service.audit_events` — trilha de auditoria (append-only)

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | |
| `event_type` | `text` NOT NULL | Ex.: `rag.search_completed`, `ai.draft_generated`, `message.operator_sent`, `autonomy.message_sent`, `knowledge.qa_created`. |
| `occurred_at` | `timestamptz` NOT NULL | Default `now()`. |
| `actor_type` | `text` NOT NULL | `CHECK IN ('CUSTOMER','OPERATOR','SYSTEM')`. |
| `actor_id` | `uuid` NULL | Sem FK (ator pode ser sistema). |
| `conversation_id` | `uuid` NULL | FK → `conversations(id)`. |
| `correlation_id` | `text` NULL | Id de request, para correlação. |
| `payload_json` | `jsonb` NOT NULL | Default `{}`. Nunca contém raciocínio interno; textos sensíveis vão como hash. |

**Trigger `audit_events_append_only`**: `BEFORE UPDATE OR DELETE` → `RAISE
EXCEPTION 'audit_events are append-only'`. Imutável pela aplicação.

### 2.12 `customer_service.conversation_satisfaction_responses` — pesquisa pós-encerramento (V3-12)

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | |
| `conversation_id` | `uuid` NOT NULL **UNIQUE** | FK → `conversations(id)`. Uma resposta por conversa. |
| `score` | `smallint` NOT NULL | `CHECK BETWEEN 1 AND 5`. |
| `resolved` | `boolean` NOT NULL | "Sua necessidade foi resolvida?" |
| `category_slug` | `text` NULL | FK → `content.categories(slug)`. |
| `submitted_at` | `timestamptz` NOT NULL | Default `now()`. |

### 2.13 `customer_service.appointment_offer_presentations` — ofertas de horário mostradas (GB-1)

Append-only. Até 4 linhas por geração que resolveu `appointment_availability`.
**Com embedding** — para casar a escolha posterior do cliente.

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | |
| `ai_generation_id` | `uuid` NOT NULL | FK → `ai_generations(id)` **ON DELETE CASCADE**. |
| `slot_id` | `uuid` NOT NULL | FK → `scheduling.schedule_slots(slot_id)` **ON DELETE CASCADE**. |
| `display_order` | `smallint` NOT NULL | `CHECK BETWEEN 1 AND 4`. `UNIQUE(ai_generation_id, display_order)`. |
| `description` | `text` NOT NULL | Linha renderizada da oferta (especialidade — profissional, dia/hora, preço). |
| `embedding` | `vector(1536)` NOT NULL | Embedding da `description`. |
| `created_at` | `timestamptz` NOT NULL | Default `now()`. |

### 2.14 `customer_service.system_settings` — configuração global (linha única)

`id boolean PK DEFAULT true` + `CONSTRAINT system_settings_singleton CHECK (id)`
⇒ **exatamente uma linha** pode existir.

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `boolean` PK | Sempre `true`. |
| `autonomy_window_seconds` | `integer` NOT NULL | Default `30`. Janela de veto (0 = envio imediato). |
| `autonomy_kill_switch_enabled` | `boolean` NOT NULL | Default `false`. **Interruptor geral N3/N4** (Emenda 1.2.0). |
| `n5_kill_switch_enabled` | `boolean` NOT NULL | Default `false`. **Interruptor N5**, independente (Emenda 1.3.0, `20260821_0001`). |
| `automatic_trigger_idle_seconds` | `integer` NOT NULL | Default `8`. Tempo ocioso antes do rascunho automático (`20260821_0001`; era constante fixa). |
| `updated_at` | `timestamptz` NOT NULL | Default `now()`. |
| `updated_by_operator_id` | `uuid` NULL | FK → `operator_users(id)`. |

### 2.15 `customer_service.pending_autonomous_sends` — janela de envio autônomo aberta (GA-3)

Uma linha por geração com janela de veto aberta.

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `uuid` PK | |
| `generation_id` | `uuid` NOT NULL | FK → `ai_generations(id)`. |
| `conversation_id` | `uuid` NOT NULL | FK → `conversations(id)`. |
| `category` | `text` NULL | FK → `content.categories(slug)`. Nullable desde `20260821_0002` (linha N5 não tem categoria). |
| `window_seconds` | `integer` NOT NULL | Congelado no insert. |
| `opens_at` | `timestamptz` NOT NULL | Default `now()`. |
| `resolves_at` | `timestamptz` NOT NULL | `opens_at + window_seconds`. |
| `status` | `text` NOT NULL | Default `'PENDING'`. `CHECK IN ('PENDING','SENT','PAUSED','EDITED','TAKEN_OVER')`. |
| `resolved_at` | `timestamptz` NULL | |
| `resolved_by_operator_id` | `uuid` NULL | FK → `operator_users(id)`. |
| `created_at` | `timestamptz` NOT NULL | Default `now()`. |
| `mechanism` | `text` NOT NULL | `CHECK IN ('governed_autonomy','ungoverned_n5')` (`20260821_0003`). Define o `autonomous_source` da mensagem resultante. |

Índices: `…_one_pending_per_generation` UNIQUE `(generation_id) WHERE
status='PENDING'` (guarda contra envio duplo); `…_resolvable` `(resolves_at)
WHERE status='PENDING'`; `…_conversation_id_idx`.

---

## 3. Schema `scheduling` — agenda (sintética, mas "real" no banco)

Criado pela migração `20260819_0001`. Só as tabelas abaixo existem.

### 3.1 `scheduling.units` — unidades de atendimento

| Coluna | Tipo | Notas |
|---|---|---|
| `unit_id` | `uuid` PK | Semente: `1000…0001` "Unidade Central (simulação)". |
| `name` | `text` NOT NULL | |
| `timezone` | `text` NOT NULL | Default `'America/Sao_Paulo'`. |
| `simulated` | `boolean` NOT NULL | Default `true`. |

### 3.2 `scheduling.specialties` — especialidades

**8 linhas semeadas** (`20260819_0001`, `_0002`, `20260820_0004`):
`mastologia-oncologica`, `cirurgia-colorretal`, `segunda-opiniao`,
`oncologia-geral` (generalista/triagem), `psico-oncologia`,
`nutricao-oncologica`, `endocrinologia-oncologica`, `fisioterapia-oncologica`.

| Coluna | Tipo | Notas |
|---|---|---|
| `specialty_id` | `uuid` PK | |
| `slug` | `text` NOT NULL **UNIQUE** | Casado com `SPECIALTY_KEYWORDS` no código. |
| `display_name` | `text` NOT NULL | |
| `description` | `text` NOT NULL | |
| `simulated` | `boolean` NOT NULL | Default `true`. |

### 3.3 `scheduling.professionals` — profissionais (fictícios)

**24 linhas semeadas** (`30000…0001` a `…0024`).

| Coluna | Tipo | Notas |
|---|---|---|
| `professional_id` | `uuid` PK | |
| `display_name` | `text` NOT NULL | Ex.: `Dra. Helena Martins (simulação)`. |
| `registration_display` | `text` NULL | Ex.: `CRM-SP 000001 (simulação)`. |
| `simulated` | `boolean` NOT NULL | Default `true`. |
| `active` | `boolean` NOT NULL | Default `true`. |

### 3.4 `scheduling.professional_specialties` — ponte N:N (preço e duração)

Fonte de preço do resolvedor `price_lookup` e da linha de preço das ofertas.

| Coluna | Tipo | Notas |
|---|---|---|
| `professional_id` | `uuid` NOT NULL | FK → `professionals`. |
| `specialty_id` | `uuid` NOT NULL | FK → `specialties`. |
| `fixed_price_cents` | `integer` NOT NULL | `CHECK (>= 0)`. Ex.: `98000` = R$ 980,00. |
| `appointment_duration_minutes` | `integer` NOT NULL | Default `60`, `CHECK (> 0)`. |
| — | | PK `(professional_id, specialty_id)`. |

### 3.5 `scheduling.holidays` — feriados

Semeados 2026–2027 (nacionais + SP estadual/municipal). Usados por
`next_business_day()`.

| Coluna | Tipo | Notas |
|---|---|---|
| `holiday_id` | `uuid` PK | |
| `holiday_date` | `date` NOT NULL | |
| `name` | `text` NOT NULL | |
| `scope` | `text` NOT NULL | `CHECK IN ('national','state','municipal','institutional')`. |
| `state_code` | `char(2)` NULL | |
| `city_code` | `text` NULL | |
| `unit_id` | `uuid` NULL | FK → `units(unit_id)`. |
| `is_business_day` | `boolean` NOT NULL | Default `false` (se `true`, "feriado" que ainda é dia útil). |
| `simulated` | `boolean` NOT NULL | Default `false`. |
| — | | UNIQUE `(holiday_date, scope, coalesce(state_code,''), coalesce(city_code,''), coalesce(unit_id::text,''))`. |

### 3.6 `scheduling.schedule_slots` — **a agenda** (vagas)

Criadas **só** pelas ações do operador ("Garantir disponibilidade D+1/D+7" e
"Preencher agenda ampla"). Lidas (nunca escritas) pelo resolvedor
`appointment_availability`.

| Coluna | Tipo | Notas |
|---|---|---|
| `slot_id` | `uuid` PK | `gen_random_uuid()`. |
| `unit_id` | `uuid` NOT NULL | FK → `units`. |
| `specialty_id` | `uuid` NOT NULL | FK → `specialties`. |
| `professional_id` | `uuid` NOT NULL | FK → `professionals`. |
| `starts_at` | `timestamptz` NOT NULL | |
| `ends_at` | `timestamptz` NOT NULL | `CHECK (ends_at > starts_at)`. |
| `status` | `scheduling.slot_status` NOT NULL | Enum `available`/`held`/`booked`/`blocked`. Default `'available'`. Na prática hoje permanece `available` (não há reserva real). |
| `simulated` | `boolean` NOT NULL | Default `true`. |
| `created_at` | `timestamptz` NOT NULL | Default `now()`. |
| — | | `UNIQUE (professional_id, starts_at)`. |

### 3.7 `scheduling.appointment_bookings` — marcação concluída (BS-1)

Uma linha por fluxo de marcação concluído. **Nunca alterada após o insert.**
**Não há coluna de CPF nem de pagamento.**

| Coluna | Tipo | Notas |
|---|---|---|
| `booking_id` | `uuid` PK | `gen_random_uuid()`. |
| `conversation_id` | `uuid` NOT NULL | FK → `customer_service.conversations(id)`. |
| `source` | `text` NOT NULL | `CHECK IN ('guided_booking','booking_script')`. |
| `specialty_id` | `uuid` NOT NULL | FK → `specialties`. |
| `professional_id` | `uuid` NULL | FK → `professionals`. **Nullable** — uma marcação via AA-10 não sabe o slot exato ("limite da honestidade"). |
| `unit_id` | `uuid` NULL | FK → `units`. Idem. |
| `slot_starts_at` | `timestamptz` NULL | Idem. Preenchido só quando `source='guided_booking'`. |
| `recorded_at` | `timestamptz` NOT NULL | Default `now()`. |
| — | | Índice `appointment_bookings_conversation_id_idx (conversation_id)`. |

---

## 4. `public.alembic_version`

Tabela padrão do Alembic; uma linha com `version_num` = revisão-cabeça
(`20260821_0005`).

---

## 5. Resumo de relacionamentos (texto)

```
content.categories ─┬─< content.qa_entries        ─< content.qa_dynamic_bindings
                    ├─< content.documents          ─< content.chunks
                    ├─< content.evaluation_cases
                    ├─< customer_service.ai_generations.category_slug
                    ├─< customer_service.pending_autonomous_sends.category
                    └─< customer_service.conversation_satisfaction_responses.category_slug

customer_service.operator_users ─< conversation_assignments >─ conversations
conversations ─< messages ─< message_citations >─ content.documents / content.chunks
conversations ─< retrieval_runs ─< retrieval_hits >─ (qa_entries | chunks + documents)
retrieval_runs ─< ai_generations ─< ai_generation_sources >─ retrieval_hits
ai_generations ─< message_selections >─ messages
ai_generations ─< appointment_offer_presentations >─ scheduling.schedule_slots
ai_generations ─< pending_autonomous_sends >─ conversations
conversations.guided_booking_selected_offer_id ─> appointment_offer_presentations

scheduling.units / specialties / professionals ─< professional_specialties
scheduling.(unit,specialty,professional) ─< schedule_slots
scheduling.specialties ─< appointment_bookings >─ customer_service.conversations
```
