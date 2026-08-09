# Referência Oncológica Cancer Center — base RAG demonstrativa

Ambiente demonstrativo para conteúdo oncológico parent-child, atendimento Q&A,
agenda dinâmica e fluxo fictício de agendamento. Toda informação comercial,
institucional, profissional, telefônica e de pagamento é uma **simulação**.

## Componentes

- PostgreSQL 16 com `pgvector` e schemas separados por responsabilidade.
- Agenda dinâmica com quatro vagas por especialidade em `D+1` e `D+7`.
- Calendário de feriados e deslocamento para o próximo dia útil.
- Reserva de vaga por 30 minutos.
- FastAPI para busca, disponibilidade e agendamento.
- Documentos Markdown para pacientes e catálogo técnico para parent-child RAG.
- Pagamento fictício confirmado automaticamente após três segundos.

## Início rápido

```bash
cp .env.example .env
docker compose up --build
```

Depois, acesse `http://localhost:8000/docs`.

## Avisos

Os documentos clínicos são materiais educativos simulados e não substituem
avaliação individual. Sintomas intensos ou piora rápida exigem procura do serviço
de emergência mais próximo. Em caso de dúvida não emergencial, use o Ramal 0000
(simulação).

O CPF não é enviado para embeddings ou logs de conversa. A API armazena hash,
últimos quatro dígitos e versão cifrada. Troque todas as chaves de demonstração
antes de qualquer uso fora de ambiente local.

