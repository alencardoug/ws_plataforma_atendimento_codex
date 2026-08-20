# Tasks: Specialty Citation and Scheduling Breadth

Governing: `spec.md`, `plan.md`, `data-model.md`. Ordered SC → SS → SV →
ND (lowest risk first, matching plan.md §1).

## Phase 1 — SC (content)

- **T1.** `20260820_0003_v6_support_specialty_categories.py` — 3 new
  `content.categories` rows.
- **T2.** 6 new lines in `documents/qa/qa-catalog.jsonl` (QA-089..QA-094),
  2 per new specialty, genuine customer-facing questions (plan.md §2).
- **T3.** Real-provider smoke-suite scenario: each new topic's question
  retrieves its own new content and cites the relevant support specialty.

## Phase 2 — SS (specialties and keywords)

- **T4.** `20260820_0004_v6_support_specialties.py` — 4 specialties, 12
  professionals, 12 `professional_specialties` rows (data-model.md §3).
- **T5.** `SPECIALTY_KEYWORDS` +4 entries in `scheduling/availability.py`.
- **T6.** Unit tests: word-boundary safety, non-collision with the 4
  existing specialties' own keyword sets.
- **T7.** Resolver-level test: a support specialty resolves through
  `price_lookup`/`appointment_availability` identically to an existing
  diagnostic one (spec.md outcome 2) — requires T4+T9 (slots must exist).

## Phase 3 — SV (wide seeding)

- **T8.** `ensure_wide_availability()` + `SeedWideResult` +
  `_WIDE_SEED_LOCK_KEY` in `scheduling/seeding.py` (plan.md §4).
- **T9.** `POST /operator/scheduling/ensure-wide-availability` in
  `scheduling/router.py`; `scheduling.wide_availability_seeded` audit
  event.
- **T10.** Frontend: new button in `OperatorPage`'s sidebar, alongside the
  existing D+1/D+7 one.
- **T11.** Tests: idempotency (second call creates 0), correct
  business-day/holiday exclusion, 45-minute spacing, covers a new SS
  specialty automatically (runs after T4).

## Phase 4 — ND (natural-language date/time)

- **T12.** `StructuredDateIntent` dataclass +
  `GenerationProvider.extract_date_intent` (protocol) in `ai/providers.py`.
- **T13.** `DeterministicTestGenerationProvider.extract_date_intent`
  (always `None`) and `OpenAIGenerationProvider.extract_date_intent`
  (real call, defensive parsing) — plan.md §5.1.
- **T14.** New `prompts/date_intent.md`.
- **T15.** `_resolve_date_intent()` (pure arithmetic, 5 rules) +
  `_add_months()` in `scheduling/availability.py` — plan.md §5.4.
- **T16.** `_looks_like_a_date_expression()` + `_resolve_via_llm()` +
  `extract_parameters(..., allow_llm_date_fallback=False)` extension —
  plan.md §5.3.
- **T17.** `resolve_appointment_availability()` passes
  `allow_llm_date_fallback=True`; `resolve_price_lookup()` does not
  (unchanged call).
- **T18.** `ai.date_intent_extracted` audit event, emitted from
  `_resolve_via_llm()` (data-model.md §5).
- **T19.** Unit tests: `_resolve_date_intent()`'s 5 rules + invalid/
  out-of-range cases (no provider needed); `extract_parameters` opt-in
  gating with a fake provider; full pre-existing
  `test_appointment_availability_keywords.py` suite passes unmodified
  (regression, outcome 7).
- **T20.** Real-provider smoke-suite scenario: the 4 example phrases
  spec.md §8 outcome 5 names, plus one genuinely ambiguous phrase falling
  through safely (outcome 6).

## Phase 5 — Gates and convergence

- **T21.** Backend `pytest`/`ruff`/`mypy`.
- **T22.** Frontend lint/typecheck/Vitest/build.
- **T23.** Full pre-existing `smoke_*.py` + Playwright suite (`v1`-`v3`,
  `v7`-`v9`) — requires a credential-backed Compose stack (deferred per
  the human's 2026-08-20 batching decision, same as 007/008/009).
- **T24.** Author `acceptance.md`/`analysis.md`; update
  `PROJECT_STATE.md`/`ROADMAP.md`/`DECISIONS.md` once the batch closes —
  this is the last of the four packages, so this also updates the
  "Immediate next action" section to reflect the whole cycle's closure.
