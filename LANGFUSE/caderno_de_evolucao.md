# Caderno de evolução — Langfuse e plataforma

Criado em 2026-09-09. Estado: estrutura para preencher durante as aulas. Nenhuma medição ou melhora foi confirmada nesta entrega.

Usar com o [plano do curso](plano_curso_pratico.md). Os campos “pendente” não são resultados negativos; indicam trabalho ainda não executado. Ao retomar uma sessão, ler o último registro e continuar da primeira atividade pendente.

## 1. Progresso e próxima ação

| Etapa | Estado | Evidência/registro |
|---|---|---|
| Planejamento do curso | Concluído | Plano e revisão de consistência nesta pasta |
| Fase 1 — Observabilidade | Pendente | Começar por P1-01 do plano técnico |
| Aula 1 — Estado inicial | Pendente | Pode começar junto a P1-01 |
| Aula 2 — Leitura de traces | Pendente | Depende da fase 1 aceita |
| Aula 3 — RAG/contexto | Pendente | Depende da captura validada |
| Fase 2 — Avaliação | Pendente | P2-01 a P2-07 |
| Aula 4 — Qualidade | Pendente | Depende da fase 2 aceita |
| Aula 5 — Experimento | Pendente | Candidato e ambiente de comparação preparados |
| Fase 3 — Prompts | Pendente | P3-01 a P3-06 |
| Aula 6 — Troca/reversão | Pendente | Depende da fase 3 aceita |
| Laboratório RAGFlow + Elasticsearch | Opcional, pendente | Instalação informada; inventário e comparação por fazer |

Próxima atividade de ensino: escolher os seis casos e completar a definição de bom atendimento. Próxima atividade técnica: P1-01. Um registro de aula contém data, atividade, o que você conseguiu explicar, dúvida restante e próximo passo.

## 2. Fotografia inicial

| Campo | Valor |
|---|---|
| Data/hora e fuso da captura | Pendente |
| Commit e identificação de alterações locais | Pendente |
| Ambiente e destino do banco, sem credenciais | Pendente |
| Modelos/configurações de geração e embeddings | Pendente |
| Versões/hashes dos prompts efetivos | Pendente |
| Snapshot/hash e quantidade de Q&A, documentos e filhos ativos/indexados | Pendente |
| Configuração N5/governada, debounce e janela de veto | Pendente |
| Versões Langfuse servidor/SDK | Pendente |
| Dataset/revisão, split e fixtures | Pendente |
| Data de referência e ofertas de agenda | Pendente |
| Definição de bom atendimento e fatos críticos | Pendente — Aula 1 |
| Limites de custo/tempo para comparação | Pendente — fixar antes do experimento |

## 3. Ficha de caso observado

Copiar esta ficha para cada caso. A expectativa deve apontar uma referência verificável; não exigir uma frase exata quando diferentes respostas corretas forem possíveis.

| Campo | Preenchimento |
|---|---|
| Caso/revisão | Pendente |
| Origem | Uso sintético observado / cenário controlado |
| Pedido e sequência de mensagens necessária | Pendente |
| Resultado esperado e referência | Pendente |
| Resposta realmente enviada | Pendente |
| Conversa/trace/observação/mensagem | Pendente |
| Caminho e mecanismo efetivos | Pendente |
| Falha percebida | Pendente |
| Critério afetado e gravidade | Pendente |
| Etapa suspeita e evidência disponível | Pendente |
| Estado do diagnóstico | Sem causa confirmada / hipótese / confirmado por experimento |
| Próxima verificação | Pendente |

Uma informação existente na sessão pode estar ausente no request do modelo. Guardar esse contraste quando relevante. Se faltar telemetria, registrar a lacuna e buscar confirmação na aplicação antes de atribuir causa.

## 4. Fila inicial de investigações

As entradas abaixo são hipóteses motivadas pela leitura do código, sem frequência ou impacto medidos. A ordem de execução será revista após o baseline.

| ID | Hipótese | Verificação que pode confirmar ou refutar | Estado |
|---|---|---|---|
| H01 | O recorte automático de mensagens prejudica a continuidade em parte dos casos | Comparar histórico necessário com request do turno que repetiu uma pergunta | A investigar |
| H02 | A posição do primeiro resultado direciona alguns pedidos para o caminho inadequado | Comparar referência correta, ranking, caminho escolhido e saída | A investigar |
| H03 | Parte do fallback é pouco útil porque faltam dados/contexto na sua entrada | Inspecionar o request de `ai.n5_free` e julgar a resposta conforme a informação recebida | A investigar |
| H04 | Uma resposta ruim pode vir do documento/template ou da troca clínica, sem composição livre | Conferir origem do texto, antes/depois do reranking e envio | A investigar |
| H05 | Parte da lentidão percebida pode estar fora da chamada principal de geração | Separar etapas, debounce, janela, polls e exibição no cliente | A investigar |

Para priorizar, registrar **impacto, frequência observada com denominador, evidência disponível e esforço da correção**. Se o problema for ausência de trace, resolver a cobertura necessária ao diagnóstico. Problemas de dados, recuperação e contexto seguem para a etapa responsável.

## 5. Ficha de experimento

```text
Experimento / data:
Problema e casos que o demonstram:
Hipótese e resultado previsto:
O que poderia refutar a hipótese:
Baseline (commit, modelos, prompts, corpus):
Candidato e única variável principal alterada:
Especificação/decisão aplicável à mudança:
Dataset/revisão e casos de elaboração:
Reserva de conferência final, sem uso na elaboração:
Fixtures, referência de data e restauração entre variantes:
Juiz/modelo/rubrica e calibração:
Repetições, concorrência e condições da máquina:
Critérios críticos e limites de custo/tempo, definidos antes:
Links/IDs das execuções e traces:
Casos que melhoraram:
Casos que pioraram:
Erros de execução e inconclusivos:
Custos de atendimento, ingestão e avaliação, separados:
Tempos e quantidade de observações:
Resultado da conferência final:
Decisão: adotar / investigar mais / descartar
Justificativa sustentada pelos casos:
Versão efetivamente verificada após eventual ativação:
Procedimento e verificação de reversão:
Próxima ação:
```

## 6. Relatório por caminho

Duplicar a tabela para cada execução. Informar contagens e denominadores antes das porcentagens. Para recuperação, incluir só casos com referência julgada; para qualidade, apresentar inconclusivos e erros separadamente.

| Medida | Reaproveitamento | Guided booking | Fallback livre |
|---|---|---|---|
| Casos executados / previstos | Pendente | Pendente | Pendente |
| Casos com falha crítica / avaliados | Pendente | Pendente | Pendente |
| Distribuição 0/1/2 de utilidade | Pendente | Pendente | Pendente |
| Distribuição 0/1/2 de continuidade | Pendente | Pendente | Pendente |
| Distribuição 0/1/2 de consistência | Pendente | Pendente | Pendente |
| Distribuição 0/1/2 de clareza | Pendente | Pendente | Pendente |
| Inconclusivos / erros de execução | Pendente | Pendente | Pendente |
| Referência encontrada / casos elegíveis (`Hit@8`) | Pendente | Pendente | Pendente |
| Tempo de processamento / até envio | Pendente | Pendente | Pendente |
| Custo conhecido / chamadas com uso desconhecido | Pendente | Pendente | Pendente |

O caminho da comparação é o de origem do caso no baseline; registrar transições de caminho do candidato à parte. Satisfação e resolução declarada são registradas por sessão, com número de respondentes, fora desta tabela de turnos.

## 7. Encerramento de aula

```text
Aula / data:
Pré-requisito técnico verificado:
Caso analisado:
O que consegui explicar com minhas palavras:
Evidências salvas:
Dúvida que ainda tenho:
Atividade concluída ou pendente e motivo:
Próxima aula/ação:
```
