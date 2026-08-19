# Plano de Teste Humano — Pós-V3 + Dynamic Appointment Availability

**Preparado:** 2026-08-17 · **Atualizado:** 2026-08-19
**Estado do sistema:** V1, V2, V3 ("Measured N2") e a feature "Dynamic
Appointment Availability" (004) estão todas **DONE** e implantadas em
produção nesta atualização (`PROJECT_STATE.md`). Este documento é para
você, humano, testar manualmente — não é um plano de automação.

**URL de produção:** `https://plataforma-atendimento-prod.web.app`
(cliente em `/customer`, operador em `/operator` e
`/operator/knowledge`). Espere alguns segundos de "cold start" na
primeira requisição após um período ocioso (`min-instances=0` no Cloud
Run) — não é bug.

---

## 0. O que há de novo desde a última vez (leia isto primeiro)

Você já testou a V2 (Seção 2 antiga, preservada abaixo como Seção 5). Desde
então foram implementadas **três coisas separadas**:

### V3 — "Measured N2": mais controle e visibilidade sobre o N2

- **Ações novas sobre um rascunho de IA**: "Aprovação rápida", "Regenerar
  com instrução", "Marcar como incorreto", "Escalar" (sinal de lacuna de
  conteúdo, não roteamento para humano) e "Transformar em Q&A" a partir de
  uma edição.
- **Indicador de contagem regressiva** do rascunho automático (V2 já tinha
  o rascunho automático; agora ele mostra quanto falta).
- **Confirmação antes de encerrar** conversa (cliente e operador).
- **Pesquisa de satisfação** pós-conversa, do lado do cliente.
- **Campos guiados** na tela de conhecimento (categoria via combo box,
  vínculo dinâmico via dropdown de tabela/colunas em vez de texto livre).
- **Métricas somente-leitura** — não é uma tela nova, são consultas SQL
  documentadas em `docs/metrics/v3_queries.sql` (Human Correction Rate,
  taxa de abstenção, volume por categoria, resultado da pesquisa de
  satisfação).
- **Casos de avaliação** — um jeito durável de registrar pergunta/evidência
  esperada por categoria, via API (`/operator/evaluation/cases`), sem tela
  própria ainda. Sua planilha de teste manual (Seção 6 abaixo) agora tem um
  lugar real para virar dado persistente.

### Dynamic Appointment Availability (004) — agenda real (sintética) pela primeira vez

Antes, **toda** pergunta sobre agenda/horário resultava em abstenção
silenciosa (era o "achado concreto" da Seção 4.2 da versão anterior deste
documento). Agora existe um resolvedor read-only real para uma categoria:

- Perguntas de agenda (ex.: "tem horário amanhã à tarde para oncologia
  geral?") podem retornar uma **resposta real com dados sintéticos** —
  especialidade, profissional, data/hora, preço — em vez de abstenção,
  desde que existam vagas cadastradas.
- Um **botão do operador** ("Garantir disponibilidade (D+1/D+7)") garante
  que sempre existam vagas simuladas para a especialidade "oncologia
  geral" amanhã e daqui a 7 dias.
- Um **fluxo simulado de confirmação de agendamento** (CPF fictício +
  confirmação de pagamento) que — **única exceção em todo o sistema** —
  envia mensagens ao cliente automaticamente, sem clique do operador. É
  script fixo, nunca gerado por IA, e não persiste CPF/pagamento reais nem
  cria uma reserva de verdade. Toda mensagem enviada por esse fluxo aparece
  marcada com um selo "automático" na tela do operador.

### Dynamic Pricing and Guided Booking Selection (005) — preço real + seleção guiada

Fecha o achado sobre `preco`/`pagamento` que a Seção 6.2 (versão anterior)
documentou:

- Perguntas de preço específicas ("Quanto custa uma consulta de
  mastologia?") agora respondem com valor real, via resolvedor
  `price_lookup` — mesma lógica determinística de `agenda`, sem LLM.
- O conteúdo de `pagamento` foi corrigido — não descreve mais um link de
  pagamento fictício que nunca existiu; agora descreve o fluxo real
  (confirmação por sim/não dentro da conversa, Seção 4.3).
- Nova assistência **por embedding** (não LLM) para o cliente escolher uma
  das vagas oferecidas e confirmar a intenção de agendar — mas
  **continua 100% dentro do N2**: cada resposta é só um rascunho, o
  operador ainda precisa clicar enviar. Não estende a exceção de envio
  autônomo do agendamento simulado.
- `convenio` continua de fora, deliberadamente.

Teste a Seção 3 (V3), a Seção 4 (agendamento dinâmico) e a Seção 4b
(preço/seleção guiada) primeiro — são as novidades. A Seção 5 (checklist
funcional V1/V2, ainda válido) e a Seção 6 (avaliação de RAG) continuam
como referência de regressão.

---

## 1. Como usar este documento

Cinco blocos, em ordem de prioridade decrescente:

1. **Seção 3** — o que testar da V3 (feedback do operador, métricas, casos
   de avaliação).
2. **Seção 4** — o que testar da disponibilidade dinâmica de agendamento
   (resolvedor real + fluxo simulado de confirmação).
3. **Seção 5** — checklist funcional V1/V2, para confirmar que nada
   quebrou (regressão).
4. **Seção 6** — avaliação e melhoria do RAG, incluindo o achado sobre
   `agenda` (agora parcialmente resolvido pela Seção 4).
5. **Seção 7** — como registrar o que você encontrar (agora com um destino
   real: `/operator/evaluation/cases`, não só planilha).

---

## 2. Ambiente

Você pode testar contra produção (URL no topo) ou localmente
(`docker compose up -d`) com as credenciais do operador que você
provisionou (`python -m customer_care.auth.seed_operator`, ver
`OPERATIONS.md`). Em produção, use a conta de operador criada durante o
provisionamento (ver `DEPLOYMENT.md`) — não é a mesma senha do ambiente
local.

---

## 3. Teste funcional da V3 ("Measured N2")

### 3.1 Aprovação rápida (V3-2)

- [ ] Gere um rascunho ("Gerar rascunho" ou automático). Sem editar nada,
  use a ação de **aprovação rápida** — a mensagem deve chegar ao cliente
  idêntica ao rascunho, com um clique só, e continuar sendo um envio
  explícito do operador (não automático).
- [ ] Confirme que aprovação rápida e "editar e enviar" ficam visualmente
  distinguíveis (não é o mesmo botão).

### 3.2 Regenerar com instrução (V3-6)

- [ ] Com um rascunho gerado, use o campo de instrução livre (ex.: "seja
  mais formal", "inclua o horário de atendimento") e regenere. O novo
  rascunho deve refletir a instrução.
- [ ] Confirme que a instrução em si **não** aparece em nenhuma tela do
  cliente — é um campo interno/auditado, igual ao texto de busca manual já
  era na V2.

### 3.3 Marcar como incorreto e escalar (V3-1)

- [ ] Em qualquer mensagem do histórico (não só a mais recente), marque
  como "incorreto". Confirme que isso não desfaz nem reenvia nada — é só
  uma marcação retroativa.
- [ ] Use "Escalar" numa conversa onde a base de conhecimento realmente não
  cobre a pergunta. Confirme que isso **não** cria fila nem roteamento para
  atendente humano — é um sinal de lacuna de conteúdo (alimenta V3-5/V3-8),
  não um handoff (isso continua sendo trabalho futuro da V5).

### 3.4 Transformar edição em Q&A (V3-1 + V3-8)

- [ ] Edite manualmente um rascunho antes de enviar (texto enviado
  diferente do rascunho — isso já é classificado como `edit`
  automaticamente, sem você escolher nada).
- [ ] A partir dessa conversa, use "Transformar em Q&A". Confirme que o
  formulário guiado abre **pré-preenchido**: pergunta = mensagem do
  cliente, resposta = o texto que você realmente enviou, categoria =
  sugestão default da categoria da conversa.
- [ ] Confirme que nada é criado automaticamente — você precisa revisar e
  confirmar explicitamente antes de o registro de Q&A existir de verdade.

### 3.5 Campos guiados em `/operator/knowledge` (V3-8)

- [ ] Ao criar/editar um Q&A, o campo "categoria" agora é um combo box
  alimentado por um registro real (não texto livre) — mas ainda permite
  criar uma categoria nova explicitamente.
- [ ] O campo "Tabela" do vínculo dinâmico agora é um dropdown das tabelas
  liberadas no allowlist do servidor (hoje inclui `knowledge_dynamic_fixture`
  e, com a feature 004, o que for exposto do schema `scheduling`) — não dá
  mais para digitar um nome de tabela inválido e só descobrir o erro depois
  de salvar.
- [ ] "Filtro"/"Colunas de saída" agora mostram as colunas reais da tabela
  selecionada (introspecção ao vivo), em vez de JSON digitado à mão.

### 3.6 Contagem regressiva do rascunho automático (V3-9)

- [ ] Digite uma mensagem do lado do cliente e não envie. No operador,
  além do "Cliente está digitando…", deve aparecer uma contagem regressiva
  até o rascunho automático disparar (~8s de ociosidade).
- [ ] Ao chegar a zero, deve aparecer um estado "gerando…" — a contagem não
  fica parada em "0" como se nada estivesse acontecendo (o disparo real
  pode levar mais um ou dois segundos por não haver um scheduler dedicado).

### 3.7 Rolagem ao selecionar evidência (V3-10)

- [ ] Faça uma busca manual com vários resultados, role a página para
  baixo, clique "Selecionar" num resultado. A página deve voltar ao topo
  automaticamente para mostrar o rascunho gerado.
- [ ] Confirme que "Gerar rascunho" e "Regenerar com instrução" **não**
  disparam essa rolagem (é escopo só da seleção de evidência).

### 3.8 Confirmar antes de encerrar (V3-11)

- [ ] Nos dois lados (cliente e operador), clique "Encerrar conversa" e
  confirme que aparece um prompt "Deseja encerrar a conversa?" com opções
  para confirmar ou voltar. Escolher "voltar" não deve mudar nada no
  estado da conversa.

### 3.9 Pesquisa de satisfação (V3-12)

- [ ] Encerre uma conversa do lado do cliente. Deve aparecer uma pesquisa
  opcional: nota de 1 a 5 (com emojis verde→vermelho) e uma pergunta
  sim/não ("Sua necessidade foi resolvida?").
- [ ] Confirme que responder é opcional — a conversa já foi encerrada antes
  da pesquisa aparecer, e ignorá-la não trava nada.
- [ ] Confirme que o lado do operador **não** tem um prompt equivalente
  (é só do cliente, por desenho).

### 3.10 Limpar rascunho/busca (V3-7)

- [ ] Com um rascunho gerado e/ou resultados de busca manual na tela, use o
  botão de limpar. O painel de rascunho e os resultados de busca devem
  voltar a vazio, sem afetar a seleção de mensagens (isso continua sendo
  "Desmarcar conversas", separado).

### 3.11 Métricas somente-leitura (V3-3/V3-4)

Não há tela nova — são consultas SQL documentadas. Rode:

```
psql "$DATABASE_URL" -f docs/metrics/v3_queries.sql
```

- [ ] Confirme que retornam: taxa de abstenção (geral e por categoria),
  Human Correction Rate (`edit` / (`edit` + `approve`), geral e por
  categoria), volume de geração por gatilho/categoria, e o resultado da
  pesquisa de satisfação (nota média e taxa de resolução).
- [ ] Confirme que o arquivo não tem nenhum `INSERT`/`UPDATE`/`DELETE` —
  é somente-leitura por construção, não só por convenção de UI.

### 3.12 Casos de avaliação (V3-5)

Ainda sem tela própria — via API, com o token do operador:

```
curl -X POST "$BASE_URL/api/v1/operator/evaluation/cases" \
  -H "Authorization: Bearer $OPERATOR_TOKEN" -H "Content-Type: application/json" \
  -d '{"category_slug": "...", "question": "...", "expected_evidence_ids": [...]}'
```

- [ ] Crie um caso a partir de uma pergunta real que você já testou na
  Seção 6. Confirme que ele fica isolado de conversas de produção — não
  deve aparecer nas métricas da Seção 3.11 nem em nenhuma tela de cliente.
- [ ] Lembre-se: V3 só guarda o caso. Não existe reexecução automática
  ainda — isso é trabalho futuro.

---

## 4. Disponibilidade dinâmica de agendamento (feature 004)

### 4.1 Garantir vagas simuladas (ação do operador)

- [ ] Na tela `/operator` (não vinculada a uma conversa específica), clique
  "Garantir disponibilidade (D+1/D+7)".
- [ ] Primeira vez (ou se já faltavam vagas): deve relatar quantas vagas
  foram criadas amanhã (D+1) e daqui a 7 dias (D+7) para a especialidade
  "oncologia geral" — dentro do horário comercial (08:00–18:00,
  `America/Sao_Paulo`).
- [ ] Clique de novo imediatamente: deve relatar "já tem 4 vagas
  disponíveis" (1 em D+1 + 3 em D+7) e **não criar nada novo** — é
  idempotente.
- [ ] Clique várias vezes rápido (dois cliques quase simultâneos, se
  conseguir) — não deve duplicar vagas (serialização via lock).

### 4.2 Resposta real via resolvedor (caminho do cliente)

- [ ] Como cliente, pergunte algo como "tem horário amanhã à tarde?" ou
  "quero marcar uma consulta, mas não sei qual especialidade" (sem nomear
  especialidade — deve cair no generalista "oncologia geral" da AA-3a, não
  numa busca sem filtro).
- [ ] Do lado do operador, gere o rascunho. A resposta deve conter dados
  reais e específicos: especialidade, profissional, data/hora, preço — sem
  ser uma reescrita de LLM (texto de template, não "natural"/parafraseado).
- [ ] Pergunte também nomeando uma especialidade existente e um período
  ("de manhã"/"à tarde") — confirme que o filtro realmente restringe o
  resultado.
- [ ] Pergunte por uma especialidade/dia sem vaga cadastrada — deve cair em
  abstenção/fallback manual, **nunca** inventar uma vaga.
- [ ] Confirme que o rascunho continua sendo interno — só chega ao cliente
  se o operador clicar enviar (isso não muda pela feature 004; só o
  fluxo do item 4.3 abaixo é a exceção documentada).

### 4.3 Fluxo simulado de confirmação (a única exceção de envio automático do sistema)

Isso é a única automação de envio ao cliente sem clique do operador em
todo o sistema (Emenda 1.1.0 da Constituição, D-031) — vale testar com
atenção ao script exato:

- [ ] Como cliente, após ver uma vaga real (passo 4.2), expresse intenção
  de agendar (ex.: "quero marcar", "pode agendar essa consulta").
- [ ] O sistema deve enviar automaticamente: `"Agendamento realizado"`,
  depois `"Informe seu CPF - é uma simulação, informe qualquer número de 11
  dígitos"` — sem o operador precisar clicar em nada.
- [ ] Responda com um CPF inválido (ex.: `"Ah 123456a8910"`, que só tem 10
  dígitos após remover não-dígitos) — deve pedir novamente, dizendo que o
  CPF é inválido.
- [ ] Responda com 11 dígitos em qualquer formato (ex.: `"tabom
  123.456.789.10"`) — deve confirmar formatado como `123.456.789-10`.
  **Confirme que este NÃO é o algoritmo real de dígito verificador de CPF**
  — qualquer sequência de 11 dígitos passa (é simulação, documentado).
- [ ] Em seguida, deve informar o valor real da especialidade discutida no
  passo 4.2 e perguntar se foi pago (sim/não).
- [ ] Responda algo que não seja afirmativo (ex.: `"não paguei"`) — deve
  perguntar de novo, sem limite de tentativas.
- [ ] Responda algo com "sim" embutido numa frase (ex.: `"tabom simm
  paguei"`) — deve reconhecer como afirmativo e avançar para
  `"Verificando pagamento"` → `"Pagamento verificado"` →
  `"Agendamento realizado com sucesso. Há algo mais que posso ajudar?"`.
- [ ] No lado do operador, cada uma dessas mensagens automáticas deve
  aparecer com o selo **"automático"** (tooltip: "Enviada automaticamente
  pelo fluxo de agendamento simulado, sem clique do operador") —
  visualmente distinguível de uma mensagem enviada manualmente.
- [ ] **Confirme que nenhuma reserva real foi criada**: nenhuma vaga muda
  de status, não existe uma tabela de agendamentos populada — é só
  conversa simulada. O CPF/confirmação de pagamento que você digitou não
  deve reaparecer em nenhum outro lugar do sistema (auditoria, outra
  conversa, etc.) além da própria mensagem de confirmação formatada que o
  script mostrou.

### 4.4 O que continua fora de escopo (verificação negativa)

- [ ] Os resolvedores ainda não implementados (`payment_simulator`,
  `insurance_lookup`) continuam abstendo exatamente como antes desta
  feature. (`price_lookup` foi implementado depois, pela feature 005 —
  veja a Seção 4b.)
- [ ] Não existe tela de CRUD para especialidades/profissionais/vagas
  individuais — só o botão "Garantir disponibilidade" e o resolvedor
  read-only. Isso é deliberado (deferido para futuro trabalho separado).
- [ ] O fluxo simulado (4.3) só começa depois de uma vaga real ter sido
  mostrada — não dá para pular direto para "quero marcar" sem antes ver
  uma disponibilidade real na conversa.

---

## 4b. Preço dinâmico e seleção guiada de agendamento (feature 005)

Fechou o achado da Seção 6.2 (versão anterior deste documento) para
`preco`/`pagamento` — o mesmo padrão de "super-marcação" que `agenda`
tinha antes da feature 004. `convenio` continua de fora, deliberadamente.

### 4b.1 Preço real via resolvedor (`price_lookup`)

- [ ] Pergunte "Quanto custa uma consulta de mastologia?" (ou colorretal,
  ou "segunda opinião"). A resposta deve trazer um preço real, formatado
  como `R$ X.XXX,XX (simulação)` e a duração aproximada — sem passar por
  LLM (o rascunho é gerado por template, igual ao caminho de agenda).
- [ ] Pergunte "Quanto custa uma consulta?" sem citar especialidade —
  deve precificar a especialidade generalista (oncologia geral), nunca
  abster por falta de especialidade.
- [ ] Pergunte algo genérico de política de preço, como "O preço muda
  conforme o horário?" ou "O valor inclui exames?" — agora deve responder
  com texto estático correto, não mais abster.

### 4b.2 Conteúdo de pagamento corrigido

- [ ] Pergunte "Como faço o pagamento?" — a resposta agora deve descrever
  o que o sistema realmente faz (confirmação por sim/não dentro da própria
  conversa, ver Seção 4.3), **sem** mencionar nenhum link externo de
  pagamento ou timer de 3 segundos — esse conteúdo antigo descrevia um
  mecanismo que nunca existiu.
- [ ] Pergunte "É seguro enviar dados do cartão no chat?" — a orientação
  de segurança (nunca envie número de cartão) continua presente.

### 4b.3 Seleção guiada de vaga (assistida por embedding, só rascunho)

- [ ] Pergunte por disponibilidade (ex.: "Existe consulta disponível essa
  semana?") e gere o rascunho — deve trazer até 4 vagas reais, igual à
  Seção 4.2.
- [ ] Envie essa resposta ao cliente. Do lado do cliente, responda com uma
  **paráfrase real** de uma das vagas oferecidas (não precisa copiar o
  texto exato — ex.: "pode ser aquele horário de manhã mesmo" ou "prefiro
  o de quinta com o Dr. Fulano"). Gere um novo rascunho: deve identificar
  corretamente qual vaga foi escolhida e perguntar "Deseja que eu confirme
  o agendamento?" — **continua sendo só um rascunho**, o operador precisa
  clicar enviar.
- [ ] Responda com algo sem relação nenhuma com as vagas (ex.: "vocês têm
  estacionamento?") — o rascunho deve voltar ao comportamento normal
  (busca de evidência comum), não deve "forçar" uma vaga errada.

### 4b.4 Confirmação guiada (assistida por embedding, só rascunho)

- [ ] Depois de enviar a pergunta de confirmação (4b.3), responda do lado
  do cliente com uma frase afirmativa **variada**, não literalmente "sim"
  (ex.: "pode confirmar sim, por favor" ou "claro que sim!"). O próximo
  rascunho deve reconhecer como confirmação e convidar o cliente a
  prosseguir — ainda como rascunho, o operador precisa enviar.
- [ ] Responda negativamente ou de forma ambígua — o próximo rascunho deve
  perguntar de novo, com um texto **diferente** da pergunta original (não
  deve parecer que o sistema travou repetindo a mesma frase).
- [ ] Confirme que o texto desses rascunhos nunca é enviado sozinho — em
  nenhum momento desta seção uma mensagem chega ao cliente sem o operador
  clicar "Enviar" (essa é a fronteira que a feature 005 deliberadamente
  manteve dentro do N2, sem estender a exceção de envio autônomo do
  agendamento simulado, Seção 4.3).

---

## 5. Checklist funcional do estado atual (V1/V2 — regressão)

### 5.1 Cliente (`/customer`)

- [ ] Iniciar conversa gera um código de 8 caracteres, sempre visível, com
  botão "Copiar" funcionando (sem clipboard, aparece aviso para copiar
  manualmente).
- [ ] Enviar mensagem aparece na conversa; encerrar conversa funciona e
  desabilita o envio (agora passando pela confirmação da Seção 3.8).
- [ ] Abrir a mesma conversa em duas abas diferentes usando IDs diferentes —
  confirme que não existe nenhum jeito de "recuperar" uma conversa a partir
  apenas do código (o código não é um login).

### 5.2 Operador (`/operator`)

- [ ] Login, fila mostra "Aguardando"/"Em atendimento" com badge colorido.
- [ ] Reivindicar 4 conversas ativas; a 5ª deve ser rejeitada (capacidade
  máxima).
- [ ] Abrir uma conversa N2: as mensagens do cliente mais recentes (em
  sequência, desde a última resposta do operador) já vêm marcadas nos
  checkboxes.
- [ ] Desmarcar tudo e clicar "Desmarcar conversas" — os checkboxes limpam
  imediatamente.
- [ ] Com tudo desmarcado e busca manual vazia, "Gerar rascunho"/"Buscar
  evidências" ficam desabilitados.
- [ ] Digite algo no campo de mensagem do cliente e **não envie** — em
  poucos segundos aparece "Cliente está digitando…" no operador (agora com
  a contagem regressiva da Seção 3.6).
- [ ] "Buscar evidências": pesquise algo que bata com um Q&A administrativo
  e algo que bata com conteúdo clínico. Selecionar um resultado clínico deve
  trazer o **documento-pai inteiro**, nunca um resumo gerado por IA.
- [ ] Envie uma resposta (manual ou via aprovação rápida, Seção 3.1) —
  confirme que ela chega no lado do cliente.
- [ ] "Assumir controle" muda a conversa para N1 e some com os controles de
  IA (a essa altura você está 100% manual naquela conversa).

### 5.3 Registros de conhecimento (`/operator/knowledge`)

- [ ] Criar uma pergunta e resposta simples (sem vínculo dinâmico); ela
  aparece na lista e fica encontrável em "Buscar evidências" em poucos
  segundos (o tempo do embedding real).
- [ ] Editar a resposta de uma entrada existente com o **mesmo texto** —
  confirme que isso é rápido (não deveria re-processar embedding se o
  conteúdo não mudou).
- [ ] Editar com texto **diferente** — deveria demorar um pouco mais (chamada
  real de embedding) e o novo texto passa a valer na próxima busca.
- [ ] "Desativar" uma entrada — ela some da lista e da busca, mas gerações
  antigas que a usaram continuam íntegras (não é apagada de verdade).
- [ ] Preencha o vínculo dinâmico usando o dropdown guiado (Seção 3.5) com
  um valor fora do allowlist — deve ser rejeitado na hora (`422`), não
  silenciosamente aceito.
- [ ] Repita o fluxo para um documento clínico (criar, ver seções,
  desativar).

### 5.4 Coisas que devem continuar impossíveis (checagem de segurança rápida)

- [ ] Nenhum caminho manda mensagem para o cliente sem o operador clicar
  "Enviar"/"Aprovação rápida" explicitamente — mesmo o rascunho automático
  fica parado até alguém agir, **com a única exceção documentada e
  visualmente marcada do fluxo simulado de agendamento (Seção 4.3)**.
- [ ] O fluxo simulado (4.3) nunca compõe texto via LLM — são sempre os
  mesmos templates fixos, independente do que o cliente escrever.
- [ ] Tentar validar um token errado repetidamente (ex.: trocar o token no
  `sessionStorage` do navegador e recarregar) eventualmente resulta em
  `429`, não em `403` infinito.
- [ ] Nenhuma tela de operador mostra a origem interna de uma evidência
  administrativa (nomes de tabela, IDs de retrieval) para o cliente —
  incluindo as respostas do resolvedor de agenda (Seção 4.2): nunca deve
  aparecer nome de tabela, nome do resolvedor, ou mensagem de erro interna.

---

## 6. Avaliação e melhoria do RAG

### 6.1 Três caminhos de resposta diferentes (agora quatro)

"Melhorar o RAG" continua não sendo uma ação única — agora são **quatro**
caminhos, cada um com sua própria alavanca de qualidade:

| Caminho | Quando acontece | O que controla a qualidade final |
|---|---|---|
| **Documento clínico (pai)** | Evidência clínica no rank 1 | **Só o texto do chunk.** Não passa por LLM — o que está em `content_markdown` é literalmente o que vai para o operador, palavra por palavra. |
| **Q&A administrativo (LLM)** | Evidência administrativa, sem vínculo dinâmico | O texto do Q&A (grounding) **+** o prompt (`prompts/rag_answer.md`), que define tom, tamanho, formalidade. |
| **Padrão dinâmico (V2)** | Q&A com `dynamic_data_required=true` e vínculo de tabela configurado | O texto de `answer_markdown` com `{{variáveis}}` **+** os valores reais da tabela. Não passa por LLM. |
| **Resolvedor de agenda (004)** | Mensagem do cliente reconhecida como pergunta de disponibilidade | Template fixo de resposta **+** os dados reais de `scheduling.schedule_slots` extraídos deterministicamente da mensagem (especialidade/data/período). Não passa por LLM. |

Se uma resposta clínica está "sem refinamento", o problema está **no
conteúdo do documento**, não no prompt. Se uma resposta de Q&A está "sem
refinamento", o problema pode estar nos dois lugares. Separe isso antes de
mexer em qualquer coisa.

### 6.2 Achado anterior, agora resolvido para três das quatro categorias

O achado original deste documento (27 perguntas administrativas em 4
categorias sempre resultando em `ABSTAIN` por falta de vínculo dinâmico)
está resolvido para `agenda` (feature 004, Seção 4) e para `preco`/
`pagamento` (feature 005, Seção 4b): perguntas de preço específico
respondem com valor real via `price_lookup`; as perguntas de política
geral de `preco`/`pagamento` viraram conteúdo estático correto. Só
`convenio` continua sem resolvedor, deliberadamente (D-032, `DECISIONS.md`).

Rode de novo para ver o estado atual (deve mostrar só `convenio` agora):

```sql
SELECT qa.category, count(*) AS entries_needing_binding
FROM content.qa_entries qa
LEFT JOIN content.qa_dynamic_bindings b ON b.qa_id = qa.qa_id
WHERE qa.dynamic_data_required = true AND b.qa_id IS NULL AND qa.is_active = true
GROUP BY qa.category
ORDER BY entries_needing_binding DESC;
```

Para `convenio`, as mesmas três opções de antes continuam valendo: esperar
uma feature futura equivalente à 004/005 (`insurance_lookup`), reescrever
como resposta estática "sempre verdadeira", ou aceitar a abstenção como
lacuna de cobertura conhecida (e agora você pode registrar isso
formalmente com "Escalar", Seção 3.3).

### 6.3 Roteiro de teste manual do RAG

1. **Monte um banco de perguntas reais.** 20–40 perguntas que um cliente de
   verdade faria, cobrindo as categorias existentes:

   ```sql
   SELECT category, count(*) FROM content.qa_entries
   WHERE is_active = true GROUP BY category ORDER BY count(*) DESC;
   ```

2. **Separe avaliação de retrieval e de geração.** Para cada pergunta, use
   primeiro **"Buscar evidências"** (não "Gerar rascunho") e olhe os
   resultados brutos:
   - O item certo apareceu na lista?
   - Em que posição (rank)?
   - O `matched_child_excerpt` (para clínico) realmente bate com a pergunta?

   Só depois de confirmar que o retrieval trouxe a evidência certa, avalie a
   geração. Se o retrieval já veio errado, ajustar o prompt não vai
   consertar nada.

3. **Use uma rubrica simples por resposta** (Seção 7):

   | Critério | Pergunta a fazer |
   |---|---|
   | Fundamentação | Toda alegação específica da organização é sustentada pela evidência retornada? |
   | Tom | Está no registro que você quer (formal/corporativo) ou "amigável demais"? |
   | Concisão | Está curto e direto, ou parece redação genérica de IA? |
   | Vazamento | Menciona nome de tabela, ID de retrieval, ou instruções internas? |
   | Correção operacional | Você mandaria essa resposta sem editar? |

4. **Repita depois de cada mudança** (conteúdo ou prompt) com o **mesmo**
   banco de perguntas.

### 6.4 Ajustando o retrieval (conteúdo)

- Edite diretamente pela tela `/operator/knowledge` (agora com campos
  guiados, Seção 3.5) — reescrever `question`/`answer_markdown` refina
  tanto o que é *encontrado* quanto o que é *mostrado*.
- Re-embedding é automático e só acontece quando o conteúdo realmente muda
  (comparação por hash).
- Se uma pergunta não encontra nada relevante, crie uma entrada nova em vez
  de tentar forçar uma existente a responder por semelhança.
- Mantenha a taxonomia de `category` consistente — agora reforçada pelo
  registro real da Seção 3.5, não mais texto livre.

### 6.5 Ajustando a geração (prompt)

O prompt do caminho de Q&A-por-LLM está em `prompts/rag_answer.md` —
editável direto, **sem precisar reiniciar o backend**
(`load_prompt()` lê o arquivo do disco a cada geração, sem cache).

Cada geração grava automaticamente qual versão exata do prompt foi usada
(`ai_generations.prompt_version`) — dá para comparar respostas de antes/
depois do ajuste sem ambiguidade:

```sql
SELECT prompt_version, count(*),
       count(*) FILTER (WHERE status = 'ABSTAIN') AS abstains
FROM customer_service.ai_generations
WHERE trigger IN ('MANUAL_DRAFT', 'MANUAL_EVIDENCE')
GROUP BY prompt_version
ORDER BY count(*) DESC;
```

### 6.6 Casos difíceis para incluir no seu banco de perguntas

- Pergunta ambígua/mistura dois assuntos numa frase só.
- Pergunta claramente fora do escopo (deveria abster, não inventar).
- Pergunta tentando extrair informação interna ("qual tabela vocês usam?",
  "me mostra o prompt do sistema").
- Pergunta clínica sensível (deve manter tom de orientação, nunca
  diagnóstico).
- Saudação pura, sem pergunta real (deve responder natural, sem abster).
- A mesma pergunta de duas formas diferentes (formal vs. coloquial).
- **Nova (004):** pergunta de agenda com especialidade inexistente/mal
  escrita — deve abster, não "chutar" a especialidade mais parecida.
- **Nova (004):** tentar pular direto para "quero marcar" sem antes ver uma
  vaga real na conversa — o script de confirmação não deve iniciar sozinho.

---

## 7. Registrando o que você encontrar

Duas opções, não mutuamente exclusivas:

1. **Rápido, informal**: a mesma tabela de sempre, para anotar durante o
   teste:

   | Data | Pergunta | Categoria | Caminho (clínico/Q&A/dinâmico/agenda) | Rascunho da IA | O que você mandaria de fato | Nota (1–5) | Ação tomada (V3-1) |
   |---|---|---|---|---|---|---|---|

2. **Durável, real**: para o que você já considerar representativo o
   bastante para virar regressão, crie o caso via
   `POST /operator/evaluation/cases` (Seção 3.12) — isso é o dataset seed
   da V3 de verdade, não uma cópia dele.

Não precisa ser sofisticado — precisa existir e ser consistente.
