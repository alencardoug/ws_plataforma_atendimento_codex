# Governança da base de conhecimento

## Identidade e escopo

Instituição: Referência Oncológica Cancer Center (simulação).

Responsável pelos documentos de mama: Dra. Fulana Silva.

Responsável pelos documentos colorretais: Dr. Ciclano Silva.

Versão inicial: `0.1.0`. Versão atual: `0.2.0` — inclusão de diretrizes para
risco hereditário, prognóstico individual e sofrimento emocional intenso, com
os respectivos Q&A em `content.qa_entries` (categorias `risco_hereditario`,
`prognostico`, `apoio_emocional`, e expansão de `sus`). Revisão ordinária
semestral e revisão extraordinária quando houver mudança relevante de
diretriz ou processo.

## Separação de apresentação e recuperação

O Markdown enviado ao paciente contém apenas identidade do documento, título,
versão, responsável e datas. Metadados clínicos, intenções, urgência, relações,
fontes e embeddings ficam no PostgreSQL, vinculados por `document_id`.

Cada seção clínica é um child recuperável, mas o download usa sempre o parent
completo. O Q&A é armazenado em entradas independentes (`content.qa_entries`) e
não usa hierarquia parent-child.

## Dados dinâmicos

Agenda, preço, profissional, feriado, pagamento e protocolo nunca devem ser
respondidos apenas pelo vetor. Entradas com `dynamic_data_required=true` chamam
o resolver indicado e consultam o PostgreSQL antes da resposta.

## Regras de segurança conversacional

- Não diagnosticar, prescrever ou alterar tratamento.
- Não reduzir sinais de alerta a uma pontuação automática.
- Em piora rápida ou risco imediato, orientar o serviço de emergência mais próximo.
- Ramal 0000 (simulação) é indicado somente para dúvidas sem risco imediato.
- CPF e dados clínicos individuais não entram em prompts de recuperação,
  embeddings, URLs ou logs de aplicação.
- Informações comerciais e institucionais devem incluir “(simulação)”.

### Risco hereditário e genético

- O chatbot pode explicar, em termos gerais, que a maioria dos cânceres não é
  hereditária e que histórico familiar pode indicar aconselhamento genético.
- Não deve estimar risco individual, interpretar resultado de exame genético
  (ex.: BRCA1/BRCA2) nem afirmar se uma pessoa "vai ter" ou "não vai ter"
  câncer. Essa avaliação é de aconselhamento genético e equipe médica.

### Prognóstico e sobrevida individual

- O chatbot nunca fornece estimativa numérica de sobrevida, expectativa de
  vida ou "quanto tempo falta", mesmo diante de estágio, exame ou diagnóstico
  informado pelo usuário.
- Estatísticas populacionais de sobrevida podem ser mencionadas apenas para
  explicar que não predizem um caso individual; a conversa sobre prognóstico
  pessoal deve ser redirecionada ao médico responsável.
- Perguntas desse tipo ficam na categoria `prognostico` do Q&A e carregam
  `metadata.escalation_recommended=true`, sinalizando apoio humano/psico-
  oncológico como complemento, não substituição, da resposta.

### Sofrimento emocional intenso

- Mensagens com medo, angústia ou menção a morte devem ser acolhidas antes de
  qualquer conteúdo transacional (ex.: não responder só sobre preço ou SUS
  quando a mensagem também expressa medo).
- Sofrimento intenso ou isolamento devem ser acolhidos com orientação para
  buscar ajuda (equipe, apoio psicológico/psico-oncológico); citar
  autoagressão ou pensamento de se machucar apenas quando o próprio cliente
  trouxer esse tema explicitamente na conversa — não incluir esse tipo de
  menção como conteúdo padrão/preventivo em respostas gerais sobre medo,
  tristeza ou prognóstico (decisão humana, 2026-08-19).
- Quando o cliente trouxer esse tema explicitamente, orientar serviço de
  emergência imediatamente, sem aguardar agendamento comum.
- Essas entradas ficam na categoria `apoio_emocional` do Q&A, também com
  `metadata.escalation_recommended=true`.
- A citação de psico-oncologia (e, quando pertinente, nutrição,
  endocrinologia e fisioterapia especializadas em oncologia) é incentivada
  sempre que houver conexão real com a mensagem do cliente — ver
  `ROADMAP.md` para a extensão dessas quatro especialidades ao agendamento,
  registrada para uma futura rodada de SDD.

### Acesso pelo SUS

- O chatbot pode orientar o fluxo público geral (UBS, encaminhamento,
  CACON/UNACON) e o prazo legal de início de tratamento, mas não promete
  vaga, encaminhamento específico ou prazo garantido no caso individual.
- Ausência de dinheiro ou plano de saúde nunca deve ser respondida apenas com
  um encerramento de conversa; sempre indicar a via pública disponível.

## Fontes-base

- Instituto Nacional de Câncer (INCA), orientações para pacientes.
- Instituto Nacional de Câncer (INCA), materiais sobre síndromes de
  predisposição hereditária ao câncer e aconselhamento genético.
- National Cancer Institute (NCI), materiais de tratamento para pacientes.
- Ministério da Saúde / SUS, rede de atenção oncológica (CACON/UNACON) e
  fluxo de acesso pela atenção básica.
- Lei nº 12.732/2012, prazo de 60 dias para início do primeiro tratamento
  oncológico no SUS após diagnóstico confirmado em laudo.
- Código de Defesa do Consumidor, especialmente artigos 46 a 49.
- Lei Geral de Proteção de Dados Pessoais, especialmente artigos 5º, 7º e 11.
- Site institucional do A.C.Camargo consultado apenas como referência de tipos
  de serviço; o projeto não representa nem se identifica como essa instituição.
