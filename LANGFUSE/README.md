# Langfuse: aprender a diagnosticar e melhorar a plataforma

Planejamento atualizado em 2026-09-09.

O objetivo é aprender, com orientação prática minha, a transformar uma conversa ruim em uma investigação, uma correção candidata e uma comparação que mostre se houve melhora. O curso acompanha a construção da integração local, com prioridade no atendimento N5.

**Comece pelo [plano do curso prático](plano_curso_pratico.md).** São seis aulas, aproximadamente seis horas de prática guiada, mais um laboratório opcional de 90 minutos com RAGFlow + Elasticsearch. O tempo de desenvolvimento da integração e das correções é separado da duração das aulas.

| Material | Para que serve |
|---|---|
| [Plano do curso prático](plano_curso_pratico.md) | Aulas, exercícios, dependências técnicas, critérios de aprendizado e caminho de melhoria |
| [Caderno de evolução](caderno_de_evolucao.md) | Registrar o estado inicial, hipóteses, experimentos, resultados e próximos passos |
| [Plano de implementação local](plano_implementacao_local.md) | Construção em três fases: observabilidade, avaliação e gestão de prompts |
| [Contratos e roteiro de execução](detalhamento_execucao.md) | Instrumentação, dataset, rubrica, isolamento dos testes, tarefas e aceitação técnica |
| [Revisão de consistência do curso](analise_consistencia_curso.md) | Evidências consultadas, encaixe entre os planos e limites desta entrega |
| [Avaliação inicial](avaliacao_langfuse.md) e [aprofundamento](avaliacao_langfuse_2.md) | Histórico que levou ao planejamento atual |

A pasta anterior `langfuse/` foi consolidada como `LANGFUSE/`, mantendo os quatro documentos existentes. Esta passa a ser a entrada única para o planejamento técnico e o aprendizado.

**Estado desta entrega:** curso e materiais de acompanhamento planejados; integração Langfuse, aulas, medições e experimentos ainda não executados. A instalação de RAGFlow + Elasticsearch foi informada pelo usuário; sua configuração e integração com a aplicação serão verificadas no laboratório.

O primeiro encontro é a Aula 1: definir o que significa um atendimento bom e escolher os casos do diagnóstico inicial. O primeiro trabalho técnico continua sendo P1-01: formalizar e analisar a especificação de observabilidade antes de código.

Para retomar em outra sessão:

> Leia `LANGFUSE/README.md`, o plano do curso e o caderno de evolução. Retome a primeira aula pendente, confira a entrega técnica necessária e me guie em passos curtos. Use os resultados da minha plataforma para explicar o que aconteceu e como testar a próxima melhoria.
