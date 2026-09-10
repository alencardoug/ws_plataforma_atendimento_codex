# Contratos e roteiro de execução — Langfuse local / N5

Data: 2026-09-09. Complementa o [plano principal](plano_implementacao.md).

> **Parcialmente vigente (revisto em 2026-09-10).** Os **contratos de
> observação do §3** (identidade, nomes, payloads, scores, dedup,
> fronteiras de transação) continuam a referência para a instrumentação —
> ajustar só os endpoints para Langfuse **Cloud**. O **§5** (DB de teste
> isolada `oncology_langfuse_test`) continua obrigatório. O **§6**
> (avaliação) e o **§7** (prompts), mais o split do dataset, são
> reavaliados **após a Fase 0** de `plano_implementacao.md` — não
> implementar como estão. "Três fases" virou "Fase 0 → reavaliar".

Este documento fecha decisões necessárias para iniciar o desenvolvimento das três fases. Valores de timeout, lotes e critérios de avaliação abaixo são padrões propostos para este projeto, não limites oficiais do Langfuse nem resultados de benchmark. Mudanças justificadas devem ser registradas no pacote SDD da fase correspondente.

O [plano do curso prático](plano_curso_pratico.md) liga estas entregas ao aprendizado do usuário. A preparação de cada aula produz um roteiro de cliques/comandos validado na versão instalada e usa o [caderno de evolução](caderno_de_evolucao.md); o curso não substitui os gates técnicos.

## 1. Entrada no desenvolvimento e limites de escopo

- Começar por P1-01 do plano: especificação, plano técnico, tarefas, aceitação e análise de consistência. As fases 2 e 3 também terão seus artefatos antes de código; usar os próximos números disponíveis, sem abrir uma feature apenas por existir uma numeração sugerida.
- A sessão autoriza o planejamento no checkout atual, local, com foco N5, conteúdo simulado sem nova camada de mascaramento e métricas no Langfuse. A presente revisão não inicia a implementação.
- Formalizar a necessidade dos componentes de observabilidade nos artefatos de autoridade. Redis/Valkey e ClickHouse atendem ao Langfuse; não serão dependências de negócio do backend.
- Manter dados, portas, projeto Compose, configurações N5 e fluxos de envio existentes. Capturar esses valores antes dos testes para verificar sua restauração.
- Alterações de qualidade nos prompts podem ser experimentadas na fase 2 e selecionadas na fase 3. Mudanças nas regras de agenda, contexto oferecido ao modelo, autonomia ou comportamento de negócio descobertas pelos experimentos exigem seu próprio tratamento SDD.
- Não condicionar a instrumentação à correção de todos os problemas históricos de conteúdo. Registrar problemas existentes separadamente dos defeitos introduzidos pela integração.

## 2. Configuração e operação da fase 1

### 2.1 Serviços e configuração mínima

Serviços propostos no profile `langfuse`: `langfuse-web`, `langfuse-worker`, `langfuse-db`, `langfuse-clickhouse`, `langfuse-redis` e `langfuse-s3`. Todos com volumes próprios quando necessário; aplicação e banco de atendimento continuam os atuais.

| Configuração | Padrão/decisão |
|---|---|
| `LANGFUSE_TRACING_ENABLED` | `false` na configuração versionada; `true` no ambiente local que usar a integração |
| `LANGFUSE_BASE_URL` | `http://langfuse-web:3000` dentro do Compose; explicitamente local, sem fallback para Cloud |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | Geradas na inicialização local; guardadas no `.env` existente |
| `LANGFUSE_ENVIRONMENT` | `local-n5`; testes usam `local-test` e avaliações `local-eval` |
| Identificação do código | Commit e identificação do conteúdo alterado quando o checkout estiver sujo; não enviar diffs como payload |
| Amostragem de observações | 100% das operações relevantes; polls sem trabalho não criam observações de IA |
| Lote de exportação | Intervalo alvo de 2 s e fila limitada a 2.048 itens; ajustar aos parâmetros efetivamente suportados pelo SDK fixado |
| Exportação | Timeout de rede de 2 s, retries limitados, sem espera por exportação no atendimento |
| Encerramento normal | Flush/shutdown com teto de 5 s; perda residual é registrada como limitação de entrega |
| Recursos pagos adicionais | Nenhum avaliador automático por LLM na fase 1 |

O Compose deve continuar sendo interpretado e executado sem chaves Langfuse quando o profile estiver desligado. Não usar interpolação obrigatória de variáveis exclusivas do profile que faça o Compose comum falhar antes de iniciar.

Criar um comando de inicialização local idempotente, documentado no runbook. Ele gera apenas chaves/configurações ausentes, configura usuário/organização/projeto, preserva valores existentes e não imprime segredos. A validação de credenciais e a espera pela prontidão do Langfuse pertencem a esse comando, não ao atendimento HTTP.

### 2.2 Prova técnica curta antes da instrumentação ampla

P1-02 deve validar primeiro: uma observação, uma chamada com consumo, um score reapresentado sem duplicação e uma consulta pelo painel/API. Fixar então as versões exatas das imagens e do SDK, sem tags `latest`.

Alvo inicial: servidor v4 e SDK Python v4 com suporte à ingestão atual. A documentação consultada identifica SDK Python 4.7.0 ou posterior para a ingestão v4 sem os atrasos do caminho antigo. Verificar a matriz self-hosted e as versões realmente disponíveis; não escolher apenas pelo número major. Consultar observações e métricas pelas APIs atuais suportadas pelo conjunto fixado. [Compatibilidade](https://langfuse.com/docs/compatibility).

Se a versão escolhida não suportar a capacidade usada no contrato, resolver a compatibilidade nessa prova curta. Não avançar com uma instrumentação completa que dependa de painel ou API incompatível. Esse é um teste de implementação previsto, não uma decisão de produto deixada em aberto.

## 3. Contrato de observações N5 — versão 1

### 3.1 Identidade e execução

| Campo | Contrato |
|---|---|
| `schema_version` | `1` em observações e scores definidos pela aplicação |
| `session_id` | UUID da conversa como string |
| `turn_id` | UUID da mensagem mais recente do grupo selecionado pelo debounce |
| `trace_id` | `turn_id` sem hífens para o turno automático |
| `attempt_id` | UUID novo por execução efetiva do processamento; não criar a cada poll |
| `observation_id` | ID próprio de cada operação; chamadas distintas não compartilham ID |
| `triggering_message_id`, `selected_message_ids` | Mensagem final e lista ordenada das mensagens do turno |
| IDs de negócio | `ai_generation_id`, `prior_generation_id`, `retrieval_run_id`, `pending_id`, `message_id`, quando existirem |
| `execution_origin` | `customer_poll`, `customer_typing`, `operator_poll` ou `operator_detail` |
| `n5_path` | `reuse_answer`, `guided_booking` ou `freeform_fallback`, somente após decisão N5 |
| `fallback_reason` | `initial_not_answer` ou `weak_clinical_shortcut`, acompanhado do status/score original |
| `mechanism` | Valor realmente utilizado, incluindo `ungoverned_n5` e `governed_autonomy` |
| Configuração observada | Switches relevantes, modo efetivo, debounce e janela; informação capturada não altera esses valores |
| Datas | ISO 8601 em UTC; interface pode apresentar em America/Sao_Paulo |

Executar `n5.process_turn` depois de o gatilho decidir realizar trabalho e antes da recuperação, encerrando após decidir/abrir a pendência ou registrar a falha. Incluir tentativa inicial e eventual fallback como operações filhas. Não mover a geração para o POST que recebe a mensagem do cliente: isso reintroduziria a espera síncrona que o código já evita.

O span principal registra exceções antes de os wrappers existentes absorvê-las. Uma falha na telemetria não pode chamar a função de negócio pela segunda vez. Proteger entrada, atualização e saída do adaptador, preservando o retorno ou a exceção original da aplicação.

### 3.2 Nomes e payloads

| Observação | Tipo lógico | Entrada/saída principal |
|---|---|---|
| `n5.process_turn` | Operação completa | Mensagens selecionadas; resultado da decisão, IDs e eventual erro |
| `rag.retrieve` | Recuperação | Query; evidências ordenadas, scores, trechos e documentos expandidos |
| `rag.admin_search`, `rag.clinical_search` | Etapa | Parâmetros da busca; IDs/quantidades e tempo de cada consulta |
| `ai.answer`, `ai.clinical_rerank`, `ai.date_intent`, `ai.n5_free` | Geração | Mensagens efetivamente enviadas ao provedor, resposta recebida, modelo, uso e erro |
| `ai.embedding` | Embedding | Textos, finalidade e modelo; dimensão, quantidade, uso e erro |
| `scheduling.resolve`, `scheduling.select_offer` | Etapa | Parâmetros/ofertas; resultado, IDs selecionados e causa de fallback |
| `autonomy.decision` | Etapa | Geração inicial, condições consultadas; caminho e mecanismo escolhidos |
| `autonomy.pending_opened` | Evento confirmado | Pendência, geração, abertura, vencimento e duração |
| `autonomy.pending_resolved` | Evento confirmado | Pendência, estado terminal, instante e ator quando aplicável |
| `message.sent` | Evento confirmado | Mensagem final, geração, fonte autônoma e timestamp |

São nomes do contrato da aplicação; o adaptador os mapeia aos tipos de observação disponíveis no SDK fixado. Usar observações de etapa quando não existir um tipo especializado. Somente chamadas reais ao provedor carregam consumo faturável.

A resposta recebida do modelo pode ser diferente do texto enviado ao cliente depois de parsing ou reranking. Preservar ambos nos pontos correspondentes, sem reconstituir o request a partir de um prompt que possa ter mudado posteriormente.

### 3.3 Correlação tardia e transações

- Em `send_customer_message()`, a mensagem recebe ID via flush antes de `advance_guided_booking()`. Embeddings executados ali podem usar esse ID e a sessão; se outra mensagem fechar o grupo do debounce, o turno posterior referencia esse trace sem copiar seu custo.
- Se uma operação fora do gatilho automático não tiver `triggering_message_id`, usar trace próprio e finalidade explícita. Não juntar gerações manuais ao turno N5 apenas por ocorrerem na mesma conversa.
- O resolvedor de envio recupera a geração e sua mensagem disparadora para reconstruir `trace_id`. Não manter contexto aberto durante a janela nem exigir uma coluna adicional apenas para esse vínculo.
- Publicar eventos de negócio somente depois do commit correspondente. Congelar antes os campos necessários em tipos simples; o exportador nunca recebe uma sessão SQLAlchemy nem consulta o banco em outra thread.
- Traces de chamadas ao provedor representam operações realmente executadas, mesmo que a transação posterior falhe. Eles podem existir sem mensagem enviada; isso não é um envio confirmado.
- Publicações são locais e enfileiradas. Nenhuma requisição de rede aguardada fica dentro de um commit ou enquanto se segura uma trava para enviar mensagem.

### 3.4 Scores e deduplicação

Usar `score_id` determinístico, por exemplo UUIDv5 de um namespace fixo e dos componentes abaixo. Fixar também nome e timestamp original. A documentação atual exige coincidência de ID, nome e data do timestamp para atualizar um score sem criar outro; ID isolado não basta. Preservar o timestamp completo em UTC também simplifica a correlação. [Atualização de scores](https://langfuse.com/docs/evaluation/evaluation-methods/scores-via-sdk).

| Score | Unidade/tipo | Chave lógica | Timestamp original |
|---|---|---|---|
| `n5.turn_started` | Turno / booleano verdadeiro | `turn_id + nome` | Criação da mensagem disparadora |
| `n5.path` | Decisão / categoria dos três caminhos | `turn_id + nome` | Criação da mensagem disparadora |
| `n5.fallback_started` | Decisão / booleano 0 ou 1 | `turn_id + nome` | Criação da mensagem disparadora |
| `n5.fallback_reason` | Fallback / categoria | `turn_id + nome` | Criação da mensagem disparadora |
| `n5.pending_opened` | Pendência / booleano verdadeiro | `pending_id + nome` | `opens_at` |
| `n5.pending_outcome` | Pendência / `SENT`, `PAUSED`, `EDITED`, `TAKEN_OVER` | `pending_id + nome` | `resolved_at` |
| `n5.sent` | Mensagem / booleano verdadeiro | `message_id + nome` | Criação da mensagem enviada |
| `n5.response_latency_ms` | Mensagem / número | `message_id + nome` | Criação da mensagem enviada |

`n5.fallback_started` é emitido para toda decisão N5: 0 nos dois caminhos de reaproveitamento e 1 quando a chamada livre é iniciada, mesmo se ela falhar. A média fornece a frequência de fallback entre decisões observadas. Turnos que falham antes de chegar à decisão entram na contagem de falhas, sem receber um falso valor 0.

Separar abertura de desfecho terminal. Não atualizar um score de estado de `PENDING` para `SENT`: uma abertura atrasada poderia sobrescrever um desfecho. Os eventos mostram a sequência e o score terminal é publicado somente quando houver resolução confirmada. A ausência de desfecho significa **sem desfecho observado**, pois pode decorrer de espera ou perda de telemetria. O painel não deve anunciá-la como contagem autoritativa de pendências atuais.

Testar reapresentação no mesmo dia, no dia seguinte e com chegada fora de ordem, mantendo os timestamps originais. Para custos, IDs de operações distintas continuam distintos: deduplicar transporte não pode esconder uma chamada ao modelo que realmente ocorreu duas vezes.

## 4. Dashboard e aceite operacional da fase 1

### 4.1 Widgets mínimos

- Contagem de turnos e mensagens N5, por dia e caminho.
- Frequência e motivo de fallback, com falhas anteriores à decisão apresentadas separadamente.
- Tokens/custo de chamadas por modelo e finalidade; custo por conversa na inspeção da sessão.
- p50/p95 de `n5.process_turn` e das etapas; latência até envio a partir de `n5.response_latency_ms`.
- Aberturas e desfechos observados, além da sequência completa em cada trace.
- Erros por observação/etapa e acesso aos respectivos turnos.

Versionar a configuração exportável dos widgets ou uma receita precisa para criá-los, incluindo fonte, filtro, agregação e nome de campo. Usar nomes/ambiente/atributos efetivamente consultáveis na versão escolhida. Não encerrar a fase com a recomendação genérica de montar o dashboard depois.

### 4.2 Padrões de validação

| Verificação | Critério inicial |
|---|---|
| Primeira inicialização | Serviços saudáveis e prova técnica em até 5 min após as imagens estarem disponíveis; se exceder, diagnosticar antes da instrumentação ampla |
| Disponibilidade das observações | Em stack saudável, API/painel mostram cada operação de teste em até 30 s após flush; timeout finito |
| Falha do Langfuse | Mesmos resultados funcionais com exportação desligada, servidor parado e erro do adaptador; nenhuma operação de negócio repetida |
| Impacto no atendimento | Comparar 30 turnos determinísticos equivalentes; aumento de p95 do processamento de até 100 ms ou 10% do baseline, o maior dos dois; medir separadamente do tempo de ingestão no painel |
| Integridade de custos | Para respostas de provedor controladas, valores de uso preservados e contabilizados uma vez; zero fictício e duplicação falham o teste |
| Reinício | Geração e envio posterior no mesmo trace, com estado confirmado e timestamps originais |
| Recursos | Roteiro com seis sessões, sem OOM/reinícios e sem fila crescendo continuamente; registrar pico de memória e espaço consumido |

Esses números são alvos de aceite propostos para a integração. Se a máquina não os atingir, registrar medição e corrigir o gargalo ou revisar o alvo com justificativa no SDD. Não transformar um timeout aumentado silenciosamente em aprovação. A capacidade de executar o teste na máquina é comprovada durante implementação.

## 5. Testes no checkout atual

Usar um banco chamado `oncology_langfuse_test` no PostgreSQL local, com configuração e dados de teste próprios. Um executor único deve preparar esse destino, executar as suítes e restaurar o backend cotidiano ao terminar, inclusive em falha ou interrupção tratável.

Sequência:

1. Registrar projeto Compose, destino normal do banco e configuração N5 em uso, sem imprimir credenciais.
2. Criar/preparar o banco descartável, aplicar migrations e carregar fixtures. Copiar conhecimento sintético já vetorizado quando compatível para evitar reembedding desnecessário.
3. Recriar temporariamente o backend com `DATABASE_URL` de testes, ambiente `local-test` e bootstrap de agenda desativado salvo quando o teste o exercitar. Não basta `restart`: a configuração é lida e os objetos de banco são mantidos em memória pelo processo.
4. Propagar o destino aos testes, aos helpers SQL e aos comandos Compose disparados pelo Playwright. Validar `current_database()` e host local antes de qualquer reset; recusar banco que não seja o destino explicitamente previsto para testes.
5. Executar suítes com um worker e sem atendimento manual simultâneo. O mesmo frontend passa a acessar o backend temporariamente conectado à base de testes.
6. Em bloco de finalização, recriar o backend com a configuração normal e conferir `/ready`, banco e configuração N5. Não editar persistentemente o `.env` do usuário para fazer a troca.

Uma interrupção abrupta do host pode impedir a finalização. O runbook deve ter um comando de restauração da configuração normal. Não criar segunda instalação cotidiana da aplicação nem exigir trabalho manual para selecionar o banco a cada suíte.

## 6. Contrato de avaliação da fase 2

### 6.1 Dataset e fixtures

Entregar `n5-baseline-v1`: 30 casos, sendo 10 de cada caminho. Separar 24 para elaboração/comparação e 6 para conferência final, com 2 de cada caminho nessa reserva. A divisão é pequena e serve a regressão inicial, não a estimativa estatística de qualidade geral.

Manter os casos em JSONL versionado e sincronizá-los idempotentemente com um dataset Langfuse. Isso preserva os cenários se os volumes locais forem recriados. Usar ID estável por caso e hash de conteúdo; alteração semântica gera nova revisão/snapshot do dataset.

| Campo do caso | Conteúdo |
|---|---|
| `case_id`, `revision`, `split` | Identidade, versão e elaboração/conferência final |
| `mode` | `scenario` para reexecutar a aplicação ou `snapshot` para avaliar uma resposta capturada |
| `messages` | Sequência de mensagens e papéis necessária ao caso |
| `fixture_id`, `fixture_version` | Conhecimento, ofertas e estado de conversa que preparam o cenário |
| `reference_time` | Referência de data/hora da comparação, quando relevante |
| `expected_path` | Um dos três caminhos N5 |
| `expected_facts` | Dados de referência e resultados estruturados esperados; não necessariamente uma frase literal |
| `critical_checks` | Lista dos requisitos objetivos que não podem falhar nesse caso |
| `quality_criteria` | Critérios qualitativos aplicáveis |
| `source_trace_id`, `source_observation_id` | Proveniência quando o caso veio de uma conversa, sem ser a única fonte dos dados necessários |

Para agenda, definir ofertas por aliases de fixture e verificar IDs/dados correspondentes. Os dois candidatos usam o mesmo estado inicial e a mesma referência de data. Quando funções SQL dependentes do relógio real impedirem replay de uma data passada, reconstruir as ofertas relativas à nova referência e registrar uma nova execução/fixture; não apresentar cenários diferentes como comparação idêntica.

Usar restauração de fixtures entre casos/candidatos. Uma opção escolhida no candidato A não pode desaparecer do cenário B como efeito da execução anterior. Para snapshots, avaliar a mensagem efetivamente enviada e suas referências capturadas, distinguindo-a das saídas intermediárias.

Para os exercícios de diagnóstico de recuperação, incluir em `expected_facts` os IDs estáveis de Q&A/documentos pais relevantes e aplicar `Hit@k` somente aos casos com referência revisada, usando o mesmo `k` entre variantes (inicialmente 8). P2-01/P2-05 formalizam essas verificações. `expected_path` registra o caminho de referência do caso; exigir esse caminho como regra objetiva somente quando listado em `critical_checks`. Uma melhoria de recuperação pode mudar o caminho efetivo: manter a comparação pelos mesmos casos e registrar a transição, sem ocultá-la nem classificá-la automaticamente como erro.

### 6.2 Rubrica inicial

Regras objetivas retornam `PASS`, `FAIL` ou `NOT_APPLICABLE`. Critérios qualitativos usam 0, 1 ou 2:

| Critério | 0 | 1 | 2 |
|---|---|---|---|
| Utilidade | Ignora a solicitação ou não ajuda | Responde parcialmente/próximo passo vago | Responde ou pede esclarecimento específico que permite avançar |
| Continuidade | Contradiz/ignora contexto necessário disponível | Usa parte do contexto com repetição evitável | Usa o contexto disponível de forma consistente |
| Consistência com referências | Afirma dado incompatível com a referência | Imprecisão sem contradição crítica | Dados específicos consistentes com a referência |
| Clareza e concisão | Confusa ou com instrução interna inadequada | Compreensível, mas com excesso/repetição | Clara e proporcional ao pedido |

Se faltar referência para julgar um critério, registrar `INCONCLUSIVE`, com categoria de motivo. Não converter inconclusivo em nota zero. No fallback livre, avaliar detalhes específicos contra os dados disponíveis; não exigir evidência/citação inexistente no contrato desse caminho.

`critical_checks` possíveis: formato estruturado, escolha de oferta, consistência de data/preço, preservação de dado fornecido e ausência de envio proibido pelo cenário. Definir explicitamente quais se aplicam a cada caso. Uma falha crítica não deve ser compensada por uma média alta de cordialidade.

Usar um juiz LLM inicialmente, com modelo configurável e fixado no manifesto da execução, saída estruturada e critérios versionados. Registrar scores, categoria e evidência observável curta; não pedir nem persistir raciocínio interno. Conferir 12 exemplos revisados, buscando ao menos 10 concordâncias na classificação aceitável/inaceitável antes de usar a classificação automática como filtro de promoção. Esse é um alvo de calibração do projeto, não uma medida científica de validade.

Para essa calibração, `ACCEPTABLE` exige todos os requisitos críticos aplicáveis aprovados e notas de pelo menos 1 em todos os critérios qualitativos aplicáveis. Uma falha crítica ou nota 0 resulta em `UNACCEPTABLE`; referência obrigatória ausente resulta em `INCONCLUSIVE`, salvo se já existir uma falha comprovada. Usar 12 exemplos com referência suficiente, incluindo bons e ruins; reportar inconclusivos do juiz separadamente e não contá-los como concordância. Essa classificação básica calibra o avaliador; promover um candidato exige também a comparação do §6.4.

### 6.3 Runner e custos

Implementar um executor local com três operações: sincronizar dataset, avaliar snapshots e comparar variantes. A forma exata do CLI fica no runbook, com exemplos copiáveis. Defaults: uma repetição por caso, concorrência 1 e nenhuma avaliação periódica habilitada automaticamente.

Para cenários completos, executar os caminhos reais da aplicação no banco de testes, incluindo requisições/etapas que produzem o resultado N5. Isolar a configuração de cada variante em processo próprio, evitando reaproveitar settings ou conexões com o modelo/banco da variante anterior. Mudança do modelo global vale para as etapas que o código já configura globalmente; não inventar configuração por etapa sem especificá-la.

Preparar uma fronteira mínima de resolução dos quatro prompts locais para permitir overrides somente no contexto do experimento. Preservar textos e versões existentes no uso normal. A fase 3 estende essa mesma fronteira ao Langfuse; não fazer duas refatorações concorrentes.

Cada execução possui manifesto: ID, dataset/snapshot, commit/conteúdo de código, configuração dos modelos, versões/hash dos prompts, fixture/data, juiz/rubrica, repetições e horário original. Scores usam chave `run_id + case_id + repetição + critério` e timestamp original da execução em reapresentações.

Reaproveitar julgamentos somente quando entrada semântica, resposta, referências, juiz e rubrica forem idênticos. Não usar IDs transitórios como parte do conteúdo semântico. Não reutilizar uma resposta antiga quando o propósito for gerar uma nova amostra para comparar variantes.

O relatório deve mostrar por caminho: regras aprovadas/reprovadas, qualidade por critério, inconclusivos, casos que pioraram, custo e tempo. Erros de execução ficam separados de notas de qualidade. Não deixar avaliações de `local-eval` dispararem novas avaliações recursivas.

### 6.4 Aceite da ferramenta e seleção de candidatos

**Aceite da fase 2:** runner reproduz os casos, isola os dados, registra custos e detecta exemplos controlados bons/ruins conforme critérios. Entregar uma comparação real de duas variantes e a calibração do juiz. Falhas de qualidade do baseline podem aparecer no relatório; não é requisito corrigir o produto inteiro para entregar a ferramenta de avaliação.

**Seleção de uma mudança de prompt:** nenhuma nova falha crítica nos casos comparados; nenhuma queda não explicada nos casos de conferência final; melhorias demonstradas no critério alvo e custo/latência apresentados. Se o resultado for ambíguo, a versão continua candidata. Não promover apenas porque a média geral subiu. A seleção é uma decisão explícita do usuário, não um comando do avaliador.

## 7. Contrato de prompts da fase 3

### 7.1 Catálogo e fronteira de carregamento

Nomes lógicos iniciais: `cc_n5_free`, `cc_rag_answer`, `cc_clinical_rerank`, `cc_date_intent`. Versionar apenas esses quatro prompts usados; manter formato/parsing, decisões de envio e templates determinísticos nos contratos de código.

A resolução retorna um objeto próprio da aplicação com conteúdo renderizável, nome, versão efetiva, hash, origem (`local`, `langfuse`, `local_fallback`) e variáveis esperadas. Objetos do SDK Langfuse ficam no adaptador. Ao registrar uma geração, usar a versão realmente resolvida; não manter o hash da antiga constante N5 quando outro texto tiver sido utilizado.

`FORMAT_INSTRUCTION` continua controlado pelo código. Registrar seu hash e o hash da mensagem de sistema completa nos traces. Na publicação inicial, os prompts renderizados devem ser equivalentes aos textos atuais sobre casos de referência, incluindo escaping JSON e variáveis do reranking. A migração para gestão não deve retocar o conteúdo silenciosamente.

### 7.2 Labels, cache e fallback

| Decisão | Regra inicial |
|---|---|
| Seleção cotidiana | Label explícita `ativo`; nunca usar implicitamente `latest` |
| Experimentos | Versões numéricas fixas no manifesto; label `candidato` serve para identificação |
| Promoção | Uma mudança de prompt por operação, associada ao relatório da comparação |
| Snapshot do turno | Resolver o conjunto necessário no início do processamento e reutilizá-lo durante o turno |
| Cache | TTL de 60 s para seleção por label; registrar a versão retornada, inclusive quando houver cache |
| Busca sem cache | Timeout de 500 ms por prompt, sem retries; no máximo 2 s para o catálogo inicial de quatro prompts |
| Indisponibilidade | Última versão válida em cache quando disponível; caso contrário, snapshot local documentado |
| Fora do Langfuse | Opção de configuração para usar os prompts locais; avaliação/tracing têm configuração independente |

Pré-aquecer o catálogo no startup sem tornar a disponibilidade do Langfuse obrigatória. Resolver as versões antes de começar o trabalho que mantém transações/travas de recuperação ou envio; não buscar novamente a label no meio do mesmo turno.

Validar tipo do prompt, variáveis requeridas, conteúdo não vazio e compatibilidade com o compilador. Resposta inválida, projeto inacessível ou versão ausente aciona fallback identificado no trace. Cache expirado pode retornar uma versão anterior durante a atualização em background; confirmar a adoção por observação posterior, não somente pelo clique na label. [Cache de prompts](https://langfuse.com/docs/prompt-management/features/caching).

### 7.3 Publicação, ativação e reversão

1. Publicar versões iniciais idempotentemente: conteúdo igual não deve gerar uma nova versão em todo startup. Guardar o catálogo e um snapshot local versionado dos prompts aprovados.
2. Editar o candidato no Langfuse e executar a comparação da fase 2 usando sua versão numérica.
3. Registrar nome, versão anterior, candidata e relatório. Ativar movendo `ativo` explicitamente para a versão escolhida. Publicar um candidato não modifica a label ativa por si só.
4. Exportar o conteúdo selecionado para o snapshot local de recuperação e registrar seu hash. O fallback local precisa ser acessível no container pelo volume já utilizado para prompts; falha da exportação deve ser visível, sem alegar que a recuperação foi atualizada.
5. Após o TTL, gerar um turno controlado e verificar a versão efetivamente adotada; a revalidação pode exigir o próximo acesso. O runbook prevê reinício do backend para invalidar caches quando for necessária reversão imediata, sem rebuild da imagem.
6. Para reverter, mover a label à versão anterior, restaurar o snapshot correspondente e confirmar nova observação. O resultado da reversão não se resume à atualização da label.

Langfuse suporta recuperação por versão ou label; usar esses recursos com a política explícita acima. [Versões e labels](https://langfuse.com/docs/prompt-management/features/prompt-version-control).

**Aceite da fase 3:** publicar, comparar, ativar, verificar e reverter uma versão; comprovar equivalência inicial, uso da versão efetiva e funcionamento com servidor parado/cache vazio e snapshot local. Não requer que um prompt candidato seja melhor para comprovar que a gestão funciona.

## 8. Tarefas das fases 2 e 3

| ID | Entrega | Dependência/fechamento |
|---|---|---|
| P2-01 | Especificação de avaliação e contratos analisados | Fase 1 aceita |
| P2-02 | Dataset de 30 casos, divisão e fixtures versionadas | P2-01; sincronização idempotente demonstrada |
| P2-03 | Fronteira de prompts locais e variantes de experimento | P2-01; baseline mantém comportamento/textos |
| P2-04 | Runner de cenários/snapshots e manifestos | P2-02/03; isolamento e reexecução comprovados |
| P2-05 | Verificações determinísticas e juiz calibrado | P2-04; 12 exemplos revisados e relatório |
| P2-06 | Scores de feedback e painel/relatório de qualidade | P2-05; sessão e geração com unidades corretas |
| P2-07 | Comparação real, custos e encerramento SDD | P2-06; gates aplicáveis e evidências |
| P3-01 | Especificação da gestão/carregamento de prompts | Fase 2 aceita |
| P3-02 | Catálogo Langfuse e publicação idempotente | P3-01; equivalência inicial verificada |
| P3-03 | Resolver, cache, fallback e snapshot por turno | P3-02; versão efetiva nos traces |
| P3-04 | Ativação, exportação local e reversão | P3-03; candidato não altera atendimento sozinho |
| P3-05 | Experimento e roteiro completo de troca/reversão | P3-04; falha/cache vazio cobertos |
| P3-06 | Runbook, gates e convergência final | P3-05 |

## 9. Revisão de prontidão do planejamento

| Lacuna encontrada na revisão | Resolução neste documento |
|---|---|
| Configuração e comportamento com profile desligado genéricos | §2 define defaults, comando de inicialização e prova técnica curta |
| Nomes e unidades das observações não consolidados | §3 define identidade, eventos, payloads e fronteiras de transação |
| ID sozinho tratado como suficiente para deduplicar scores | §3.4 fixa ID, nome e timestamp e separa abertura de desfecho terminal |
| “Montar dashboard” sem definição de entrega | §4 define widgets, filtros, medição e alvos de aceite |
| Testes no banco cotidiano poderiam apagar dados | §5 define seleção, validação e restauração automatizada do banco de testes |
| Avaliação detalhada em benefícios, mas sem contrato de execução | §6 define 30 casos, rubrica, runner, manifesto, calibração e critérios |
| Gestão de prompts sem procedimento operacional fechado | §7 define catálogo, carregamento, versões, cache, fallback e reversão |
| Fases 2/3 sem sequência de tarefas | §8 define tarefas, dependências e fechamento |

**Veredito:** planejamento suficientemente detalhado para iniciar desenvolvimento por P1-01. Não há necessidade de outra rodada de detalhamento conceitual antes dessa etapa. A formalização SDD, a fixação das versões, os testes e as medições são trabalho previsto da implementação; ainda não foram executados. Nenhum serviço, código de aplicação ou configuração em uso foi alterado por esta revisão.
