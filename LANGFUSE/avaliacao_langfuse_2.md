No seu uso em N5, avaliação de qualidade e gestão de prompts são partes importantes do resultado pretendido. Elas
  permitem identificar respostas fracas, testar melhorias e saber quais alterações realmente ajudaram. Mantive essas
  duas frentes nas fases 2 e 3 e aprofundei seus benefícios no plano.

  Avaliação de qualidade permite medir se o atendimento foi útil.

  Hoje, uma resposta N5 pode ser registrada como ANSWER e enviada corretamente, mas ainda ser genérica, repetitiva
  ou não resolver a solicitação. Como você trabalha sem revisão obrigatória do operador, esses problemas podem
  passar despercebidos.

  Eu avaliaria critérios diferentes para cada caminho:

   Caminho N5                Qualidade a verificar
  ━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Resposta reaproveitada    Responde à pergunta e respeita as informações recuperadas?
  ────────────────────────  ────────────────────────────────────────────────────────────────────────────────────────
   Agendamento guiado        Entendeu a opção escolhida e manteve profissional, data e horário corretos?
  ────────────────────────  ────────────────────────────────────────────────────────────────────────────────────────
   Fallback livre            Oferece ajuda concreta, considera o contexto recebido e evita inventar detalhes
                             específicos?

  Por exemplo: diante de uma solicitação específica, uma resposta como “Posso ajudar, conte um pouco mais” pode ser
  cordial, mas pouco útil. A avaliação permitiria distinguir cordialidade, relevância e avanço do atendimento.

  Os benefícios mais concretos seriam:

  - Encontrar problemas recorrentes: descobrir quais perguntas produzem respostas vagas ou inadequadas.
  - Localizar a causa: conferir se o problema está no prompt, na recuperação, nos dados ou no contexto enviado ao
    modelo.

  - Evitar regressões: verificar se uma mudança que melhora determinada resposta prejudica outras.
  - Comparar modelos e configurações: avaliar qualidade, custo e tempo sobre os mesmos casos.
  - Preservar aprendizado: transformar uma falha encontrada durante o uso em um caso que será verificado nas
    próximas mudanças.

  Langfuse oferece datasets, experimentos e scores para organizar essas comparações. Para começar, os 20–30 casos
  previstos seriam uma base prática, ampliada conforme surgissem situações novas. Conceitos de avaliação.

  Usaria regras para fatos objetivos, como a opção de horário selecionada, e um avaliador por LLM para aspectos como
  utilidade e coerência. A nota desse avaliador precisaria ser conferida em uma amostra humana: ela é um sinal de
  qualidade, não uma garantia. LLM-as-a-Judge.

  Gestão de prompts permite experimentar mudanças com histórico e reversão.

  O projeto já calcula hashes de alguns prompts, mas as instruções estão distribuídas entre arquivos Markdown e
  constantes Python. Há prompts distintos para resposta fundamentada, interpretação de datas, reranking clínico e
  fallback N5.

  O benefício adicional do Langfuse é relacionar a versão utilizada aos resultados que ela produziu, facilitando
  comparações de qualidade, custo e latência. Gestão de prompts.

  Na prática, você ganharia:

  - Diagnóstico por etapa: descobrir se a alteração relevante está no prompt livre N5, no reranking ou na
    interpretação de datas.

  - Histórico das decisões: preservar o que mudou e quais experimentos justificaram a escolha.

  As versões e labels do Langfuse permitem organizar essa seleção. A adoção efetiva precisa aparecer nos traces,
  pois o cache pode adiar a atualização no backend. Versões e labels, cache e fallback.

  Um detalhe específico do seu projeto: melhorar o prompt livre N5 só afeta os turnos que o executam. Se a resposta
  veio diretamente do agendamento ou da geração inicial, o trace ajuda a direcionar a alteração para o componente
  correto.

  O maior benefício aparece quando as três frentes trabalham juntas.

  Um exemplo de rotina seria observar respostas de fallback pouco úteis, selecionar essas conversas como casos de
  avaliação, criar um prompt candidato que ofereça melhores próximos passos e compará-lo com o atual. Você
  examinaria também possíveis pioras, consumo e tempo antes de selecionar a nova versão.

  Se o trace revelar que faltava contexto ao modelo, a correção será no fornecimento desse contexto. Isso evita
  gastar tempo tentando resolver tudo com alterações de prompt.

  A avaliação acrescenta chamadas de IA quando utiliza um modelo como juiz. Para controlar esse custo, começaria com
  execuções sob demanda e respostas já capturadas. A economia futura viria de escolhas melhores de prompt e modelo,
  comprovadas pelos experimentos.

  Aprofundei essas entregas no [plano de implementação local](plano_implementacao_local.md#5-fase-2--qualidade-das-respostas-no-n5).
