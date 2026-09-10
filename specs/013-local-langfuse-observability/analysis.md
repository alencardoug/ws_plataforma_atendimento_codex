# Análise de consistência — LF-0 / Langfuse Cloud

Data: 2026-09-10. Escopo: revisão documental anterior à instrumentação.
Resultado da revisão inicial: **LF-0 preparado para revisão humana**.
Atualização: **LF-0 aprovado; prova LF-1 disponível para revisão**, conforme §7–§8.

## 1. Método e fontes

Executada revisão cruzada **equivalente ao `analyze` do Spec Kit**,
permitida por [AGENTS.md](../../AGENTS.md) e
[instrucoes_codex.md §2](../../LANGFUSE/instrucoes_codex.md). Não se afirma
execução do comando `analyze`: foram confrontados requisitos, autoridade,
contratos, código existente, ambiguidades, cobertura de aceite e limites.
Não se exigiu `plan.md`/`tasks.md` que a instrução humana dispensou
expressamente neste pacote.

A leitura seguiu §1 das instruções, antes de editar arquivos:

1. [Constituição](../../.specify/memory/constitution.md), especialmente
   Artigo III e Emendas 1.1.0 / 1.2.0 / 1.3.0.
2. [AGENTS.md](../../AGENTS.md), autoridade e fluxo SDD.
3. [PROJECT_STATE.md](../../PROJECT_STATE.md), inclusive correções e
   ressalvas de fechamento.
4. [Revisão Claude Code](../../LANGFUSE/revisao_claude_code.md).
5. [Plano Cloud](../../LANGFUSE/plano_implementacao.md).
6. [Playbook](../../LANGFUSE/playbook_diagnostico.md).
7. [Detalhamento §3 e §5](../../LANGFUSE/detalhamento_execucao.md), com o
   banner que limita a vigência do restante.
8. Código em `ai/router.py`, `ai/providers.py`, `rag/service.py`,
   `autonomy/service.py`, `knowledge/embeddings.py`.
9. [DECISIONS.md](../../DECISIONS.md) D-043 / D-043-2 / D-044 e todos os
   seis artefatos Markdown de cada pacote
   [010](../010-governed-autonomous-response/spec.md) e
   [011](../011-ungoverned-fictional-demo-autonomy-n5/spec.md).
10. `git status`, diff de trabalho e diff staged antes de qualquer escrita.

Complementos para resolver os achados: [spec 012](../012-appointment-availability-continuity-and-booking-action/spec.md),
[ARCHITECTURE.md](../../ARCHITECTURE.md), [SECURITY.md](../../SECURITY.md),
[DATA_MODEL.md](../../DATA_MODEL.md), [TEST_PLAN.md](../../TEST_PLAN.md),
[SDD_WORKFLOW.md](../../docs/sdd/SDD_WORKFLOW.md) e
[CITATION_POLICY.md](../../docs/governance/CITATION_POLICY.md);
`anonymous_access/router.py`, modelos, settings, fluxo GB, polls do
operador, disclaimers do frontend, requirements/Dockerfile e localização
dos testes de autonomia/containment existentes.

Checkout analisado: branch `refino-rag`, HEAD
`6d08c680ce94ddbeb3ed63943a7a6a962a40d020`. Já havia quatro arquivos
modificados em `LANGFUSE/` (`README`, detalhamento, curso e plano local) e
quatro novos (instruções, plano Cloud, playbook e revisão). Nenhuma mudança
staged. Esses materiais pertencem ao estado recebido e são preservados.

## 2. Consistência normativa

| Autoridade / limite | Confronto com a spec 013 | Resultado |
|---|---|---|
| Constituição I/XII; SDD de AGENTS | Somente spec + análise agora; revisão humana antes de LF-1; roteiro LF existente conserva dependências | Compatível com a exceção documental explícita da sessão |
| Artigo III / Emenda 1.1.0 | R01/R06 não adicionam envio nem estendem AA-10; nenhum hook no script de booking | Nenhuma exceção nova |
| Artigo III / Emenda 1.2.0; 010 GA-2..GA-6 | Gates de evidência/categoria/trigger, switch, veto, ações humanas, WAITING e capacidade são preservados; mecanismo governado precede N5 | Compatível; não classificar governado como N5 |
| Artigo III / Emenda 1.3.0; 011 N5-1..N5-6 | R01 observa N5 e as correções humanas já registradas; switch independente e disclaimer mantidos | Compatível após reconciliação histórica explícita (§3) |
| Artigos IV/V/X | R05/R06 preservam falhas de negócio, traceabilidade, ausência de reasoning e verificação negativa | Cobertura definida, prova de execução pendente |
| Artigo VI; SECURITY | R02 limita conteúdo a sintético, mantém redação já existente e exclui secrets/tokens/objetos; conteúdo não vira log INFO | Cloud é destino autorizado de diagnóstico, sem dados reais |
| Artigo VII; política de citações | Não há endpoint/campo público de trace, acesso anônimo ao diagnóstico nem relaxamento de exposição administrativa | Compatível |
| Artigos VIII/IX; arquitetura/dados | Adaptador no monólito, exportação sem dependência transacional, zero schema novo; PostgreSQL e auditoria continuam autoritativos | Sem nova infraestrutura de negócio |
| 012 AC/OB; D-044 | R01 não muda agenda, criação de slots, `MANUAL_BOOKING_OFFER`, envio por poll ou trava de concorrência | Compatível com o comportamento corrigido existente |

**Conclusão:** a spec 013 não introduz contradição normativa com a
constituição, AGENTS ou os comportamentos autorizados de 010/011. Isso
não equivale a afirmar que todos os textos históricos estejam sincronizados
nem que a implementação futura já passou nos testes.

## 3. Divergências encontradas e tratamento no artefato ativo

| ID | Evidência / impacto | Resolução explícita em spec.md |
|---|---|---|
| A01 — Escopo histórico | AGENTS para em 005; PROJECT_STATE contém 006–012. Há inclusive resumos antigos de DONE/deploy que não refletem as ressalvas posteriores | §2 incorpora o baseline posterior exigido pelo humano e mantém 007/012 CONDITIONAL. Não usa o resumo antigo para proibir a observação de N5 nem fecha pendências alheias |
| A02 — N5 antigo | 011 N5-2 descreve nova completion para `ANSWER` sem categoria; seu plan §4 faz fallback sempre que o governado não abre. D-043/D-043-2 e o código corrigiram isso | §2 registra reaproveitamento mesmo sem categoria, GB elegível só em N5 e gate clínico de 0.40. É reconciliação das decisões humanas existentes, não nova mudança de política |
| A03 — Origem do disparo | PROJECT_STATE/D-044 ainda narram a primeira versão com geração no POST; o final de D-044 e o código retiram essa chamada por latência | §2/§6 usam GET poll e typing para o cliente, além dos polls do operador. Não se reintroduz geração no POST nem se cria scheduler |
| A04 — Três pontos versus catálogo completo | Detalhamento §3 nomeia também buscas internas e etapas de agenda; plano §7 LF-4 pede envio confirmado, enquanto instruções §3 condiciona como capturá-lo | §5 limita a coleta aos três pontos, com contexto e confirmação pós-commit necessários ao aceite do plano §4.5/LF-4. Não transforma todo o catálogo em tarefas; spans internos adicionais ficam fora |
| A05 — Pacote SDD completo versus LF-0 | Fluxo padrão menciona spec/plan/tasks; instrução atual manda apenas dois arquivos e revisão antes de instrumentar | §1 formaliza a exceção de maior autoridade. §8 contém aceite; plano Cloud §7 continua a lista de tarefas. Não criar artefatos vazios para satisfazer um template |
| A06 — Ordem do aceite | Plano §4.5 inclui o caderno diagnóstico, LF-5 referencia esse aceite, mas a leitura dos traces só ocorre em LF-6 | AC-01..AC-07 são técnicos; AC-08 e o fechamento do diagnóstico dependem de LF-6. LF-0 não se confunde com a Fase 0 inteira |
| A07 — Dados sintéticos / credenciais | `Conversation` não possui campo `simulated`; clientes OpenAI e Langfuse precisam de autenticação, mas secrets não pertencem aos traces | §3 define `simulated: true` como metadado, não coluna/anonimização. Credenciais autenticam apenas o serviço correspondente, jamais entram no payload. Preserva a redação atual de CPF, sem presumir redação de toda resposta de pagamento |
| A08 — Cloud e testes | Arquitetura V1 diz “no cloud dependency for acceptance”; validação de integração LF-1 exige prova real Cloud; dev DB tem incidentes documentados | §4/§8 preservam suíte determinística sem Langfuse e tratam prova real como aceite adicional da integração. Gates com banco usam o destino isolado de detalhamento §5, sem limpeza da dev DB |

As reconciliações estão na **spec ativa 013**, sob a autorização humana
desta sessão, sem reescrever artefatos fechados ou os planos históricos de
`LANGFUSE/`. Nenhuma delas autoriza refazer os comportamentos observados.
Não restou conflito novo de escopo que impeça entregar LF-0 para revisão.

## 4. Evidência no código e limites de observação

| Inspeção direta | Consequência para o contrato |
|---|---|
| [ai/router.py](../../app/customer_care/ai/router.py): `generate_draft`, `_trailing_customer_messages`, `generate_ungoverned_reply`, `maybe_open_autonomous_window` | Query é concatenação literal das mensagens selecionadas e busca manual; histórico automático é a corrida final de mensagens CUSTOMER. Fallback cria outra geração com `prior_generation_id` e mesmo retrieval, sem evidências atribuídas. A observação não amplia esse contexto |
| [rag/service.py](../../app/customer_care/rag/service.py): `retrieve` | `embed([query])`; mistura candidatos Q&A/clínicos por distância, deduplica pais, corta em `top_k` (8 no draft), score `1.0-distance`. Capturar os resultados ordenados e texto exato, sem refazer a busca |
| [ai/providers.py](../../app/customer_care/ai/providers.py) e [knowledge/embeddings.py](../../app/customer_care/knowledge/embeddings.py) | Dois clientes OpenAI separados. Uso é persistido hoje no resultado de `generate`, mas não no retorno de `generate_ungoverned`, `rerank_clinical`, `extract_date_intent` ou `embed`; observar respostas no limite do provider, sem migração nem chamadas adicionais |
| [autonomy/service.py](../../app/customer_care/autonomy/service.py): `resolve_elapsed_autonomous_sends` | Seleciona pendências com `FOR UPDATE SKIP LOCKED`, cria Message/auditoria e faz commit por resolução. Cada mensagem precisa da correlação de sua própria geração, não da conversa do poll. Telemetria pós-commit não pode transformar uma falha de export em falha do envio |
| [anonymous_access/router.py](../../app/customer_care/anonymous_access/router.py) e [operator_workspace/router.py](../../app/customer_care/operator_workspace/router.py) | Gatilhos reais cobrem customer GET/typing e operator queue/detail; o POST somente recebe/persiste a mensagem e avança os parsers existentes. São necessários metadados de origem, não serialização de request |
| [scheduling/guided_booking.py](../../app/customer_care/scheduling/guided_booking.py) | Redação de CPF ocorre antes de persistir Message; resposta de pagamento pode permanecer literal por decisão anterior. `interpret_slot_choice` não retorna um campo de proveniência do parser. Não inventar esse campo por ausência de um span de embedding |
| [infrastructure/models.py](../../app/customer_care/infrastructure/models.py) | IDs e vínculos suficientes já existem em Conversation, RetrievalRun/Hit, AIGeneration e PendingAutonomousSend. Não há necessidade demonstrada de schema |
| [frontend/src/main.tsx](../../frontend/src/main.tsx) | Disclaimers presentes na entrada do cliente e login do operador, por inspeção estática; nenhuma verificação de navegador executada em LF-0 |
| [app/Dockerfile](../../app/Dockerfile), [requirements.txt](../../app/requirements.txt), [settings.py](../../app/customer_care/shared/settings.py) | Python 3.12, `openai==1.102.0`, modelos default `gpt-5-mini`/`text-embedding-3-small`; ainda sem SDK/flag Langfuse. Não há compatibilidade Langfuse já comprovada |

O baseline SQL opcional de `plano_implementacao.md` §4.1 **não foi
executado**. Mesmo executado, `GROUP BY provider,status` contaria gerações,
não envios, turnos ou taxa de qualidade: uma tentativa e seu fallback
podem gerar duas linhas. Não há distribuição ou diagnóstico medido nesta
entrega. Similaridade, `ANSWER` e ausência de telemetria não viram notas de
qualidade, sucesso ou contagem autoritativa de pendências.

## 5. Cobertura e pendências antes da implementação

| Requisito | Aceite definido em spec.md §8 | Estado em LF-0 |
|---|---|---|
| R01 — Baseline, Artigo III e comportamento preservado | AC-03..AC-07 | Conferência documental/código existente concluída; regressão futura pendente |
| R02 — Dados/exportação | AC-01, AC-06 | Campos permitidos/proibidos explícitos; teste do payload futuro pendente |
| R03 — Flag/no-op/SDK | AC-01, AC-02 | Defaults e gates especificados; SDK não escolhido nem instalado |
| R04 — Três pontos e decisão | AC-04, AC-08 | Ramos identificados; nenhum trace coletado |
| R05 — Correlação, commit, dedup e consumo | AC-01, AC-04, AC-05, AC-08 | Contratos definidos; prova no SDK/Cloud e transações pendente |
| R06 — Fail-open/limites | AC-02, AC-03, AC-06, AC-07 | Negativos e gates definidos; nenhum teste de instrumentação executado |

Antes do adaptador, LF-1 deve verificar em fontes oficiais a versão
disponível/compatível do SDK, API dos wrappers e deduplicação de scores
(ID + nome + timestamp), endpoint Cloud e preços datados dos modelos.
Não se reproduz a suposição antiga de “SDK v4” nem se inventa custo.
Limites concretos de export/flush deverão ser registrados e validados
antes de depender deles como prova de fail-open. São pendências da etapa
seguinte, não resultados de LF-0.

A futura regressão deve preservar os testes de
`test_governed_autonomy.py`, `test_ungoverned_n5.py` (incluindo GB e gate
clínico), `test_customer_driven_autonomy.py`, `test_booking_offer_draft.py`
e os testes de containment 005/010/011/012/AA-10; complementar com testes
próprios de no-op, payload, falhas do adaptador e confirmação pós-commit.
Gates abrangem capacidade seis abas/quatro ativas, grounding,
parent-child, ingestão idempotente e negativos de segurança, conforme
AGENTS. Execução exclusivamente com banco isolado quando houver escrita;
não reproduzir a antiga limpeza da dev DB por `provider` ou categoria.

## 6. Verificação desta entrega e parada

- [x] Ordem de leitura concluída e diff inicial inspecionado.
- [x] Revisão equivalente ao analyze e reconciliações registradas na spec.
- [x] Todos os seis requisitos possuem critérios de aceite.
- [x] Pacote limitado a `spec.md` e `analysis.md`.
- [x] 42 links locais resolvidos; seis requisitos mapeados e oito critérios
  de aceite; dois arquivos Markdown, com newline final e sem whitespace
  excedente (verificação local por script).
- [x] `git diff --check` sem erros; hash SHA-256 do diff versionado e dos
  quatro arquivos novos recebidos em `LANGFUSE/` iguais aos registrados
  antes da escrita. Apenas o pacote 013 foi acrescentado por LF-0.

Não foram executados backend/frontend/E2E/smoke, SQL de baseline, escrita
no banco, alteração de `.env`, instalação de SDK, criação de projeto
Cloud, coleta/exportação ou deploy. Os gates “After code” serão executados
após código autorizado; não há resultado verde de instrumentação a
declarar agora.

**Parada obrigatória:** solicitar revisão humana destes dois documentos,
conforme a instrução da sessão e `LANGFUSE/instrucoes_codex.md` §2/§5.
LF-1 permanece pendente; preparar LF-0 não autoriza iniciar instrumentação.

## 7. LF-1 — autorização, baseline e revisão anterior ao código

Em 2026-09-10 o humano aprovou LF-0 (“Pode seguir”), solicitou o baseline
como primeira atividade e depois informou ter preenchido o `.env`.
A parada registrada no §6 é o histórico da entrega LF-0; o próximo
checkpoint é a prova curta de LF-1, antes do adaptador de atendimento.

**Baseline executado em 2026-09-10 04:34:04 UTC**, banco local `oncology`,
em `BEGIN READ ONLY` (`transaction_read_only=on`), com a query de
`plano_implementacao.md` §4.1. O serviço estava parado e a porta 5433
ocupada; usou-se o mesmo volume em container temporário, sem portas
publicadas, encerrado e removido após a consulta. Nenhum atendimento,
reseed, migration ou limpeza foi executado.

| Provider | Status | Gerações nos últimos 30 dias |
|---|---|---:|
| dynamic-pattern-resolver | ANSWER | 102 |
| guided-booking | ANSWER | 41 |
| openai | ANSWER | 16 |
| ungoverned-n5 | ANSWER | 9 |
| test | ABSTAIN | 7 |
| clinical-parent-document | ANSWER | 4 |
| clinical-deflection-rerank | ANSWER | 3 |
| openai | ABSTAIN | 2 |
| test | ANSWER | 1 |
| dynamic-pattern-resolver | ABSTAIN | 1 |

Total **186 gerações**, incluindo fixtures. Não é contagem de turnos,
envios ou qualidade; tentativa inicial/fallback podem aparecer separados.

**Provisionamento confirmado:** chaves lidas do `.env` sem exibir valores;
`GET /api/public/projects` autenticou o projeto `My Project`
(`cmtv15btb069jad0f0fretg3g`) em `cloud.langfuse.com`. O usuário forneceu
`LANGFUSE_BASE_URL`, que é o nome atual documentado pelo SDK. Spec §4 →
plano Cloud §3/§7 foram atualizados antes do código para aceitar esse nome
e `LANGFUSE_HOST` como alias, sem destino implícito ou ambiguidade.

**SDK escolhido: `langfuse==4.15.1`**, release 2026-08-28, Python
`>=3.10,<4`. Metadados oficiais e resolução `pip install --dry-run` em
Python **3.12.14** confirmaram compatibilidade com os pins atuais,
inclusive `openai==1.102.0`, `pydantic==2.11.7` e `httpx==0.28.1`.
O pin deve preceder o cliente de prova. Fontes consultadas em 2026-09-10:
[PyPI 4.15.1](https://pypi.org/project/langfuse/4.15.1/),
[SDK/endpoint](https://langfuse.com/docs/observability/sdk/overview),
[wrapper OpenAI](https://langfuse.com/integrations/model-providers/openai-py).
O nome “v4” é agora verificado, não herdado por suposição do plano antigo.

Preços **Standard**, USD por milhão de tokens, conferidos na
[documentação oficial OpenAI](https://developers.openai.com/api/docs/pricing)
em 2026-09-10: `gpt-5-mini` input **0.25**, input cached **0.025**,
output **2.00**; `text-embedding-3-small` input **0.02**. Verificar o
cadastro no projeto antes da prova; não interpretar custo ausente como
zero. O contrato ID + nome + timestamp está confirmado pela
[documentação de scores](https://langfuse.com/docs/evaluation/evaluation-methods/scores-via-sdk).

Revisão de consistência desta continuação: a prova será um comando
isolado em `infrastructure/`, com cliente de prova em `ai/providers.py`
(único import de wrapper neste passo), conteúdo sintético fixo e sem
acesso ao banco. Não altera o construtor normal do provider nem instala
hooks nos três pontos de atendimento antes do checkpoint. Os limites
e fail-open do adaptador de atendimento continuam sujeitos a LF-2/LF-5;
o comando diagnóstico pode reportar falha sem afetar serviço algum.

Inspeção do código instalado de `langfuse==4.15.1` (antes do cliente de
prova): `openai.py::register_tracing()` modifica recursos OpenAI no
processo; `OPENAI_METHODS_V1` inclui `Embeddings.create` e
`AsyncEmbeddings.create`. A premissa “wrapper não cobre embeddings” de
`instrucoes_codex.md` §3 ficou obsoleta. Spec §4 → plano §4.2 → instruções §3 foram
reconciliados: preservar captura explícita e consumo único em LF-3,
com contenção dos hooks em LF-2. Import do wrapper na prova somente
no processo CLI; nenhum import no startup do atendimento.

O catálogo existente retornado por `GET /api/public/models` já contém
os preços Standard corretos; nenhuma sobrescrita foi necessária:

| Modelo | ID da definição Langfuse gerenciada | USD/token |
|---|---|---|
| `gpt-5-mini` | `3d6a975a-a42d-4ea2-a3ec-4ae567d5a364` | input `0.00000025`; cached `0.000000025`; output/reasoning `0.000002` |
| `gpt-5-mini-2025-08-07` | `03b83894-7172-4e1e-8e8b-37d792484efd` | mesmos preços Standard do alias |
| `text-embedding-3-small` | `clruwn3pc00010al7bl611c8o` | total `0.00000002` (tokens de entrada para embedding) |

O custo da prova deve ser calculado pelo Cloud, comparado com o usage
real e a fonte acima, sem enviar `cost_details` fabricado. Reasoning é
parte dos tokens de saída, não consumo adicional sobre esse total.

## 8. Checkpoint LF-1 — prova persistida e convergência

**Prova técnica disponível para revisão; LF-2 não iniciado.**
Uma única completion real, em processo diagnóstico separado, sem banco,
endpoints ou hooks no atendimento:

| Evidência | Resultado confirmado pela API autenticada |
|---|---|
| Trace | [`9a9c83d1ffdd43b18af57c9269569761`](https://cloud.langfuse.com/project/cmtv15btb069jad0f0fretg3g/traces/9a9c83d1ffdd43b18af57c9269569761) |
| Início UTC | `2026-09-10T04:50:23.377Z` |
| Sessão / ambiente | ID sintético igual ao trace; `local-test`, `simulated: true`, `purpose=lf1_sdk_probe` |
| Observações | Um span raiz e uma geração `0c6a4e4fee0b59d4` |
| Modelo retornado | `gpt-5-mini-2025-08-07`; definição gerenciada verificada no §7 |
| Consumo | 28 input + 10 output = 38 tokens; cache e reasoning numérico = 0 |
| Custo calculado no Cloud | **USD 0.000027** = `28 × 0.25 / 1e6 + 10 × 2 / 1e6`; nenhuma duplicação do custo no span raiz |
| Score | `lf1.exact_answer`, BOOLEAN **1**, ID `af3aba60-b7f2-5776-a04d-6799e282eaa7` |
| Timestamp original do score | `2026-09-10T04:50:23.376239+00:00` (API retorna precisão em milissegundos) |

O prompt é aritmética fixa e pública; a resposta foi `2`. Esse score
confirma o critério da prova, não mede qualidade N5. O link exige acesso
ao projeto; não foi criada uma publicação pública do trace.

**Timeout observado e corrigido:** a primeira consulta de confirmação
atingiu `ReadTimeout` de 3 s após a chamada e exportação. O trace e o
score já estavam persistidos. Recuperou-se o mesmo ID com GET; a consulta
corrigida confirmou os dados em **1.133 s**, sem nova completion ou score.
O comando agora repete somente leituras em falhas transitórias dentro
do teto original de 30 s e imprime IDs/consumo selecionados para permitir
recuperação. Não se afirma que a primeira execução cumpriu o alvo de
visibilidade em 30 s; a medição completa permanece no aceite LF-5.
O flush do SDK não expõe timeout próprio: esta CLI foi executada sob
`timeout --kill-after=5s 90s`; o ciclo de vida do atendimento é LF-2.

**Refinamento de R02 para este checkpoint:** a inspeção recursiva do
payload completo encontrou somente `LANGFUSE_PUBLIC_KEY`, nos atributos
`scope.attributes.public_key` do SDK. Nenhuma secret key, chave OpenAI,
pepper ou senha do `.env` apareceu. O SDK usa o atributo público em
`span_processor.py::_is_langfuse_project_span` para separar projetos;
a autenticação utiliza o par public/secret. Spec R02/AC-01 foi explicitada
para permitir esse identificador público automático, mantendo os valores
fora de código/docs e a proibição integral de segredos no payload. Esse
detalhe e os hooks globais/embeddings do §7 compõem a revisão do wrapper.

**Código entregue:** pin em `app/requirements.txt`; campos opcionais em
`shared/settings.py` e `.env.example` (flag default false, typo desativa);
factory de prova lazy em `ai/providers.py`; CLI em
`infrastructure/langfuse_probe.py`. Os métodos/classes existentes do
provider são idênticos ao HEAD por comparação de AST. `rag/service.py`,
`ai/router.py`, `knowledge/embeddings.py`, `autonomy/service.py` e
`docker-compose.yml` não mudaram. Nenhuma migração, startup hook,
dependência de banco ou nova chamada de negócio.

Validação em Python 3.12.14, SDK fixado e dependências do backend:

- `ruff check customer_care tests`: passou.
- `mypy customer_care`: passou, 53 arquivos.
- `test_langfuse_probe.py`, `test_ai_providers.py`,
  `test_date_intent_extraction.py`: **48 testes com flag false e 48 com
  flag true**, provider determinístico. Subprocessos proíbem import
  Langfuse/OpenTelemetry, conexão de rede e início de threads; geração e
  embedding determinísticos continuam funcionando sem credenciais.
- Regressão do timeout: simula timeout → 404 → leitura persistida,
  apenas GET, consumo em buckets separados e teto total mantido.
- Integração PostgreSQL, API, frontend, smoke e Playwright completos
  não executados neste checkpoint: são gates LF-5 no banco isolado.

Reprodução da prova em ambiente **Python 3.12** com
`app/requirements.txt` instalado, a partir da raiz (Settings lê `.env`):

```bash
PYTHONPATH=app LANGFUSE_TRACING_ENABLED=true timeout --kill-after=5s 90s \
  python -m customer_care.infrastructure.langfuse_probe
```

Cada execução dessa prova cria uma nova chamada faturável. Para um timeout
de leitura, consultar o ID emitido antes de considerar outra execução.
Nesta máquina, usou-se o Python 3.12 da imagem backend em contêiner
`docker compose run --rm --no-deps`, com venv temporário, código e `.env`
montados para leitura, sem publicar portas. O `.env` não foi editado pelo
Codex e a flag foi ligada somente nesse processo. Os serviços cotidianos
continuam parados como no início; os contêineres de prova são removidos.

Convergência deste recorte: R01/R03/R05/R06 preservados nos pontos
existentes; R02 explicitado com a evidência do SDK; AC-01 comprovado
tecnicamente e entregue ao checkpoint. A contenção global do wrapper,
fail-open de entrada/update/saída, captura de embeddings sem duplicação
e os demais aceites continuam a cargo de LF-2..LF-5, após esta revisão.
