# Revisão do pacote LANGFUSE/ — Claude Code

Data: 2026-09-10. Branch: `refino-rag`.
Autor: Claude Code (sessão `session_01Fb45HPgRffXTuXQy7CCcjK`).
Escopo: revisão do pacote de planejamento Langfuse criado pelo Codex
(`avaliacao_langfuse*.md`, `plano_implementacao_local.md`,
`detalhamento_execucao.md`, `plano_curso_pratico.md`,
`caderno_de_evolucao.md`, `analise_consistencia_curso.md`), cruzada com o
código real (`ai/router.py`, `ai/providers.py`, `rag/service.py`,
`autonomy/service.py`), `PROJECT_STATE.md` e o histórico D-043/D-043-2/D-044.

Este documento registra decisões do humano tomadas em 2026-09-10 e as
mudanças de plano que decorrem delas. Não altera código nem inicia a
implementação.

---

## 1. Decisões firmadas nesta sessão

| Decisão | Detalhe |
|---|---|
| **Langfuse Cloud** | Self-hosted (web + worker + Postgres nº2 + ClickHouse + Redis + MinIO) está **descartado**. Motivo: limitação de máquina, abaixo. O profile `langfuse` no Compose sai do caminho crítico e vira apêndice histórico. |
| **Trilha de aprendizado mantida** | O humano está instalando Langfuse e precisa aprender a usá-lo de verdade. O que muda é o **formato** — ver §4. |
| **Norte único** | Consertar as respostas ruins da plataforma. Langfuse, RAGFlow, Elasticsearch e o aprendizado são **meio**, não fim. Toda escolha se justifica por "isso ajuda a localizar/corrigir um defeito específico?". |

**Confirmado pelo humano em 2026-09-10:** o formato de trilha do §4 e a
decisão de segurar RAGFlow / Elasticsearch / LangChain / LangGraph até o
diagnóstico da Fase 0 (§5). O `plano_curso_pratico.md` do Codex **não é
apagado** — recebe uma nota de "substituído" no topo e serve de fonte de
conteúdo para o `playbook_diagnostico.md`.

### Por que Cloud (registro do raciocínio)

A primeira avaliação (`avaliacao_langfuse.md`) já recomendava Cloud. A
revisão local inverteu isso com base em "custo" e "trabalho operacional" —
os dois argumentos estão **invertidos**:

- **Custo:** o free tier do Langfuse Cloud (checar limites atuais) cobre
  com folga um loop de diagnóstico de um desenvolvedor. Self-hosted custa
  recursos de máquina que não existem.
- **Trabalho:** Cloud = trocar 2 imports + `.env`. Self-hosted = 6
  serviços, healthchecks, headless init, tuning de memória.
- **Máquina (fotografia 2026-09-10):** 11,7 GiB RAM total, ~820 MiB
  livres, ~4,6 GiB "disponível", 4 cores, swap já em uso. Docker já
  segura ~34,6 GB de imagens e roda Airbyte + kind (k8s) + 3 Postgres de
  outro projeto. A doc oficial recomenda "4 cores / 16 GiB"; ClickHouse
  sozinho quer 2–4 GiB. Ia bater em swap.
- **"Dados sintéticos exigem local":** não se sustenta. A Constituição
  (Art. VI) se preocupa com dado **real de paciente**, e não existe
  nenhum — tudo é `simulated: true`. Masking é discutível igual nos dois.
- **Bônus:** Cloud torna trivial instrumentar **produção** depois (mesmo
  SDK, `environment=production`). O plano local é cego pro prod, onde
  também se observa "responder mal".

---

## 2. Avaliação do pacote do Codex

### 2.1 Forte — manter

- **Contrato de correlação/transação/dedup (`detalhamento_execucao.md`
  §3).** Foi escrito por quem leu `autonomy/service.py` e
  `maybe_open_autonomous_window()`. Acerta o difícil: o modelo de trigger
  lazy sem scheduler, o envio adiado em `resolve_elapsed_autonomous_sends()`
  numa requisição posterior, publicar evento de negócio só pós-commit,
  nunca segurar span aberto durante a janela de veto, "a chamada ao
  provider aconteceu mesmo se a transação der rollback depois", score
  idempotente por **id + nome + timestamp** (pegadinha real do SDK).
- **N5 como prioridade.** É o único caminho onde resposta ruim do LLM
  chega ao cliente sem revisão.
- **`session_id = conversation_id`, `trace_id = triggering_message_id`
  sem hífen.** Usa IDs que já existem, sem migração.
- **Fail-open.** Langfuse fora do ar não trava atendimento; export em
  lote; flush com teto.
- **Honestidade sobre limites.** "Instalar não melhora resposta",
  "similaridade não é nota de qualidade", "dataset pequeno é regressão,
  não taxa estatística".
- **Laboratório RAGFlow/Elasticsearch gated** atrás de "nossos casos
  demonstraram uma limitação de recuperação". Está no lugar certo.

### 2.2 A ajustar

- **Infra (era o maior risco):** resolvido pela decisão Cloud. Reescrever
  `plano_implementacao_local.md` para Cloud; o profile Compose vira
  apêndice "se algum dia self-hosted".
- **Sequência invertida:** o plano front-loada instrumentação exaustiva +
  dashboard p50/p95 + custo/conversa + harness de DB de teste + fechamento
  SDD **antes** do primeiro insight. → Fase 0 (§3).
- **Cerimônia SDD:** o pacote `specs/013` completo (spec+plan+tasks+
  data-model+acceptance+analysis) é desproporcional. Instrumentação **não
  cruza invariante de segurança**: sem novo caminho de envio, sem
  superfície nova pro cliente, sem schema (o plano já diz "sem
  migração"). Um `spec.md` curto + `analysis.md` bastam, cobrindo (a) que
  conteúdo sai do processo da app para o Cloud e (b) reconciliação de
  escopo com 006–012 (o resumo do `AGENTS.md` para em 005).
- **Curso:** ver §4.
- **Dataset 10/10/10 por caminho (`detalhamento` §6.1):** pode estar
  errado. Se o diagnóstico apontar recuperação como gargalo dominante, o
  dataset deve ser ponderado por `Hit@k`, não por split de caminho.
  Definir **depois** da Fase 0.

---

## 3. Escopo e sequência revistos

### Fase 0 — diagnóstico mínimo (dias, não semanas)

1. Projeto no Langfuse Cloud, `environment=local-n5`.
2. Instrumentar **3 pontos só**: `retrieve()`, as chamadas de provider
   (`generate` / `generate_ungoverned` / `rerank_clinical` /
   `extract_date_intent`), e a **decisão** em
   `maybe_open_autonomous_window()` (qual dos ~5 ramos disparou).
3. Correlação `session_id` / `trace_id` conforme §2.1.
4. Rodar 20–30 conversas N5 reais. Ler os traces:
   `{mensagem, evidências + scores, caminho, draft, texto enviado}`.
5. **Saída:** os 3 modos de falha mais frequentes, com denominador.

**Baseline de graça no dia 1, sem instalar nada:** `GROUP BY provider,
status` em `customer_service.ai_generations` já dá a distribuição crua de
caminhos (`clinical-parent-document`, `dynamic-pattern-resolver`,
`guided-booking`, `ungoverned-n5`, `clinical-deflection-rerank`, LLM).

### Depois da Fase 0

Reavaliar as Fases 1–3 do plano do Codex à luz do que a Fase 0 mostrar. O
dashboard, o custo por conversa, o runner de avaliação e a gestão de
prompts continuam valiosos — mas a ordem e o peso de cada um dependem do
diagnóstico. Não congelar o formato final agora.

---

## 4. Formato da trilha de aprendizado

O aprendizado é real e necessário (decisão do humano). O que muda é o
formato: de **currículo** para **aprendizado aplicado**.

### Por que não o calendário de 6 aulas

- É estrutura de curso (aulas time-boxed, "você conclui quando…") em cima
  de uma tarefa que, no fundo, é "instrumentar e ler traces junto".
- Ensina o conceito antes da necessidade. O **conteúdo** é bom; a entrega
  calendarizada atrasa o payoff.
- O humano quer "o que transforme e resolva a plataforma" — aprendizado
  como efeito colateral de consertar, não um curso paralelo.

### Modelo proposto: apprenticeship de diagnóstico

- **Sessões pareadas sobre conversas reais.** Pego uma resposta ruim de
  verdade, abrimos o trace, eu narro o que cada view significa **naquele
  caso** ("esse span é a recuperação; o documento certo está em rank 4;
  a query embedada foi o blob concatenado de 3 mensagens"). O conceito
  entra quando a tarefa esbarra nele.
- **Todo encontro termina com um resultado:** um modo de falha
  diagnosticado ou uma correção testada. O tempo nunca é "gasto num
  curso".
- **Dois documentos de apoio, não notas de aula:**
  - `playbook_diagnostico.md` — a taxonomia de falha (conteúdo ×
    recuperação × contexto × geração × agenda × envio), "o que cada view
    do Langfuse serve", "sinal bom × ruim", as armadilhas conhecidas
    (score `0.40`, embeddings revertidos por `smoke_ingestion_changed`,
    `n5_kill_switch_enabled`). Cresce à medida que batemos em cada
    recurso. Absorve o conteúdo bom do `plano_curso_pratico.md`, sem o
    calendário.
  - `caderno_de_evolucao.md` — o logbook de achados e experimentos. Já
    existe, manter como está.

### Reestruturação proposta de LANGFUSE/

| Arquivo | Ação |
|---|---|
| `README.md` | atualizar: entrada única, Cloud, aponta pra Fase 0 |
| `revisao_claude_code.md` | este doc |
| `plano_implementacao_local.md` → `plano_implementacao.md` | reescrever pra Cloud + Fase 0; profile Compose vira apêndice |
| `detalhamento_execucao.md` | manter; ajustes pontuais pra Cloud (endpoint, sem serviços locais); dataset/rubrica revisitados após Fase 0 |
| `plano_curso_pratico.md` | **manter, não apagar** (decisão do humano 2026-09-10). Nota de "substituído" no topo — feita. Registro do desenho original e fonte de conteúdo pro playbook. |
| `playbook_diagnostico.md` (novo) | escrever do zero reaproveitando o conteúdo conceitual do curso (taxonomia de falha, "o que cada view serve", armadilhas), sem o calendário |
| `caderno_de_evolucao.md` | manter |
| seção 10 do curso → `laboratorio_recuperacao.md` | extrair; ver §5 |
| `avaliacao_langfuse*.md`, `analise_consistencia_curso.md` | manter como histórico |

---

## 5. Ferramentas: Langfuse, RAGFlow, Elasticsearch, LangChain, LangGraph

Pergunta do humano: consertar a plataforma via Langfuse + RAGFlow +
Elasticsearch (+ LangChain/LangGraph "se achar que vai ajudar"). Resposta
franca, amarrada ao `AGENTS.md`: *"Do not add LangChain, LlamaIndex,
Redis, Kafka, Celery, microservices, or a vector database separate from
PostgreSQL unless an analyzed active-feature requirement proves
necessity."*

### Langfuse — sim (decidido)

É observabilidade: não muda o sistema, deixa ver. Puro ganho. Cloud.

### RAGFlow + Elasticsearch — experimento gated, depois da Fase 0

Valor real **se, e só se**, o diagnóstico mostrar que recuperação (miss
ou mis-rank em casos de termo exato / vocabulário) está no top 3 de
falhas. Elasticsearch dá hybrid search (BM25 + vetor); RAGFlow dá
parsing/chunking melhor. Porém:

- É vector store **separado do Postgres** → exceção à regra de
  arquitetura → precisa de spec própria e análise antes de código.
- Sequência certa (o `laboratório` do plano já acerta): nos casos
  específicos que o pgvector erra, comparar `pgvector atual` × `pgvector
  ajustado` × `RAGFlow/ES`, mesmo `k`, mesmo corpus, cópia de
  laboratório. Só integra com **ganho reproduzível nos casos-alvo** e
  impacto operacional aceitável.

**Antes de stack externa, há fruta baixa dentro do Postgres.**
`rag/service.py::retrieve()` tem ~40 linhas e:

- embeda o **blob concatenado** de todas as mensagens do cliente como um
  vetor só (dilui a query num run multi-mensagem);
- não tem reranking de recuperação (o `rerank_clinical` é outra coisa —
  escolhe entre resposta e deflexão);
- usa `score = 1.0 - distance` cru;
- HNSW nos defaults.

Hybrid search **dentro do PG** (`tsvector` + `ts_rank`, ou uma extensão
BM25), embedar só a última mensagem do cliente, um rerank leve — várias
dessas são pequenas, no stack atual, não tropeçam em nenhuma regra do
`AGENTS.md`, e podem fechar a maior parte do gap. **Testar essas
primeiro.**

### LangChain — não

Envolveria as chamadas que hoje cabem em ~50 linhas legíveis
(`providers.py`); não conserta recuperação, contexto nem seleção de
caminho; é citado **explicitamente** na regra; e piora o debug bem no
momento em que a plataforma está sendo depurada. D-043, D-043-2 e D-044
foram root-caused em uma sessão cada **porque** o código é Python plano
sem framework. Isso é propriedade a preservar, não a trocar.

### LangGraph — não por ora

A decisão de autonomia (`maybe_open_autonomous_window`, ~5 ramos) é de
fato uma máquina de estados, e há um argumento de legibilidade. Mas os
bugs recentes foram **semânticos** (thresholds, estado obsoleto,
elegibilidade de trigger) — LangGraph não teria pego nenhum. Revisitar só
se a lógica de decisão continuar crescendo, e como spec própria.

### O princípio

Toda ferramenta acima, menos o Langfuse, deixa a plataforma **maior**. O
caminho pra "transformar e resolver" é: **medir → achar o defeito
específico → aplicar a menor correção que resolve aquilo.** Uma pilha
especulativa de ferramentas é como se chega a uma plataforma maior que
ainda responde mal e agora não dá pra depurar.

---

## 6. Notas técnicas para quem implementar

O humano deixou os detalhes de implementação para Claude Code + Codex.
Registradas aqui para o Codex não perder contexto.

- **Fixar a versão do SDK Langfuse antes de escrever o adapter.** O plano
  assume "servidor/SDK v4"; confirmar o que existe (o corrente conhecido
  é o v3 baseado em OpenTelemetry). Gate de cronograma.
- **Wrapper OpenAI:** trocar `OpenAI` → wrapper do Langfuse **só** em
  `ai/providers.py` e `knowledge/embeddings.py`, atrás do flag de
  settings. `embeddings.py` tem client separado; uso de embedding
  capturado explicitamente (o wrapper de chat não cobre).
- **`deterministic-test` provider fica 100% sem instrumentação** (gate em
  `ai_provider != "deterministic-test"` **e** no flag de tracing) pra
  `pytest` não mudar em nada.
- **Preço dos modelos:** registrar `gpt-5-mini` e `text-embedding-3-small`
  no Langfuse (com fonte datada), senão todo número de custo vem
  vazio/errado.
- **Capturar a string de query exata** que foi embedada em `retrieve()`,
  não só os IDs das mensagens.
- **Na decisão N5:** distinguir "entregou o ANSWER fundamentado verbatim"
  (fix D-043) de "gerou resposta fresca sem evidência". São histórias de
  qualidade diferentes.
- **Score da evidência rank-1 + `provider` em todo turno**
  (`full_parent_draft()` devolve o pai inteiro sempre que rank-1 é
  clínico; `_AUTONOMOUS_CLINICAL_MIN_SCORE=0.40` só gateia o envio
  autônomo, não o draft).
- **Reusar `app/customer_care/evaluation/`** (casos V3-5) na fase de
  avaliação, não criar um paralelo.
- **DB de teste isolada (`oncology_langfuse_test`):** o §5 do
  `detalhamento` está caprichado; manter o rigor. Esta dev DB
  compartilhada já mordeu sessões passadas (revert de embeddings,
  `n5_kill_switch_enabled`, resíduo de fixtures `t010-*`/`t011-*`).
- **A spec fica leve** justamente porque a instrumentação não cruza
  invariante: sem novo caminho de envio, sem superfície nova pro cliente,
  sem schema.

---

## 7. Próximos passos

1. ~~Humano confirma: Cloud, formato de trilha (§4), veredito de
   ferramentas (§5).~~ **Feito em 2026-09-10.**
2. ~~Reestruturar `LANGFUSE/` conforme §4.~~ **Feito em 2026-09-10:**
   `plano_implementacao.md` (Cloud + Fase 0) e `playbook_diagnostico.md`
   escritos; `README` reapontado; notas de "substituído" em
   `plano_curso_pratico.md`, `plano_implementacao_local.md` e
   `detalhamento_execucao.md`.
3. **(próximo)** Codex segue [`instrucoes_codex.md`](instrucoes_codex.md).
   LF-0 = `spec.md` leve + `analysis.md` em
   `specs/013-local-langfuse-observability/` (parada para revisão do
   humano). Cobre: o que sai do processo para o Cloud; reconciliação de
   escopo com 006–012; a exceção mínima ao Artigo III que a
   instrumentação **não** cria (sem novo caminho de envio).
4. Codex implementa a instrumentação dos 3 pontos (LF-1..LF-5).
5. Sessão pareada: ler 20–30 traces reais, preencher os 3 modos de falha
   no `caderno_de_evolucao.md` (LF-6).
6. Reavaliar as fases seguintes e o laboratório de recuperação à luz do
   diagnóstico.
