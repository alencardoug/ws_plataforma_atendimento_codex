# Especificação leve — Observabilidade local N5 com Langfuse Cloud

Data: 2026-09-10. Estado: **LF-0 aprovado; prova LF-1 disponível para revisão**.
Instrumentação do atendimento não iniciada. “Local” nomeia a execução da aplicação; o
destino da telemetria é **Langfuse Cloud**.

## 1. Objetivo e autorização desta etapa

Permitir diagnosticar uma resposta N5 a partir da query de recuperação,
evidências, requests e respostas reais do provider, decisão de autonomia e
mensagem confirmada. A instrumentação observa o atendimento existente;
melhorias em conteúdo, recuperação, contexto, prompts ou agendamento
dependem do diagnóstico e de autorização própria.

A primeira instrução autorizou **LF-0**: este `spec.md` e
[analysis.md](analysis.md), entregues para revisão. Em 2026-09-10, o humano
aprovou a continuação (“Pode seguir”), pediu o baseline SQL primeiro e
forneceu as chaves pelo `.env` local. **LF-1** está autorizado até a prova
curta e seu checkpoint; LF-2..LF-5 aguardam essa revisão. Permanece a
exceção documental explícita ao pacote SDD completo, registrada em
[instrucoes_codex.md §2](../../LANGFUSE/instrucoes_codex.md) e
[revisao_claude_code.md §2.2](../../LANGFUSE/revisao_claude_code.md): sem
`plan.md`, `tasks.md`, `data-model.md`, `acceptance.md` ou `contracts/`
adicionais. A sequência de trabalho permanece **LF-0..LF-6** em
[plano_implementacao.md §7](../../LANGFUSE/plano_implementacao.md).
LF-0 é uma etapa da Fase 0; não conclui o diagnóstico inteiro.

## 2. LF-R01 — Baseline e autoridade de envio preservados

O resumo “Current authorized scope” de [AGENTS.md](../../AGENTS.md)
termina em 005 e está defasado. O baseline observado inclui **006–012**,
as Emendas **1.1.0 / 1.2.0 / 1.3.0** da
[constituição](../../.specify/memory/constitution.md) e as decisões humanas
**D-043 / D-043-2 / D-044** de [DECISIONS.md](../../DECISIONS.md),
conforme [PROJECT_STATE.md](../../PROJECT_STATE.md). “Implementado” não
significa fechamento irrestrito: 007 e 012 conservam seus registros
**CONDITIONAL**. Esta feature não os encerra nem reabre seu escopo.

**Nenhuma exceção nova ao Artigo III.** Permanecem os mesmos gatilhos,
elegibilidade, switches independentes, políticas de categoria, debounce,
janela global de veto e ações PAUSE / EDIT / TAKE OVER. O SDK, seus
callbacks, scores e exportadores não podem enviar mensagens, abrir ou
resolver pendências, alterar políticas ou repetir chamadas de negócio.
AA-10 permanece contido em `booking_script/`; nenhum booking, pagamento
ou armazenamento de identidade real é autorizado.

A decisão existente em `maybe_open_autonomous_window()` será descrita
pelos seguintes resultados, na ordem do código:

| Condição observada | Resultado e classificação |
|---|---|
| Trigger inelegível, settings ausentes ou nenhum mecanismo aplicável | Sem abertura de pendência; `n5_path` e mecanismo escolhido ausentes |
| `AUTOMATIC`, `ANSWER`, categoria habilitada, switch governado ligado e atalho clínico não fraco | `mechanism=governed_autonomy`; `n5_path` ausente, mesmo com N5 ligado |
| Ramo N5 alcançado, switch N5 ligado e trigger GB elegível | `mechanism=ungoverned_n5`, `n5_path=guided_booking`; mesmo template/geração |
| Ramo N5 alcançado, `ANSWER` e atalho clínico não fraco | `mechanism=ungoverned_n5`, `n5_path=reuse_answer`; mesmo ID e texto, sem nova completion |
| Ramo N5 alcançado, status inicial diferente de `ANSWER` ou atalho clínico fraco | `n5_path=freeform_fallback`; nova geração livre, ligada à tentativa inicial, destinada ao mecanismo `ungoverned_n5` se houver abertura |

D-043 preserva o `ANSWER` **também quando `category_slug` é nulo**.
D-043-2 restringe o gate `0.40` ao envio autônomo de
`provider=clinical-parent-document` (score ausente é comparado como `0.0`);
não modifica o rascunho manual. Os triggers GB elegíveis somente em N5
são `GUIDED_SLOT_SELECTION`, `GUIDED_SLOT_RESELECTION`,
`GUIDED_CPF_CONFIRMED` e `GUIDED_BOOKING_COMPLETE`.
`MANUAL_DRAFT`, `MANUAL_EVIDENCE` e `MANUAL_BOOKING_OFFER` continuam
inelegíveis. `ANSWER` ou `reuse_answer` não são notas de qualidade nem
prova, sozinhos, de fundamentação.

O disparo continua lazy, pelos polls/typing existentes. A correção final
de D-044 retirou a geração do `POST /messages`: não recolocá-la ali.
O envio continua em `resolve_elapsed_autonomous_sends()`, preservando
`FOR UPDATE SKIP LOCKED`, auditoria e transações. Falhas de IA/RAG mantêm
seu tratamento atual; um erro antes da decisão não é um falso sucesso N5.
O disclaimer de demonstração exigido pela Emenda 1.3.0 permanece presente.

## 3. LF-R02 — Fluxo de dados para o Cloud

Coleta prospectiva de execuções sintéticas, identificadas na telemetria
com **`simulated: true`**, `schema_version=1` e ambiente `local-n5`
(`local-test` nas validações da integração). O marcador é metadado de
observabilidade, não uma nova coluna nem uma garantia de anonimização.

| Pode sair do processo como telemetria | Nunca entra na serialização/exportação de telemetria |
|---|---|
| Texto sintético das mensagens selecionadas, query exata, prompts renderizados e array `messages` efetivamente enviado | Token anônimo, seu digest, tokens de operador, cookies ou headers de autenticação |
| Resposta do modelo, resultado após parsing/rerank, draft/template e texto da mensagem confirmada | `OPENAI_API_KEY`, `*_SECRET`, `*_PEPPER`, `LANGFUSE_SECRET_KEY`, senhas, DSNs com credenciais ou dumps de ambiente/settings |
| Evidências ordenadas: IDs, tipo, rank, score, conteúdo, trecho filho e pai expandido; parâmetros e IDs de ofertas já disponíveis | Objeto `Session` SQLAlchemy, entidades ORM completas, request FastAPI, cliente/objeto bruto do SDK ou argumentos capturados indiscriminadamente |
| IDs de correlação, provider/modelo, versão de prompt, parâmetros realmente usados, decisões, timestamps, duração e consumo informado | Chain-of-thought, conteúdo de reasoning ou raciocínio interno; reasoning só pode aparecer como metadado numérico de consumo |

Construir payloads por seleção explícita de campos e tipos simples.
Preservar a redação já aplicada ao CPF no fluxo GB/AA-10; não capturar
`payload.body` bruto nem reconstruir conteúdo ocultado. A resposta
sintética de pagamento segue a representação que o fluxo atual permite
persistir. Não se adiciona uma nova camada geral de mascaramento.
Erros de diagnóstico não podem serializar secrets, requests ou objetos
via `repr`/mensagem de exceção sem controle.

Chaves secretas são usadas apenas para autenticar seus respectivos clientes de
serviço, nunca como conteúdo do trace. O SDK `4.15.1` acrescenta o
identificador público do projeto (`scope.attributes.public_key`) aos
metadados de instrumentação e o usa para separar projetos. Esse campo
automático público é permitido; não inclui a secret key nem autentica
sozinho. Este refinamento verificado em LF-1 está registrado para revisão
em [analysis.md §8](analysis.md). Valores de chaves, inclusive a pública,
ficam fora do versionamento; exemplos documentam apenas os nomes. Acesso ao
projeto Cloud é de quem conduz o diagnóstico; não há link público de
trace, novo endpoint ou campo de telemetria para o cliente. Conteúdo
administrativo continua interno e corpos de mensagens continuam fora de
logs INFO. Não exportar retrospectivamente o histórico nem apagar
conversas existentes.

## 4. LF-R03 — Configuração e desativação

`LANGFUSE_TRACING_ENABLED` tem **default `false` em toda configuração
versionada**. Instrumentação só pode atuar quando a flag estiver ligada
**e** `get_settings().ai_provider != "deterministic-test"`.
`deterministic-test` fica **0% instrumentado**, inclusive embeddings e
eventos, com a flag em qualquer valor.

O adaptador fica em `shared/` ou `infrastructure/`, independente de
requests FastAPI e objetos de provider. Desligado, é no-op real: não
importa o SDK Langfuse, não cria cliente/exportador/thread e não faz rede
nem exige credenciais Langfuse. `LANGFUSE_BASE_URL` (nome atual do SDK)
ou `LANGFUSE_HOST` (alias do planejamento) deve indicar explicitamente
a região Cloud; se ambos estiverem preenchidos, devem concordar. Sem
fallback para outro destino; configuração ausente ou
inválida desativa a observação sem impedir atendimento ou testes.

LF-1 deve verificar compatibilidade com Python 3.12 e
`openai==1.102.0`, fixar a versão do SDK em `app/requirements.txt` **antes**
do adaptador e validar a API real. LF-0 não escolhe versão presumida.
Wrappers OpenAI ficam limitados a `ai/providers.py` e
`knowledge/embeddings.py`, atrás da mesma flag e exclusão de testes.
O SDK fixado em LF-1 (`4.15.1`) registra hooks globais no processo,
inclusive para embeddings. LF-2/LF-3 devem conter esses hooks e impedir
que captura explícita e automática contem a mesma chamada duas vezes;
a premissa antiga de que o wrapper não cobre embeddings está corrigida.
Em LF-1, a prova é um comando isolado, sem banco ou endpoints, que usa
um cliente de prova em `ai/providers.py`. O construtor normal do provider
continua sem instrumentação; adaptador de atendimento e ciclo de vida
pertencem a LF-2. O comando usa finalidade `lf1_sdk_probe`, IDs sintéticos
próprios, conteúdo fixo e público e flag ligada só em seu processo.
Ele deve confirmar via API autenticada que trace, consumo/custo e score
foram persistidos no projeto, antes de declarar a prova concluída.

## 5. LF-R04 — Três pontos de instrumentação

| Ponto | Captura mínima |
|---|---|
| `rag/service.py::retrieve()` | A string **exata** recebida em `query` e passada a `embed([query])`, incluindo o `"\n".join(...)` das mensagens + `manual_search_text` quando usado; evidências finais ordenadas, `score=1.0-distance`, tipo, rank, IDs, conteúdo/tamanho e expansão pai-filho; `top_k` real |
| `ai/providers.py::{generate,generate_ungoverned,rerank_clinical,extract_date_intent}` e `knowledge/embeddings.py::embed` | Requests efetivos, saída, modelo/parâmetros, duração, erro e usage quando disponível. Captura explícita de embeddings, com textos/finalidade, dimensão e quantidade; nenhuma inferência de uso a partir do wrapper de chat |
| `ai/router.py::maybe_open_autonomous_window()` | Resultado da decisão, geração inicial/final, provider, trigger, status, evidência rank-1/score quando existente, condições consultadas, `n5_path`, `fallback_reason` e mecanismo efetivo |

`fallback_reason=initial_not_answer` identifica status inicial diferente
de `ANSWER`; `weak_clinical_shortcut` identifica o `ANSWER` clínico abaixo
do gate, preservando score original ou ausência. Registrar a entrada no
fallback mesmo se a chamada livre falhar, sem afirmar abertura/envio.
Não atribuir as evidências da tentativa inicial ao request N5 livre:
`generate_ungoverned()` não recebe esse payload.

Propagação de contexto no disparo e confirmação do envio são o suporte
mínimo desses três pontos. Conforme LF-4 do plano, incluir a confirmação
em `autonomy/service.py::resolve_elapsed_autonomous_sends()`, limitada a
observar o commit existente. O catálogo de nomes do
[detalhamento §3](../../LANGFUSE/detalhamento_execucao.md) não autoriza
instrumentação adicional de buscas internas, resolvers ou parsers de
agendamento. Usar dados disponíveis; não fabricar o parser utilizado ou
o “documento certo”, cujo julgamento pertence ao diagnóstico.

## 6. LF-R05 — Correlação, transações e consumo

Reutilizar IDs existentes: `session_id=conversation_id`;
`turn_id=triggering_message_id` da última mensagem do grupo;
`trace_id=turn_id` sem hífens (**32 hex**). Um `attempt_id` por execução
efetiva, não por poll; cada operação real tem seu próprio ID. Correlacionar
`selected_message_ids` em ordem, `retrieval_run_id`, `ai_generation_id`,
`prior_generation_id`, `pending_id` e `message_id` quando existirem.
Registrar `execution_origin` (`customer_poll`, `customer_typing`,
`operator_poll`, `operator_detail`) sem capturar o request.

O contexto de `n5.process_turn` envolve o trabalho desde antes da
recuperação até decisão/falha, incluindo tentativa inicial e fallback.
Encerra antes da espera da janela de veto. O poll de resolução reconstrói
o vínculo pela **geração de cada pendência**, mesmo que resolva várias
conversas; não herda a identidade da conversa que causou o poll.
Chamadas manuais não se juntam a um turno N5 só por compartilharem
mensagem/conversa. Operações fora do turno usam trace próprio e finalidade
explícita; referências entre traces não duplicam consumo (§3.3 do contrato).

`autonomy.pending_opened`, `autonomy.pending_resolved` e `message.sent`,
quando publicados, exigem **commit confirmado**. Congelar previamente os
campos simples necessários; o exportador não recebe sessão nem consulta
ORM em outra thread. Uma chamada ao provider continua observável se a
transação posterior der rollback, mas isso não confirma envio. Ausência
de evento terminal significa “sem desfecho observado”; persistência da
mensagem não comprova exibição no navegador.

Scores seguem §3.4 do contrato: ID determinístico, nome e timestamp UTC
original estáveis, abertura separada do resultado terminal; reenvio e
chegada fora de ordem não duplicam fatos. Apenas chamadas reais ao modelo
carregam consumo faturável; `AIGeneration` determinística não é uma chamada
LLM. Uso/custo ausente é desconhecido, não zero. LF-1 valida o contrato de
scores no SDK fixado e os preços de `gpt-5-mini` e
`text-embedding-3-small`, com fonte oficial datada, antes da prova de custo.
PostgreSQL e auditoria permanecem a fonte de verdade de negócio.

## 7. LF-R06 — Fail-open e limites

Langfuse indisponível, flag desligada, configuração inadequada ou falha
na entrada/atualização/saída do SDK não podem afetar atendimento nem
`pytest`. Preservar retorno ou exceção original, número de chamadas ao
provider, textos e decisões; nunca executar o negócio novamente para
recuperar uma falha de telemetria. Exportar em lote, enfileirando localmente
sem rede de telemetria aguardada na transação ou sob trava de envio.
Inicialização/exportação são por processo, com flush de duração limitada
no shutdown; falha de exportação não aciona rollback de negócio.

**Sem migração de schema**, coluna, endpoint, mudança de UI ou contrato
público. Sem alterações de `docker-compose.yml`, self-hosted, ClickHouse,
Redis/MinIO, LangChain, LangGraph, LlamaIndex, Elasticsearch, RAGFlow,
vector DB separado, scheduler ou deploy. Dashboards, runner de avaliação,
gestão de prompts e correções de produto ficam após o diagnóstico. Nova
necessidade de schema/escopo exige interromper o trecho afetado e revisar
`spec.md` → roteiro LF correspondente → `analysis.md` antes de implementar.

## 8. Aceite e checkpoints (execução posterior à revisão de LF-0)

| ID | Evidência exigida | Requisitos / etapa |
|---|---|---|
| AC-01 | Uma prova Cloud com trace, chamada real com custo e score; SDK fixado/compatível, endpoint explícito e credenciais secretas ausentes do payload; identificador público automático conforme R02 | R02–R05 / LF-1; parar para revisão |
| AC-02 | Flag false e provider `deterministic-test` com flag true/false: zero import Langfuse, cliente, rede e observações; comportamento e resultados da suíte idênticos ao baseline | R03, R06 / LF-2, LF-5 |
| AC-03 | Falhas do SDK em inicialização/entrada/update/saída/export/flush e Cloud indisponível preservam sucesso, exceção e contagem de chamadas do negócio; atendimento manual disponível | R01, R06 / LF-2, LF-5 |
| AC-04 | Traces dos três caminhos N5, ambos os motivos de fallback e prioridade governada; resposta reaproveitada mantém ID/texto; chamadas e query/evidências correspondem ao executado | R01, R04, R05 / LF-3, LF-4 |
| AC-05 | Conversa sem operador recebe uma resposta por poll/typing; mesmo trace liga decisão e mensagem pós-commit; janela >0 não mantém span aberto; rollback não gera falso envio; repetição/out-of-order não duplica fatos ou custo | R01, R05 / LF-4, LF-5 |
| AC-06 | Negativos comprovam exclusão dos dados proibidos, manutenção da redação existente, não exposição de telemetria/citações administrativas ao cliente, triggers manuais inelegíveis, gates governados e PAUSE/EDIT/TAKE OVER intactos | R01, R02, R06 / LF-5 |
| AC-07 | Backend `ruff`, `mypy`, `pytest`, integração PostgreSQL e OpenAPI/API; frontend `eslint`, `tsc`, `vitest`, `build`; todos os `smoke_*.py` e Playwright, com flag true e false; convergência spec-to-code | R01–R06 / LF-5 |
| AC-08 | Humano + Claude Code leem 20–30 conversas sintéticas executadas, registram os três modos de falha com denominador no caderno; sem antecipar resultado ou formato de dataset | R04, R05 / LF-6 |

Gates com banco usam **`oncology_langfuse_test`**, validando banco/host
local antes de reset, com um worker e restauração do backend cotidiano
inclusive em falha, sem editar persistentemente o `.env` do usuário
([detalhamento §5](../../LANGFUSE/detalhamento_execucao.md)).
`smoke_ingestion_changed.py` nunca roda na dev DB de trabalho. Resíduos
`t010-*`/`t011-*` e configurações de autonomia são tratados somente no
destino isolado; não normalizar a demo compartilhada para a suíte.

Checkpoints: **LF-0 → revisão humana antes de qualquer instrumentação**;
LF-1 → revisão da prova curta; LF-5 → revisão antes de LF-6. AC-08 encerra
o diagnóstico depois de LF-6, não é um resultado exigível antes dessa
sessão. A prova AC-01 está registrada em [analysis.md §8](analysis.md),
com refinamentos do SDK para revisão humana. AC-02..AC-08 permanecem
pendentes; testes parciais LF-1 não substituem os gates LF-5.
