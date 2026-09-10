# Avaliação de integração do Langfuse

> Atualização em 2026-09-09: esta avaliação registra as premissas da análise inicial. A decisão atual do usuário é executar localmente no checkout existente, sem worktree, com prioridade no atendimento N5, captura do conteúdo simulado sem nova camada de mascaramento e uso do Langfuse para acompanhar métricas, aceitando duplicação. A recomendação atual e as fases estão no [plano de implementação local](plano_implementacao_local.md).

**Sim, dá para integrar o Langfuse, e vejo benefício concreto neste projeto.** Minha recomendação é começar com observabilidade de IA no backend, usando Langfuse Cloud e exportação controlada de dados. Hospedar a plataforma inteira agora teria um custo operacional consideravelmente maior.

Fiz uma revisão estática da arquitetura, dos fluxos de geração e RAG, embeddings, agendamento, autonomia, auditoria, avaliações, frontend e implantação, além de consultar a documentação oficial. Não alterei arquivos nem executei testes durante a avaliação; portanto, esta é uma avaliação de viabilidade, não uma integração validada.

## O que no código favorece a integração

| Área | Situação encontrada | Encaixe do Langfuse |
|---|---|---|
| Provedores de IA | Interface `GenerationProvider` e adaptador centralizado | Instrumentar chamadas sem espalhar dependências pelo domínio |
| Embeddings | Interface própria usada por RAG, ingestão e seleção de horários | Medir chamadas, duração e consumo nesses três contextos |
| RAG | Busca administrativa, busca clínica e expansão para documento pai explícitas | Visualizar cada etapa e seus resultados |
| Persistência | Gerações, buscas, evidências e mensagens possuem identificadores | Correlacionar execução técnica com registros do sistema |
| Prompts | Versionamento por hash do conteúdo | Comparar resultados entre versões |
| Feedback | Aceitação, edição, escalonamento e satisfação já registrados | Associar sinais de qualidade às execuções |

Os principais pontos estão em [providers.py](../app/customer_care/ai/providers.py), [embeddings.py](../app/customer_care/knowledge/embeddings.py) e [rag/service.py](../app/customer_care/rag/service.py).

A integração pode usar o SDK Python e instrumentação própria baseada em OpenTelemetry. **Não exige adicionar LangChain nem LlamaIndex.** [Documentação dos SDKs](https://langfuse.com/docs/observability/sdk/overview).

## Benefícios reais para este projeto

1. **Enxergar o custo completo de uma resposta.**

   Atualmente, `generate()` retorna tokens, mas reranking clínico, interpretação de datas e resposta N5 não propagam esse consumo nos respectivos retornos. O adaptador de embeddings também retorna apenas vetores. Uma resposta pode envolver várias chamadas e ter custo superior ao registrado na geração principal.

   Instrumentando todas essas chamadas, seria possível apurar consumo por operação e estimar custos por conversa e modelo. Os valores dependem da cobertura da instrumentação e da tabela de preços utilizada. [Tokens e custos](https://langfuse.com/docs/observability/features/token-and-cost-tracking).

2. **Descobrir onde está a lentidão.**

   Em [generate_draft()](../app/customer_care/ai/router.py), o cronômetro da geração começa depois da recuperação de evidências. Hoje há tempos separados, mas falta uma visão integrada de busca, embeddings, resolução dinâmica, geração e reranking.

3. **Investigar respostas inadequadas com contexto.**

   Seria mais fácil distinguir recuperação ruim, interpretação incorreta de data, escolha de horário, resposta do modelo e substituição pelo reranking clínico. Langfuse fornece a visualização; os pontos de instrumentação precisam representar essas decisões.

4. **Comparar mudanças com evidências.**

   O projeto já possui casos de avaliação, mas o fluxo atual é manual. Datasets e experimentos poderiam permitir comparar versões de prompt, modelo e recuperação sobre os mesmos casos. Isso seria uma evolução separada, com critérios próprios. [Conceitos de avaliação](https://langfuse.com/docs/evaluation/core-concepts).

5. **Relacionar qualidade técnica com intervenção humana.**

   Aceitação e edição de rascunhos podem virar scores vinculados à geração. A satisfação deve continuar associada à conversa, evitando atribuí-la automaticamente a uma única resposta. [Scores](https://langfuse.com/docs/evaluation/scores/overview).

## Viabilidade e limites

| Opção | Avaliação |
|---|---|
| **Langfuse Cloud** | Melhor ponto de partida: reduz a operação de infraestrutura, mas exige controlar dados enviados, retenção e consumo |
| **Self-hosted separado** | Tecnicamente viável; adequado se controle de armazenamento justificar manutenção e infraestrutura |
| **Self-hosted junto ao Compose atual** | Possível para desenvolvimento, porém aumenta bastante o ambiente e exige justificativa arquitetural |
| **Substituir a auditoria pelo Langfuse** | Incompatível com a exigência atual de fatos duráveis e auditoria imutável no sistema |
| **Permitir que avaliações alterem autonomia automaticamente** | Fora do escopo de observabilidade e das permissões atuais para esta solicitação |

O self-hosted envolve **Web, Worker, PostgreSQL, ClickHouse, Redis/Valkey e armazenamento S3 compatível**. Isso é relevante porque o projeto restringe Redis e infraestrutura distribuída sem necessidade demonstrada. Não é impossibilidade técnica, mas exige especificação e justificativa antes de implementação. [Arquitetura oficial](https://langfuse.com/self-hosting).

## Contras e cuidados específicos

- **Mais uma cópia de conteúdo potencialmente sensível.** Prompts contêm histórico e evidências. Eu começaria com metadados permitidos explicitamente, sem captura automática de argumentos, headers, tokens de acesso ou objetos de banco. Conteúdo textual exigiria política de exportação e mascaramento; raciocínio interno permaneceria excluído. [Mascaramento](https://langfuse.com/docs/observability/features/masking).
- **Instrumentação parcial pode enganar.** Trocar apenas o cliente de IA não revela buscas SQL, caminhos determinísticos nem decisões de autonomia.
- **Pode duplicar métricas existentes.** O projeto já calcula indicadores em [v3_queries.sql](../docs/metrics/v3_queries.sql). PostgreSQL deve continuar sendo a referência para esses indicadores de negócio.
- **Há custo e manutenção.** Cloud possui franquias e limites; self-hosted consome infraestrutura e trabalho operacional. Avaliações com LLM acrescentam consumo do provedor. [Preços](https://langfuse.com/pricing).
- **Exportação precisa sobreviver ao ciclo da aplicação.** O deployment documenta Cloud Run com escala a zero. Seria necessário validar envio em lote, encerramento e entrega dos eventos, sem bloquear os polls que movimentam o atendimento.
- **Não melhora respostas sozinho.** Ele ajuda a localizar problemas e medir correções; não corrige recuperação, prompts ou regras de negócio automaticamente.

## Como eu faria

Começaria com uma especificação pequena para instrumentar geração, RAG, embeddings e chamadas auxiliares, mantendo prompts locais e auditoria existente. Agruparia execuções por conversa e correlacionaria geração, mensagem e busca, preservando a distinção entre **rascunho gerado** e **mensagem efetivamente enviada**.

A integração teria configuração para desligamento e falhas isoladas: indisponibilidade do Langfuse não poderia impedir atendimento. Antes da entrega, validaria ausência de vazamento, contabilização das chamadas auxiliares, correlação entre requisições e regressão dos fluxos de autonomia.

**Minha avaliação: vale a pena para diagnóstico, custos e evolução da qualidade da IA. Para o estágio atual, priorizaria Cloud com instrumentação limitada; deixaria self-hosted e avaliações automatizadas para uma segunda decisão, sustentada pelo uso observado.**
