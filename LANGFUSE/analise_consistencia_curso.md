# Revisão de consistência — curso prático de Langfuse

Data: 2026-09-09. Revisão equivalente de consistência entre o pedido, planejamento técnico, ensino e evidências do repositório. Escopo: documentação; não substitui a análise SDD anterior ao código de cada fase.

## 1. Pedido e entregas

| Necessidade do usuário | Cobertura |
|---|---|
| Usar uma pasta LANGFUSE e considerar o projeto | Consolidação da pasta existente em `LANGFUSE/`; mapa das funções reais no curso |
| Aprender a enxergar o estado atual | Aulas 1–3 e fotografia inicial no caderno |
| Entender por que a plataforma responde mal | Matriz de diagnóstico por conteúdo, recuperação, contexto, geração, agenda e envio |
| Curso curto ligado à construção | Seis aulas/360 minutos com dependências P1/P2/P3 explícitas |
| Aprender a resolver e verificar melhora | Aulas 4–6, rubrica, experimento, decisão e reversão |
| Considerar RAGFlow + Elasticsearch já instalado | Laboratório opcional de 90 minutos e comparação controlada |
| Ter orientação prática futura | Modelo de encontro, critérios de conclusão, caderno e instrução de retomada |

## 2. Base consultada

- Constituição 1.3.0, `AGENTS.md`, `PROJECT_STATE.md` e arquitetura, dados, observabilidade, segurança e plano de testes da raiz.
- Os quatro documentos existentes de planejamento Langfuse, incluindo contratos de scores, 30 casos, rubrica, runner e catálogo de prompts.
- Documentação de RAG/ingestão, teste humano, casos de avaliação existentes, requisitos pertinentes de 009/011 e aceitação de 012.
- Código de recuperação, seleção de mensagens, composição, reranking, provedores, fluxo N5, fronteiras de envio e configuração Compose/dependências.
- Documentação oficial atual de Langfuse, repositório oficial RAGFlow e documentação Elastic, citados junto às propostas correspondentes no curso.

As constatações de código são estáticas. Não foram consultados dados de conversas em execução nem medidas atuais de qualidade, e a instalação externa de RAGFlow não foi inspecionada. O relato de qualidade ruim e de instalação existente é do usuário.

## 3. Consistência entre planos

| Ponto de revisão | Resolução |
|---|---|
| Plano técnico já define três fases | Curso usa P1/P2/P3, sem criar uma quarta fase obrigatória |
| Foco cotidiano em N5 sem operador | Aula 2 exige os três caminhos e o mecanismo efetivo, distinguindo o ramo governado |
| Dados sintéticos, execução local, checkout atual | Mesmas premissas; nenhuma frente adicional de mascaramento ou implantação Cloud |
| Curso poderia exigir recursos antes da integração | Pré-requisito por aula; comandos/cliques serão validados na versão instalada |
| Dataset e rubrica poderiam divergir | Mantidos 30 casos, 10/caminho, divisão 24+6, notas 0/1/2 e calibração 10/12 |
| Seis casos didáticos poderiam virar outro conjunto obrigatório | São sementes da parte de elaboração; cobertura dos ramos é confirmada com fixtures |
| Métrica de recuperação não estava detalhada como exercício | `Hit@k` usa referências em `expected_facts`, sem outro dataset; especificar verificações aplicáveis em P2-01/P2-05 |
| Mudança no RAG pode alterar o caminho do caso | Comparar pelo caminho de origem e registrar transição; exigir ramo só quando for requisito crítico; formalizar em P2-01 |
| Confundir aceitação da ferramenta com qualidade do produto | Marcos separados; um candidato reprovado pode comprovar aprendizado e funcionamento da avaliação |
| Transformar aula de prompt em correção automática de contexto | Primeiro diagnosticar; mudanças de comportamento/contexto/recuperação exigem seu próprio SDD |
| Reserva de seis casos pode vazar para elaboração | Conferência após congelamento; nova reserva se os exemplos passarem a orientar ajustes |
| RAGFlow poderia ser tratado como solução comprovada | Laboratório opcional com baseline, condições comparáveis e decisão posterior sobre integração |

## 4. Divergências históricas consideradas

O resumo de escopo de `AGENTS.md` termina em 005, enquanto a constituição contém a emenda N5 e os artefatos posteriores documentam 006–012. O curso usa a constituição e as decisões posteriores para descrever o funcionamento atual; P1-01 já prevê reconciliar os resumos de autoridade antes de implementação. Esta entrega didática não altera políticas nem declara uma nova exceção arquitetural.

Os exemplos antigos de avaliação incluem agenda com `expected_status=ABSTAIN`, anterior à disponibilidade dinâmica e ao N5. O curso exige revisar o gabarito antes de reutilizá-los. Falta de fechamento documental em 007/012 permanece como situação registrada nos artefatos existentes; não se presume encerramento por acrescentar observabilidade.

## 5. Aceitação desta entrega documental

- [x] Seis aulas com duração, dependência técnica, prática e critério de conclusão.
- [x] Evidências locais ligadas às hipóteses; ausência de baseline medido declarada.
- [x] Primeira investigação e rotina posterior concretas.
- [x] Dataset, rubrica e critérios de seleção compatíveis com os contratos existentes.
- [x] Alternativa RAGFlow/Elasticsearch tratada como experimento, com preparação delimitada.
- [x] Caderno e entrada única para retomada; links nos planos técnicos.

Veredito: planejamento didático pronto. A integração, as aulas e os experimentos permanecem pendentes. A validação desta mudança é documental; testes de aplicação e gates de implementação continuam nas fases técnicas correspondentes.

Verificação da entrega: 51 links locais e suas âncoras conferidos; quatro documentos originais comparados com a versão anterior para confirmar preservação e alterações pontuais. A duração das seis aulas totaliza 360 minutos. Código, dependências e serviços não foram modificados.
