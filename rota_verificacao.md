# Rota de verificação geral

Este roteiro verifica o projeto em quatro camadas: infraestrutura, banco de
dados, API e documentos. A ordem começa pela execução do ambiente e termina na
origem dos conteúdos gerados.

## 1. Iniciar e conferir o ambiente

```bash
cd /home/doug/Projetos/ia/onco_docs
docker compose up -d
docker compose ps
```

O esperado é encontrar o banco `healthy`, exposto em `5433`, e a API ativa em
`8000`.

```bash
docker compose logs db --tail=100
docker compose logs api --tail=100
docker compose logs -f
```

Use `Ctrl+C` para sair dos logs contínuos sem parar os contêineres.

## 2. Entrar no PostgreSQL

```bash
docker compose exec db psql -U oncology -d oncology
```

Comandos básicos do `psql`:

```text
\dn                  listar schemas
\dt content.*        tabelas de documentos e RAG
\dt scheduling.*     agenda e consultas
\dt identity.*       pacientes e consentimentos
\dt billing.*        pagamentos
\dt governance.*     fontes e políticas
\df scheduling.*     funções de agenda
\dv scheduling.*     views de agenda
\d content.documents descrever uma tabela
\q                   sair
```

## 3. Visão geral do banco

```sql
SELECT schemaname, tablename
FROM pg_tables
WHERE schemaname IN (
    'content', 'scheduling', 'identity', 'billing', 'governance'
)
ORDER BY schemaname, tablename;
```

Quantidade de registros por área:

```sql
SELECT 'documents' AS entidade, count(*) FROM content.documents
UNION ALL SELECT 'chunks', count(*) FROM content.chunks
UNION ALL SELECT 'qa_entries', count(*) FROM content.qa_entries
UNION ALL SELECT 'specialties', count(*) FROM scheduling.specialties
UNION ALL SELECT 'professionals', count(*) FROM scheduling.professionals
UNION ALL SELECT 'slots', count(*) FROM scheduling.schedule_slots
UNION ALL SELECT 'offers', count(*) FROM scheduling.slot_offers
UNION ALL SELECT 'appointments', count(*) FROM scheduling.appointments
UNION ALL SELECT 'patients', count(*) FROM identity.patients
UNION ALL SELECT 'payments', count(*) FROM billing.payments
UNION ALL SELECT 'holidays', count(*) FROM scheduling.holidays;
```

## 4. Conteúdo clínico e RAG

### Documents parent

```sql
SELECT document_id, title, cancer_type, care_phase,
       responsible_physician, version, next_review_at
FROM content.documents
ORDER BY cancer_type, care_phase, title;
```

```sql
SELECT cancer_type, count(*) AS documents
FROM content.documents
GROUP BY cancer_type
ORDER BY cancer_type;
```

Esperado: 28 documents de mama e 29 colorretais.

```sql
SELECT cancer_type, care_phase, count(*) AS quantidade
FROM content.documents
GROUP BY cancer_type, care_phase
ORDER BY cancer_type, care_phase;
```

### Children

```sql
SELECT chunk_id, parent_document_id, ordinal, heading, urgency
FROM content.chunks
ORDER BY parent_document_id, ordinal
LIMIT 100;
```

Todos os children de uma mastectomia:

```sql
SELECT ordinal, heading, urgency, content_markdown
FROM content.chunks
WHERE parent_document_id = 'MAMA-MASTECTOMIA_SIMPLES-001'
ORDER BY ordinal;
```

Quantidade de children por parent:

```sql
SELECT d.document_id, d.title, count(c.chunk_id) AS total_children
FROM content.documents d
LEFT JOIN content.chunks c ON c.parent_document_id = d.document_id
GROUP BY d.document_id, d.title
ORDER BY total_children DESC, d.title;
```

### Busca textual

```sql
SELECT chunk_id, parent_document_id, heading, urgency,
       ts_rank_cd(
           search_vector,
           websearch_to_tsquery('portuguese', 'febre após cirurgia')
       ) AS relevancia
FROM content.chunks
WHERE search_vector @@ websearch_to_tsquery(
    'portuguese', 'febre após cirurgia'
)
ORDER BY relevancia DESC
LIMIT 10;
```

Busca filtrada para mama:

```sql
SELECT c.chunk_id, d.title, c.heading, c.urgency
FROM content.chunks c
JOIN content.documents d ON d.document_id = c.parent_document_id
WHERE d.cancer_type = 'mama'
  AND c.search_vector @@ websearch_to_tsquery(
      'portuguese', 'dreno secreção'
  )
ORDER BY ts_rank_cd(
    c.search_vector,
    websearch_to_tsquery('portuguese', 'dreno secreção')
) DESC;
```

### Metadados JSON

```sql
SELECT chunk_id,
       metadata ->> 'cancer_type' AS cancer_type,
       metadata ->> 'care_phase' AS care_phase,
       metadata ->> 'procedure_slug' AS procedure,
       metadata ->> 'section' AS section
FROM content.chunks
LIMIT 30;
```

```sql
SELECT chunk_id, heading, metadata
FROM content.chunks
WHERE metadata @> '{"cancer_type":"colorretal"}'::jsonb
LIMIT 20;
```

## 5. Q&A de atendimento

```sql
SELECT category, count(*) AS perguntas
FROM content.qa_entries
GROUP BY category
ORDER BY category;
```

```sql
SELECT qa_id, category, question, answer_markdown
FROM content.qa_entries
ORDER BY qa_id;
```

Entradas que exigem uma consulta dinâmica:

```sql
SELECT qa_id, category, question, dynamic_resolver
FROM content.qa_entries
WHERE dynamic_data_required
ORDER BY dynamic_resolver, qa_id;
```

Resolvers esperados:

```text
appointment_availability
price_lookup
payment_simulator
insurance_lookup
```

Preço, profissional, horário e disponibilidade nunca devem ser respondidos
somente pelo conteúdo vetorial.

## 6. Agenda dinâmica

### Especialidades

```sql
SELECT *
FROM scheduling.specialties
ORDER BY display_name;
```

### Profissionais e preços

```sql
SELECT s.display_name AS especialidade,
       p.display_name AS profissional,
       p.registration_display,
       ps.fixed_price_cents / 100.0 AS preco,
       ps.appointment_duration_minutes AS duracao_minutos
FROM scheduling.professional_specialties ps
JOIN scheduling.professionals p
  ON p.professional_id = ps.professional_id
JOIN scheduling.specialties s
  ON s.specialty_id = ps.specialty_id
ORDER BY s.display_name, p.display_name;
```

### Feriados

```sql
SELECT holiday_date, name, scope, state_code, city_code
FROM scheduling.holidays
ORDER BY holiday_date;
```

Testar o próximo dia útil:

```sql
SELECT scheduling.next_business_day(DATE '2026-08-09');
```

Como 09/08/2026 é domingo, o resultado esperado é `2026-08-10`.

### Gerar as ofertas dinâmicas

```sql
SELECT *
FROM scheduling.ensure_demo_availability(CURRENT_DATE);
```

Reproduzir o cenário de 08/08/2026:

```sql
SELECT *
FROM scheduling.ensure_demo_availability(DATE '2026-08-08');
```

### Consultar as ofertas

```sql
SELECT specialty_slug, offer_window, starts_at,
       professional_name,
       fixed_price_cents / 100.0 AS preco,
       unit_name
FROM scheduling.available_offers
ORDER BY specialty_slug, offer_window, starts_at;
```

Confirmar o limite de quatro:

```sql
SELECT specialty_slug, offer_window, reference_date,
       count(*) AS ofertas
FROM scheduling.available_offers
GROUP BY specialty_slug, offer_window, reference_date
ORDER BY reference_date, specialty_slug, offer_window;
```

Responsabilidades:

- `schedule_slots`: vaga física;
- `slot_offers`: quando e em qual janela a vaga pode aparecer;
- `available_offers`: view pronta para consumo.

Essa separação impede que uma vaga antiga de `D+7` se some a quatro novas vagas
quando a data chegar a `D+1`.

## 7. Pacientes e CPF

```sql
SELECT patient_id, full_name, cpf_last4,
       phone, email, created_at
FROM identity.patients;
```

Não consulte ou exiba `cpf_ciphertext` normalmente.

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'identity'
  AND table_name = 'patients'
ORDER BY ordinal_position;
```

O modelo armazena CPF cifrado, hash para detectar duplicidade e os últimos
quatro dígitos para conferência. O CPF não deve entrar em chunks, embeddings,
URLs ou Q&A.

## 8. Agendamentos e pagamentos

```sql
SELECT a.protocol, a.status, a.hold_expires_at,
       a.confirmed_at, s.starts_at,
       p.full_name, p.cpf_last4
FROM scheduling.appointments a
JOIN scheduling.schedule_slots s ON s.slot_id = a.slot_id
JOIN identity.patients p ON p.patient_id = a.patient_id
ORDER BY a.created_at DESC;
```

```sql
SELECT payment_id, appointment_id,
       amount_cents / 100.0 AS valor,
       status, payment_url, simulated,
       confirmed_at,
       refunded_cents / 100.0 AS devolvido
FROM billing.payments
ORDER BY created_at DESC;
```

Histórico de eventos:

```sql
SELECT * FROM billing.payment_events ORDER BY occurred_at DESC;
SELECT * FROM scheduling.appointment_events ORDER BY occurred_at DESC;
```

Liberar reservas expiradas:

```sql
SELECT scheduling.release_expired_holds();
```

Simular falta com retenção de 30%:

```sql
SELECT *
FROM scheduling.mark_no_show('UUID-DO-AGENDAMENTO');
```

Não execute `mark_no_show` em um agendamento que queira preservar.

## 9. Políticas e governança

```sql
SELECT policy_code, version, title, effective_from, simulated
FROM governance.policies
ORDER BY policy_code, version;
```

```sql
SELECT title, body_markdown
FROM governance.policies
WHERE policy_code = 'CANCELAMENTO';
```

As fontes e os vínculos documentais estão previstos em:

```sql
SELECT * FROM governance.sources;
SELECT * FROM content.document_sources;
```

As tabelas de fontes foram estruturadas, mas a carga inicial ainda não criou um
relacionamento detalhado entre cada documento e cada fonte. Esse é um próximo
refinamento de governança.

## 10. Testar a API

Abra:

```text
http://localhost:8000/docs
```

Rotas principais:

```text
GET  /health
GET  /v1/specialties
GET  /v1/availability
POST /v1/appointments/hold
POST /v1/appointments/{appointment_id}/simulate-payment
GET  /v1/policies/{policy_code}
GET  /v1/content/search
```

Consultar disponibilidade:

```bash
curl 'http://localhost:8000/v1/availability?specialty=mastologia-oncologica&window=NEXT_DAY'
```

Buscar conteúdo:

```bash
curl --get 'http://localhost:8000/v1/content/search' \
  --data-urlencode 'q=febre depois da cirurgia' \
  --data-urlencode 'cancer_type=mama'
```

## 11. Ordem recomendada dos arquivos

1. `README.md`: visão geral, inicialização e avisos.
2. `documents/GOVERNANCE.md`: segurança e divisão entre conteúdo estável e dados dinâmicos.
3. `docker-compose.yml`: serviços, portas e volumes.
4. `.env.example`: configuração demonstrativa.
5. `db/init/001_schema.sql`: schemas, tabelas, pgvector e índices.
6. `db/init/002_seed_and_schedule.sql`: especialidades, preços, feriados e agenda.
7. `db/init/003_content.sql`: parents e children gerados.
8. `db/init/004_qa.sql`: Q&A independente.
9. `db/init/005_lifecycle.sql`: expiração de reserva e falta.
10. `app/main.py`: API, CPF, agenda, reserva e pagamento.
11. `documents/INDEX.md`: índice dos 57 parents.
12. `documents/clinical/mama/mastectomia-simples.md`: exemplo de mama.
13. `documents/clinical/colorretal/colectomia-direita.md`: exemplo colorretal.
14. `documents/qa/atendimento-primeira-consulta.md`: Q&A completo.
15. `documents/catalog.jsonl` e `documents/qa/qa-catalog.jsonl`: catálogos técnicos.
16. `scripts/generate_documents.py` e `scripts/generate_qa.py`: fontes geradoras.

## 12. Detalhes importantes

- Os arquivos `db/init/*.sql` só são executados automaticamente quando o volume
  PostgreSQL é criado pela primeira vez.
- Alterar uma migration não modifica automaticamente um volume existente.
- `docker compose down` preserva os dados.
- `docker compose down -v` apaga o volume e os dados posteriores aos seeds.
- Os embeddings ainda estão `NULL`. O pgvector e os índices estão preparados,
  mas falta conectar um modelo de embeddings.
- A recuperação atualmente disponível usa a busca textual do PostgreSQL.
- O calendário contém feriados de 2026 e parte de 2027 e exige atualização.
- O pagamento é fictício e confirmado por temporizador, não por webhook.
- A chave de CPF e a senha do banco são demonstrativas.
- Os documentos clínicos usam conteúdo compartilhado gerado por template e
  precisam de revisão clínica individual antes de uso assistencial real.
- A API ainda não implementa autenticação, autorização, limitação de requisições
  ou auditoria completa; deve permanecer local até receber essas proteções.
