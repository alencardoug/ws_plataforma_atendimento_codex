# Data Model: Specialty Citation and Scheduling Breadth

## 1. New `content.categories` rows (SC)

```sql
INSERT INTO content.categories (slug, label) VALUES
    ('nutricao_oncologica', 'Nutrição oncológica'),
    ('endocrinologia_oncologica', 'Endocrinologia oncológica'),
    ('fisioterapia_oncologica', 'Fisioterapia oncológica')
ON CONFLICT DO NOTHING;
```

No change to `content.categories`' schema (table already exists, V3-8).

## 2. New `content.qa_entries` rows (SC)

6 rows (QA-089..QA-094), added to `documents/qa/qa-catalog.jsonl` (the
canonical ingest source, plan.md §2 — not a migration, not `db/init/*.sql`),
picked up by the existing idempotent `python -m customer_care.knowledge.ingest`
CLI. No schema change — reuses `content.qa_entries` exactly as every
existing entry does.

## 3. New `scheduling.specialties`/`professionals`/`professional_specialties` rows (SS)

```sql
INSERT INTO scheduling.specialties (specialty_id, slug, display_name, description) VALUES
('20000000-0000-0000-0000-000000000005', 'psico-oncologia', 'Psico-oncologia', '...'),
('20000000-0000-0000-0000-000000000006', 'nutricao-oncologica', 'Nutrição oncológica', '...'),
('20000000-0000-0000-0000-000000000007', 'endocrinologia-oncologica', 'Endocrinologia oncológica', '...'),
('20000000-0000-0000-0000-000000000008', 'fisioterapia-oncologica', 'Fisioterapia oncológica', '...');

INSERT INTO scheduling.professionals (professional_id, display_name, registration_display) VALUES
('30000000-0000-0000-0000-000000000013', '... (simulação)', 'CRM-SP 000013 (simulação)'),
-- ... 11 more, continuing ...014-...024

INSERT INTO scheduling.professional_specialties (professional_id, specialty_id, fixed_price_cents, appointment_duration_minutes) VALUES
-- 12 rows, 3 professionals × 4 specialties
```

No schema change — reuses the exact tables/columns 004/005 already
established. No `scheduling.schedule_slots` rows (SV's own job).

## 4. No change to `scheduling.holidays`

Already seeded through all of 2027 (`20260819_0001`'s own `INSERT`) —
confirmed by direct inspection, covers SV's full 2026-12-30 window with no
new migration.

## 5. `ai_generations` — no new column for ND's `prompt_version`

Direct inspection of `generate_draft()`'s call path: `extract_parameters()`
runs **before** any `AIGeneration` row is constructed, as part of
`resolve_appointment_availability()`'s own query-parameter resolution —
the same `AIGeneration` row's existing `prompt_version` field already
records `prompts/rag_answer.md`'s own version, not a second prompt's. Spec
§7 left the exact field open ("most likely a new nullable column... or a
dedicated field on `RetrievalRun`"); this plan resolves it as **neither**:
ND-4's traceability requirement is satisfied by a new audit event instead
(below), matching this codebase's existing precedent for a
resolution-adjacent fact that isn't itself the generation's own prompt
(e.g. `ai.dynamic_pattern_resolved`'s `specialty_slug`/`slot_count`
payload, not a new `ai_generations` column either).

New audit event `ai.date_intent_extracted` (SV/ND-4), emitted from
`_resolve_via_llm()` at the point the LLM call actually happens (only when
the pre-filter triggers it — not on every draft), payload:
`{query_text_hash: str, prompt_version: str, intent_resolved: bool}` —
`query_text_hash` (not the raw text) matching this codebase's own
Constitution Article VI framing (conversation content excluded from
ordinary logs); `prompt_version` is `date_intent.md`'s own content-hash
version (via `load_prompt()`, unchanged mechanism); `intent_resolved`
records whether §5.4's arithmetic actually produced a usable date (`True`)
or fell through (`False`) — useful for future measurement without a new
table.

## 6. No other schema change

`scheduling.schedule_slots` gains only new rows (SV), no new column.
`GenerationProvider`/`ai/providers.py` gain a new method and dataclass —
Python-level, not persisted.
