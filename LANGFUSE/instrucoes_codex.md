# Instruções para o Codex — Fase 0 do Langfuse

Data: 2026-09-10. Escrito por Claude Code para o Codex executar. Ponto de
entrada da implementação. Autoridade acima deste arquivo:
`revisao_claude_code.md` e, acima de tudo, `AGENTS.md` +
`.specify/memory/constitution.md`.

## 0. TL;DR

Instrumentar **3 pontos** do backend com o SDK do **Langfuse Cloud**,
atrás de uma flag, para diagnosticar por que o atendimento N5 responde
mal. **Não** é self-hosted. **Não** é para instrumentar tudo. **Não**
entra LangChain / LangGraph / Elasticsearch. Primeiro uma `spec.md` leve
(LF-0, parar para revisão do humano), depois a instrumentação
(LF-1..LF-5). A leitura dos traces (LF-6) é do humano + Claude Code.

## 1. Ler nesta ordem antes de qualquer código

1. `.specify/memory/constitution.md` — Artigo III e Emendas 1.1.0 / 1.2.0 / 1.3.0.
2. `AGENTS.md` — o contrato: fluxo SDD obrigatório, regras de arquitetura, stop conditions.
3. `PROJECT_STATE.md` — estado real (006–012 implementados; D-043 / D-043-2 / D-044).
4. `LANGFUSE/revisao_claude_code.md` — decisões e veredito de ferramentas.
5. `LANGFUSE/plano_implementacao.md` — o roteiro: §2 (fluxo N5), §3 (ambiente Cloud), §4 (Fase 0), §7 (passos LF-0..LF-6).
6. `LANGFUSE/playbook_diagnostico.md` — a taxonomia que a Fase 0 vai preencher.
7. `LANGFUSE/detalhamento_execucao.md` **§3 e §5** — contratos de observação e DB de teste. O resto do arquivo é provisório (banner no topo).
8. Código: `app/customer_care/ai/router.py`, `ai/providers.py`, `rag/service.py`, `autonomy/service.py`, `knowledge/embeddings.py`.
9. `DECISIONS.md` D-043 / D-043-2 / D-044 e `specs/010` / `specs/011` — o comportamento N5 real que você vai observar.
10. O `git diff` atual antes de tocar em qualquer arquivo.

Antes mesmo de LF-0 você pode rodar o SQL de baseline de
`plano_implementacao.md` §4.1 (`GROUP BY provider, status` em
`ai_generations`) — dá a distribuição crua de caminhos sem instrumentar
nada.

## 2. LF-0 — spec leve (fazer primeiro, PARAR para revisão do humano)

Criar `specs/013-local-langfuse-observability/` com **apenas**:

- `spec.md`
- `analysis.md`

**Não** criar `plan.md`, `tasks.md`, `data-model.md` nem `contracts/`.
Motivo: sem schema novo, sem endpoint novo, sem migração, sem mudança de
superfície para o cliente. A lista de tarefas já existe como LF-0..LF-6
em `plano_implementacao.md` §7. O repo normalmente usa o pacote completo;
aqui o humano e o Claude Code decidiram o mínimo (ver
`revisao_claude_code.md` §2.2).

`spec.md` **precisa** cobrir:

- **Fluxo de dados para o Cloud** — o que sai do processo: texto de
  mensagens, prompts renderizados, respostas do modelo, evidências,
  parâmetros, decisões (tudo de conversa sintética `simulated: true`). O
  que **nunca** sai: `OPENAI_API_KEY`, `*_SECRET`, `*_PEPPER`, token
  anônimo, objeto `Session` SQLAlchemy, request FastAPI, chain-of-thought
  (reasoning só como metadado de consumo).
- **Nenhuma exceção nova ao Artigo III.** A instrumentação **observa** o
  caminho N5 existente (Emenda 1.3.0); não cria envio direto IA→cliente,
  não altera decisão / elegibilidade / regra de envio.
- **Fail-open como invariante:** Langfuse indisponível, flag `false` ou
  erro do SDK não podem afetar atendimento nem `pytest`.
- **Kill flag:** `LANGFUSE_TRACING_ENABLED`, default `false` no
  versionado.
- **Reconciliação de escopo:** o resumo "Current authorized scope" do
  `AGENTS.md` para em 005; 006–012 + D-043 / D-043-2 / D-044 são o
  baseline real e é o que será instrumentado. Registrar que isso é
  entendido.
- **Sem migração de schema.** Correlação usa IDs que já existem.

`analysis.md`: revisão de consistência cruzada — a spec contradiz
constituição / `AGENTS.md` / `specs/010` / `specs/011`? Confirmar que
não. Rodar o `analyze` do Spec Kit (ou equivalente) antes de implementar.

**PARAR aqui e pedir revisão do humano antes de LF-1.**

## 3. LF-1..LF-5 — implementação

### Regras que não se negociam

- **Fixar a versão do SDK Langfuse em `app/requirements.txt` ANTES de
  escrever o adaptador.** Os docs antigos assumem "v4"; confirmar o que
  existe e é compatível com Python 3.12 + `openai==1.102.0`. Não escrever
  contra API presumida.
- **Adaptador em `shared/` ou `infrastructure/`.** No-op real quando
  `LANGFUSE_TRACING_ENABLED=false` — sem custo de import, sem rede.
- **Provider `deterministic-test`: 0% instrumentado.** Gate em
  `get_settings().ai_provider != "deterministic-test"` **E** na flag.
  `pytest` não pode mudar de comportamento — provar isso.
- **Wrapper OpenAI só em `ai/providers.py` e `knowledge/embeddings.py`,
  atrás da flag.** `embeddings.py` tem client `OpenAI` próprio — tratar
  separado; uso de embedding capturado **explícito**, sem duplicação.
  Verificação LF-1 (2026-09-10): o SDK fixado `4.15.1` também instala
  hooks globais para embeddings; conter esses hooks em LF-2/LF-3.
- **Nada de chamada de rede dentro de transação de atendimento.** Export
  em lote. Flush com teto no shutdown. Proteger entrada / atualização /
  saída do adaptador preservando retorno ou exceção original.
- **Registrar preço de `gpt-5-mini` e `text-embedding-3-small`** no
  projeto Langfuse (com fonte datada) ou o custo vem vazio.
- **Sem migração.** Se aparecer necessidade real de coluna nova: PARAR,
  atualizar `spec.md` → `analysis.md` primeiro (`AGENTS.md` documentation
  drift rule + stop conditions).

### Os 3 pontos (e só esses 3)

| # | Onde | Capturar |
|---|---|---|
| 1 | `rag/service.py::retrieve()` | a **string exata** que foi embedada (o `"\n".join(...)` de mensagens + `manual_search_text`), não só IDs; evidências ordenadas com score (`1.0 - distance`), tipo, rank |
| 2 | `ai/providers.py`: `generate`, `generate_ungoverned`, `rerank_clinical`, `extract_date_intent`; `knowledge/embeddings.py::embed` | mensagens enviadas, resposta, modelo, uso (tokens); embedding explícito |
| 3 | `ai/router.py::maybe_open_autonomous_window()` | qual dos ~5 ramos disparou; `n5_path` (`reuse_answer` / `guided_booking` / `freeform_fallback`), `fallback_reason` (`initial_not_answer` / `weak_clinical_shortcut`), `mechanism` (`ungoverned_n5` / `governed_autonomy`); **distinguir "entregou o ANSWER fundamentado verbatim" (D-043) de "gerou fallback fresco sem evidência"** |

Correlação: `session_id = conversation_id`, `trace_id =
triggering_message_id` sem hífen (32 hex). Contrato:
`detalhamento_execucao.md` §3.1.

Envio confirmado (`autonomy/service.py::resolve_elapsed_autonomous_sends()`)
roda numa requisição **posterior** (poll). Se capturar isso: publicar só
pós-commit, reconstruir o trace pelo `triggering_message_id` da geração,
**não** manter span aberto durante a janela de veto. Contrato:
`detalhamento_execucao.md` §3.3.

### Não fazer

- Self-hosted (nada de ClickHouse / Redis / MinIO; `docker-compose.yml`
  não muda).
- LangChain, LangGraph, LlamaIndex, Elasticsearch, vector DB separado.
- Instrumentar além dos 3 pontos (dashboards, runner de avaliação,
  gestão de prompts são pós-diagnóstico).
- Editar `plano_implementacao_local.md` / `plano_curso_pratico.md` (já
  têm banner).
- Transformar correção em mudança de comportamento de agendamento /
  autonomia. A instrumentação **observa**, não muda decisão /
  elegibilidade / regra de envio.
- Persistir chain-of-thought.
- Deploy. Fase 0 é diagnóstico local.

## 4. Gates (depois do código — `AGENTS.md` "After code")

- Backend: `ruff`, `mypy`, `pytest`, integração PostgreSQL, OpenAPI/API.
- Frontend: `eslint`, `tsc`, `vitest`, `build`.
- `smoke_*.py` completo. Playwright.
- **Tudo passa com a flag `true` E `false`.**
- `pytest` no caminho `deterministic-test` = comportamento idêntico ao de
  antes. Provar.
- Convergência spec-to-code.

### Armadilhas desta base (PROJECT_STATE / PROCESSO_RAG)

- Dev DB compartilhada. `n5_kill_switch_enabled = true` aqui (demo,
  intencional). `test_governed_autonomy.py` / `test_ungoverned_n5.py`
  assumem `false` — limpar antes da suíte, restaurar `true` depois.
- Resíduo `t010-*` / `t011-*` (`ai_generations` / `messages` órfãos)
  FK-falha o teardown desses arquivos — limpar antes de rodar a suíte
  cheia.
- `smoke_ingestion_changed.py` reverte TODOS os embeddings do catálogo
  para hash de teste, sem aviso. **Não rodar contra a dev DB de
  trabalho.** Recuperação aleatória → checar
  `SELECT embedding_model, count(*) FROM content.qa_entries GROUP BY 1`.

## 5. Checkpoints com o humano

- Após **LF-0** (spec + analysis): revisão antes de implementar.
- Após **LF-1** (prova curta: 1 trace, 1 chamada com custo, 1 score
  visíveis no Cloud): confirmar SDK / wrapper antes de instrumentação
  ampla.
- Após **LF-5** (gates verdes): antes da sessão de leitura de traces.

## 6. Divisão

- **Codex:** LF-0 a LF-5 — spec, adaptador, instrumentação, gates.
- **Humano + Claude Code:** LF-6 — ler 20–30 traces reais e nomear os 3
  modos de falha no `caderno_de_evolucao.md`. Trabalho de julgamento.
