# Langfuse: aprender a diagnosticar e melhorar a plataforma

Planejamento atualizado em 2026-09-09. **Revisto em 2026-09-10 — a
autoridade atual é [`revisao_claude_code.md`](revisao_claude_code.md).**

O objetivo é diagnosticar e corrigir as respostas ruins da plataforma,
com prioridade no atendimento N5. Langfuse é o meio; o fim é consertar.

**Comece por [`revisao_claude_code.md`](revisao_claude_code.md)**, depois
[`plano_implementacao.md`](plano_implementacao.md). Decisões firmadas em
2026-09-10: Langfuse **Cloud** (não self-hosted); a trilha de aprendizado
é *apprenticeship de diagnóstico*, não um calendário de aulas; RAGFlow /
Elasticsearch / LangChain / LangGraph ficam segurados até o diagnóstico
da **Fase 0**. Os documentos que descrevem o desenho anterior (curso de 6
aulas, self-hosted, 3 fases) permanecem na pasta como registro e fonte de
conteúdo — **não seguir como estão**.

| Material | Para que serve | Status |
|---|---|---|
| [Revisão Claude Code](revisao_claude_code.md) | Decisões de 2026-09-10, escopo revisto, veredito sobre ferramentas | **Autoridade** |
| [Plano de implementação](plano_implementacao.md) | Cloud + Fase 0 (diagnóstico mínimo) + fases seguintes provisórias | **Vigente** |
| [Instruções para o Codex](instrucoes_codex.md) | Handoff de implementação: LF-0 (spec leve) → LF-5 (instrumentação), regras, gates, checkpoints | **Vigente** |
| [Playbook de diagnóstico](playbook_diagnostico.md) | Taxonomia de falha, o que cada view serve, armadilhas, primeira investigação | **Vigente** |
| [Caderno de evolução](caderno_de_evolucao.md) | Logbook: estado inicial, hipóteses, experimentos, resultados | Em uso |
| [Contratos e roteiro de execução](detalhamento_execucao.md) | Contratos de observação (§3) e DB de teste (§5) vigentes; §6/§7 após a Fase 0 | Parcial |
| [Plano de implementação local](plano_implementacao_local.md) | Desenho self-hosted / 3 fases | Substituído |
| [Plano do curso prático](plano_curso_pratico.md) | Desenho original da trilha (6 aulas); fonte de conteúdo do playbook | Substituído |
| [Revisão de consistência do curso](analise_consistencia_curso.md) | Evidências consultadas, encaixe entre os planos | Histórico |
| [Avaliação inicial](avaliacao_langfuse.md) e [aprofundamento](avaliacao_langfuse_2.md) | Histórico que levou ao planejamento | Histórico |

A pasta anterior `langfuse/` foi consolidada como `LANGFUSE/`, mantendo os quatro documentos existentes. Esta passa a ser a entrada única para o planejamento técnico e o aprendizado.

**Estado:** direção decidida e pasta reestruturada (2026-09-10).
Implementação ainda não executada — nada de Langfuse foi instrumentado no
código. RAGFlow + Elasticsearch estão instalados na máquina do usuário,
mas segurados como experimento até o diagnóstico da Fase 0.

**Próximo passo:** o Codex segue
[`instrucoes_codex.md`](instrucoes_codex.md) — LF-0 (`spec.md` leve em
`specs/013-local-langfuse-observability/`, com parada para revisão do
humano) e depois a instrumentação dos 3 pontos (LF-1..LF-5). LF-6
(leitura dos traces) é humano + Claude Code.

Para retomar em outra sessão:

> Leia `LANGFUSE/revisao_claude_code.md` e `caderno_de_evolucao.md`.
> Estamos na reestruturação da pasta e na Fase 0 (diagnóstico mínimo via
> Langfuse Cloud). Me guie em passos curtos, usando conversas reais da
> plataforma.
