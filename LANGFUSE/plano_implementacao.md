# Plano de implementação — Langfuse Cloud, foco em N5

Criado em 2026-09-10. Substitui `plano_implementacao_local.md` (self-hosted,
3 fases). Autoridade: `revisao_claude_code.md`. Contratos técnicos
reaproveitáveis: `detalhamento_execucao.md` §3 e §5.

## 1. Decisão e premissas

- **Langfuse Cloud**, free tier. Sem serviços locais — nada de ClickHouse,
  Redis ou MinIO. Motivo em `revisao_claude_code.md` §1 (limitação de
  máquina; o argumento de custo/trabalho estava invertido).
- Desenvolvimento no checkout atual (`refino-rag`), Compose da aplicação
  como está. A observabilidade **não adiciona serviço** ao
  `docker-compose.yml`.
- **N5 é o fluxo prioritário** — único caminho onde uma resposta ruim do
  LLM chega ao cliente sem revisão (Amendment 1.3.0). Cobrir resposta
  reaproveitada, guided booking e fallback livre.
- Dados sintéticos (`simulated: true`). Capturar mensagens, prompts,
  respostas e evidências. Fora da serialização: credenciais, tokens,
  objetos de sessão HTTP/SQL, raciocínio interno.
- **Fail-open**: Langfuse indisponível, flag desligada ou erro do SDK não
  pode afetar atendimento. Export em lote, sem chamada de rede dentro de
  transação de atendimento, flush com teto no encerramento.
- **Coleta prospectiva**: começa com novas execuções. Não reconstruir
  histórico nem apagar conversas atuais.
- O PostgreSQL continua a fonte de verdade das métricas de negócio
  (`docs/metrics/v3_queries.sql`). Langfuse é a interface de diagnóstico;
  duplicação é aceita.
- Objetivo: **localizar e corrigir os defeitos que fazem a plataforma
  responder mal.** Instalar a ferramenta não melhora resposta por si.

## 2. O fluxo N5 a observar

N5 não é só `generate_ungoverned_reply()`. O sistema primeiro produz uma
geração pelo fluxo normal (`generate_draft()`, `ai/router.py:263`) e depois
`maybe_open_autonomous_window()` (`ai/router.py:749`) decide o envio.

| Caminho | Comportamento | O que registrar |
|---|---|---|
| Reaproveitar `ANSWER` | Geração fundamentada passa e é entregue **verbatim** (fix D-043) | Geração inicial, evidências, chamadas, decisão de reaproveitamento |
| Guided booking | Trigger de GB elegível (`_N5_ELIGIBLE_GB_TRIGGERS`) entregue pelo N5 | Ofertas/seleção, parser ordinal vs embedding, template |
| Fallback livre | `status != "ANSWER"` **ou** atalho clínico fraco (`< _AUTONOMOUS_CLINICAL_MIN_SCORE = 0.40`) → `generate_ungoverned_reply()` | Motivo do fallback, tentativa inicial, nova geração, prompt N5, consumo das duas etapas |

O ramo governado (N3/N4) é avaliado **antes** do N5. Registrar o mecanismo
efetivo (`ungoverned_n5` / `governed_autonomy`) — não classificar tudo
como N5 porque o switch está ligado.

A mensagem é criada **depois**, por `resolve_elapsed_autonomous_sends()`
(`autonomy/service.py`), numa requisição posterior (poll do cliente, do
operador, ou `_drive_unclaimed_autonomy()`). Registrar só a geração perde
o tempo de espera e a confirmação de envio.

Referências: `ai/router.py`, `ai/providers.py`, `rag/service.py`,
`autonomy/service.py`, `anonymous_access/router.py`.

## 3. Ambiente — Langfuse Cloud

| Item | Definição |
|---|---|
| Projeto | Um projeto no Langfuse Cloud; `environment` = `local-n5` (dev), `local-test` (suíte) |
| Credenciais | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` no `.env` local; `LANGFUSE_HOST` aceito como alias do plano anterior; documentar no `.env.example` sem valores |
| Flag | `LANGFUSE_TRACING_ENABLED` — `false` na config versionada, `true` no `.env` local que usa a integração; adaptador **inerte** quando `false` |
| Endpoint | `LANGFUSE_BASE_URL` ou `LANGFUSE_HOST` explícito (região Cloud); ambos devem concordar se preenchidos; sem fallback para outro destino |
| SDK | Versão fixada em `app/requirements.txt` **antes** de escrever o adaptador (o pacote antigo assumia "v4"; confirmar o corrente) |
| Serviços | Nenhum. `docker-compose.yml` não muda |

**O que sai do processo para o Cloud:** texto de mensagens, prompts
renderizados, respostas do modelo, evidências recuperadas, parâmetros e
decisões — tudo de conversa sintética. **Nunca:** `OPENAI_API_KEY`,
`*_SECRET`, `*_PEPPER`, token anônimo, objeto `Session` SQLAlchemy,
request FastAPI, reasoning além de metadado de consumo.

## 4. Fase 0 — diagnóstico mínimo

**Resultado esperado:** abrir uma conversa N5 ruim e dizer, com
evidência, qual etapa a causou — recuperação, construção de contexto,
seleção de caminho, geração ou envio.

### 4.1 Baseline de graça (dia 1, sem instrumentar nada)

```sql
SELECT provider, status, count(*)
FROM customer_service.ai_generations
WHERE created_at > now() - interval '30 days'
GROUP BY provider, status
ORDER BY count(*) DESC;
```

Dá a distribuição crua de caminhos (`clinical-parent-document`,
`dynamic-pattern-resolver`, `guided-booking`, `ungoverned-n5`,
`clinical-deflection-rerank`, `openai`, `unavailable`). Primeira leitura
de "por onde as respostas estão saindo".

### 4.2 Instrumentar 3 pontos

| Ponto | Código | Capturar |
|---|---|---|
| Recuperação | `rag/service.py::retrieve()` | a **query exata embedada** (não só IDs), evidências ordenadas com score/tipo/tamanho, rank do documento certo. `retrieve()` mistura Q&A e clínico por distância, dedupa pais, corta em `top_k=8`, `score = 1.0 - distance` |
| Chamadas ao modelo | `ai/providers.py` — `generate`, `generate_ungoverned`, `rerank_clinical`, `extract_date_intent`; `knowledge/embeddings.py::embed` | mensagens enviadas, resposta, modelo, uso (tokens); embedding capturado **explícito**, sem duplicar o hook automático presente no SDK 4.15.1 |
| Decisão N5 | `ai/router.py::maybe_open_autonomous_window()` | qual dos ~5 ramos disparou; `n5_path`, `fallback_reason`, `mechanism`; distinguir "entregou ANSWER verbatim" de "gerou fallback fresco" |

Correlação: `session_id = conversation_id`, `trace_id =
triggering_message_id` sem hífen (`detalhamento_execucao.md` §3.1). O
provider `deterministic-test` fica **100% sem instrumentação** (gate em
`ai_provider != "deterministic-test"` **e** na flag) — `pytest` não muda.

Registrar preço de `gpt-5-mini` e `text-embedding-3-small` no Langfuse
(com fonte datada), senão o custo vem vazio.

### 4.3 Ler 20–30 conversas N5 reais

Sessão pareada. Para cada conversa ruim: qual caminho, o que a
recuperação trouxe e em que rank, o que o modelo recebeu, o que foi
enviado. Preencher a ficha de caso no `caderno_de_evolucao.md`.

### 4.4 Saída da Fase 0

Os **3 modos de falha mais frequentes, com denominador**. Sem isso não se
decide o resto. Taxonomia em `playbook_diagnostico.md`.

### 4.5 Aceite da Fase 0

- Conversa N5 sem operador: cliente recebe resposta; trace mostra
  acionamento pelo cliente, caminho e mensagem confirmada.
- Três caminhos N5 demonstrados, um trace cada.
- Langfuse parado / flag `false`: atendimento e `pytest` intactos.
- `smoke_*` e gates de backend/frontend existentes passam.
- Caderno com os 3 modos de falha e denominador.

## 5. O que a Fase 0 decide

| Se o diagnóstico apontar… | O próximo passo é… |
|---|---|
| **Recuperação** (miss / mis-rank em termo exato ou vocabulário) | Ajuste in-stack primeiro (`retrieve()`: embedar só a última mensagem em vez do blob; hybrid `tsvector`; rerank). **Depois** o `laboratorio_recuperacao.md` (RAGFlow/ES), com spec própria. Dataset ponderado por `Hit@k`. |
| **Construção de contexto** (info de turno anterior não chega ao modelo) | Corrigir o payload de `retrieve()` / `build_llm_history` — não é prompt. |
| **Seleção de caminho** (`full_parent_draft` vs LLM vs dynamic escolhe errado) | Revisar a orquestração em `generate_draft()`. |
| **Prompt N5 fraco** (fallback livre pouco útil) | Fase de gestão de prompts (`detalhamento_execucao.md` §7). |
| **Conteúdo errado/ausente** | Curadoria + reingestão (`DOCS_PESSOAIS/PROCESSO_RAG.md`). |

Só depois disso o peso e a ordem das fases seguintes fazem sentido
definir.

## 6. Fases seguintes (provisório — reavaliar após a Fase 0)

Material aproveitável do pacote do Codex, hoje **provisório**:

- **Contratos de observação completos** — `detalhamento_execucao.md` §3
  (identidade, nomes, payloads, scores, dedup, fronteiras de transação).
  Sólido; ajustar só os endpoints para Cloud.
- **Avaliação** — §6 (dataset, rubrica 0/1/2, juiz LLM + calibração,
  runner). Reusar `app/customer_care/evaluation/` (casos V3-5), não criar
  paralelo. Split do dataset definido pela Fase 0.
- **Gestão de prompts** — §7 (catálogo `cc_n5_free` / `cc_rag_answer` /
  `cc_clinical_rerank` / `cc_date_intent`, TTL, fallback local,
  publicar → comparar → ativar → reverter).
- **DB de teste isolada** — §5 (`oncology_langfuse_test`). Rigor
  obrigatório: esta dev DB já reverteu embeddings e tem
  `n5_kill_switch_enabled = true`.

## 7. Ordem de implementação da Fase 0

| Passo | Trabalho | Dependência |
|---|---|---|
| LF-0 | `spec.md` leve + `analysis.md` (fluxo de dados pro Cloud; reconciliar escopo com 006–012) | — |
| LF-1 | Baseline SQL primeiro; validar projeto/chaves Cloud, `.env.example`, flag, SDK fixado; comando de prova isolado (1 trace, 1 chamada com custo, 1 score), sem instrumentar o atendimento; parar para revisão | LF-0 aprovado em 2026-09-10 |
| LF-2 | Adaptador inerte-quando-off; correlação de turno; ciclo de vida por processo | LF-1 |
| LF-3 | Instrumentar `retrieve()` + chamadas de provider/embeddings | LF-2 |
| LF-4 | Instrumentar a decisão em `maybe_open_autonomous_window()` + envio confirmado | LF-3 |
| LF-5 | Gates (backend / frontend / smoke) com flag on/off; aceite §4.5 | LF-4 |
| LF-6 | Sessão pareada: ler 20–30 traces, preencher os 3 modos de falha | LF-5 |

Checkpoint em 2026-09-10: prova LF-1 persistida no Cloud; ver
[analysis.md §8](../specs/013-local-langfuse-observability/analysis.md).
Revisar os hooks globais do SDK, captura de embeddings e identificador
público automático descritos na spec antes de LF-2.

## 8. Entregáveis

| Área | Arquivos |
|---|---|
| SDD | `specs/013-local-langfuse-observability/spec.md` + `analysis.md` (leves) |
| Config | `.env.example`, `app/requirements.txt` (SDK fixado) |
| Adaptador | módulo em `shared` / `infrastructure`, settings, `bootstrap.py` |
| Instrumentação | `ai/providers.py`, `ai/router.py`, `rag/service.py`, `knowledge/embeddings.py` |
| Validação | testes do adaptador, smoke N5 sem operador, regressão com flag `false` |
| Aprendizado | `playbook_diagnostico.md`, `caderno_de_evolucao.md` |

Sem migração de schema. Necessidade demonstrada passa por spec → analysis
antes.
