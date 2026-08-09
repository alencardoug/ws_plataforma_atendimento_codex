# Governança da base de conhecimento

## Identidade e escopo

Instituição: Referência Oncológica Cancer Center (simulação).

Responsável pelos documentos de mama: Dra. Fulana Silva.

Responsável pelos documentos colorretais: Dr. Ciclano Silva.

Versão inicial: `0.1.0`. Revisão ordinária semestral e revisão extraordinária
quando houver mudança relevante de diretriz ou processo.

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

## Fontes-base

- Instituto Nacional de Câncer (INCA), orientações para pacientes.
- National Cancer Institute (NCI), materiais de tratamento para pacientes.
- Código de Defesa do Consumidor, especialmente artigos 46 a 49.
- Lei Geral de Proteção de Dados Pessoais, especialmente artigos 5º, 7º e 11.
- Site institucional do A.C.Camargo consultado apenas como referência de tipos
  de serviço; o projeto não representa nem se identifica como essa instituição.
