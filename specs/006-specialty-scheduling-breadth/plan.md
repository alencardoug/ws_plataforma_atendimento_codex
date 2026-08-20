# Implementation Plan: Specialty Citation and Scheduling Breadth

Governing spec: `spec.md`. Constitution: `.specify/memory/constitution.md`
(unchanged — spec.md §6).

## 1. Technical summary

Four independent pieces, ordered by risk (lowest first, matching spec.md's
own SC→SS→SV→ND presentation order):

1. **SC** — content-only: new Q&A entries via the existing
   `documents/qa/qa-catalog.jsonl` ingest source (§2). No code.
2. **SS** — one data-only migration (4 specialties, 12 professionals, 12
   `professional_specialties` rows) + 4 new `SPECIALTY_KEYWORDS` entries.
   Confirmed by direct inspection (spec.md §4/SS-3): `resolve_price_lookup`/
   `resolve_appointment_availability` need zero code change.
3. **SV** — one new seed action/endpoint, reusing `seeding.py`'s exact
   insert pattern with a wider specialty loop and 45-minute spacing.
4. **ND** — the only genuinely new mechanism: one new `GenerationProvider`
   method, one new prompt, and an LLM-gated (opt-in, not default) extension
   to `extract_parameters()`.

## 2. SC — content source and category registry

Direct inspection of `knowledge/ingest.py`'s `ingest()` found the actual
canonical source for Q&A content is `documents/qa/qa-catalog.jsonl` (JSON
Lines, one `{qa_id, category, question, answer, dynamic_data_required,
dynamic_resolver, metadata}` object per line) — **not** `db/init/004_qa.sql`
(that file is the one-time fresh-database seed, out of sync with the
canonical catalog for anything added after V1's original launch) and
**not** a migration. New entries are appended to the `.jsonl` file; the
existing `python -m customer_care.knowledge.ingest` CLI (idempotent,
content-hash-gated) picks them up on the next run — the same mechanism
005/PM-2's own content correction used.

`QAEntry.category` is FK-constrained to `content.categories.slug`
(`20260818_0001`'s migration) — no existing category fits nutrição/
endocrinologia/fisioterapia (confirmed: `apoio_emocional` is the closest,
covers psico-oncologia only). New migration
`20260820_0003_v6_support_specialty_categories.py` inserts 3 new category
rows (`nutricao_oncologica`, `endocrinologia_oncologica`,
`fisioterapia_oncologica`) — additive, matches `20260818_0001`'s own
`INSERT ... ON CONFLICT DO NOTHING` shape.

6 new Q&A entries (QA-089..QA-094, next available IDs — confirmed by
inspecting the catalog's current highest, QA-088), 2 per new specialty,
each grounded in a genuine customer-facing question (matching spec.md
SC-1's "not a generic 'we also offer X' filler" requirement):
appetite/weight-loss-during-treatment and food-safety-during-chemo for
nutrição; hormonal-symptom and thyroid/hormone-monitoring-during-treatment
for endocrinologia; mobility/lymphedema and post-surgery-strength
questions for fisioterapia. Exact wording is this plan's own editorial
task (spec.md's own explicit allowance).

No change to `rag/service.py`, `providers.py`'s `rerank_clinical`, or
`prompts/rag_answer.md` (spec.md SC-2, unaffected by construction — new
content competes for retrieval exactly like every existing entry).

## 3. SS — reference data and keyword extension

New migration `20260820_0004_v6_support_specialties.py`, same shape as
`20260819_0002_v4_generalist_specialty.py`: 4 `scheduling.specialties`
rows, 12 `scheduling.professionals` rows (3 per specialty, continuing the
existing UUID/CRM numbering — professionals `...013`-`...024`,
specialties `...005`-`...008`), 12 `scheduling.professional_specialties`
rows. No `schedule_slots` rows (SV's job, per SS-1's own note).

`SPECIALTY_KEYWORDS` (`scheduling/availability.py`) gains 4 entries —
word-boundary-safe, non-colliding with the 4 existing specialties'
keyword sets (checked against the existing 4 sets directly, not just by
inspection of the new ones alone).

SS-3 requires no code change to either resolver — reconfirmed by this
plan's own re-reading of both functions (§1 above); this is an acceptance
outcome (spec.md §8 outcome 2), not a task.

## 4. SV — wide-window seed action

New function `ensure_wide_availability()` in `scheduling/seeding.py`,
reusing `create_slots_on()`'s exact `ON CONFLICT DO NOTHING`/`RETURNING`
insert pattern (`availability.py`'s import of `ScheduleSlot`/`Professional`/
etc. already covers what's needed) but:

- looped over **every** `scheduling.specialties` row (read live via
  `select(Specialty.specialty_id)`, not a hardcoded list — SV-2's own
  "automatically covers any specialty that exists by the time it runs"
  requirement);
- looped over every business day from tomorrow through **2026-12-30**
  (`next_business_day_sql()` reused, iterated day-by-day — `scheduling.
  holidays` already covers this whole window, confirmed by spec.md §4b/
  SV-2's own direct inspection);
- 45-minute spacing, 08:00 up to (not including) 18:00 — **14** slots/day/
  professional (08:00, 08:45, ..., 17:45; verified against a real
  database — spec.md's own illustrative "13 slots... 17:15" text does not
  reconcile with its own 45-minute/18:00-exclusive rule under any
  reading, and an earlier draft of this plan miscounted it as 13 ending
  17:00 by hand arithmetic before catching the error against real data —
  see `seeding.py`'s own docstring), replacing `create_slots_on()`'s
  hour-only increment with a `timedelta(minutes=45)` step function,
  `_SEED_HOUR_END`-exclusive matching AA-9's own convention;
- targets "every missing slot", not a fixed count — no
  `already_sufficient` short-circuit (SV-3's own note: `ON CONFLICT DO
  NOTHING` is already idempotent by construction), so this function
  returns a single `created_count: int`, not `SeedResult`'s
  d1/d7/already_sufficient shape.

New endpoint `POST /operator/scheduling/ensure-wide-availability`
(`scheduling/router.py`), same shape as `ensure-availability`, holding a
**new**, distinct `pg_advisory_xact_lock` key (`_WIDE_SEED_LOCK_KEY`,
arbitrary fixed constant ≠ `_SEED_LOCK_KEY`) — SV-3's own explicit
requirement, so this action and AA-9's D+1/D+7 button can never block each
other unnecessarily while each still serializes against concurrent clicks
of itself.

New audit event `scheduling.wide_availability_seeded` (SV-4), payload
`{specialty_count, business_day_count, slots_created}`.

### 4.1 Row-count and runtime risk (spec.md §7's own open question)

8 specialties × 3 professionals each × 14 slots/day × ~90 remaining
business days (2026-08-20 to 2026-12-30, minus Sundays/holidays) is on the
order of 30,000 rows (8×3×14×90) and a single request that could run for
several seconds to low tens of seconds. Mitigated by: (a) `ON CONFLICT DO
NOTHING` batched per `(day, professional, interval)` exactly like AA-9
already does (no behavior change, same statement shape, just iterated
more times); (b) this is an explicit, rare, one-time operator action (not
a request-path/customer-facing operation, no latency budget to protect);
(c) the advisory lock already bounds concurrent execution to one caller
at a time. No pagination/background-job infrastructure is introduced
(Constitution Article VIII) — a future finding that this is too slow in
practice would be a new, separately-authorized correction, not something
this plan pre-solves speculatively.

## 5. ND — natural-language date/time extraction

### 5.1 Provider protocol extension

`GenerationProvider` (`ai/providers.py`) gains:

```python
@dataclass(frozen=True)
class StructuredDateIntent:
    relative_unit: str | None
    relative_count: int | None
    weekday: int | None
    nth_weekday_of_month: int | None
    month: int | None
    day: int | None
    time_range_start: int | None
    time_range_end: int | None

class GenerationProvider(Protocol):
    ...
    def extract_date_intent(self, customer_text: str, reference_date: date) -> StructuredDateIntent | None: ...
```

`DeterministicTestGenerationProvider.extract_date_intent` always returns
`None` — matching `rerank_clinical`'s own established "no real semantic
judgment, conservative stand-in" precedent; genuine extraction quality is
smoke-tested against the real provider only (same unit-vs-smoke split
this codebase already uses everywhere else this pattern applies).

`OpenAIGenerationProvider.extract_date_intent` loads
`prompts/date_intent.md` via `load_prompt("date_intent.md")` (existing
function, already supports a `name` parameter — no change needed there),
calls the model with `response_format={"type": "json_object"}` (matching
`rerank_clinical`'s own call shape), and parses the 8 fields — any missing/
invalid field defaults to `None` rather than raising, matching this
provider's general defensive-parsing style (`rerank_clinical`'s own
`payload.get("chosen") == "B"` never raises on a malformed response
either). Returns `None` only on a hard parse failure (e.g. non-JSON
response) — a well-formed response with every field `None` is a valid,
distinct "the model found nothing" result, still returned (not coerced
to `None`), so `extract_parameters()`'s own arithmetic layer (§5.3) can
distinguish "provider failed" from "provider understood nothing" — both
end up falling through identically today, but keeping them distinct in
the return type avoids conflating two different failure classes for a
future caller that might want to (e.g. a future audit/metrics need).

### 5.2 New prompt: `prompts/date_intent.md`

New file, following `prompts/rag_answer.md`'s existing convention (plain
Markdown, no template variables — the customer text/reference date are
passed as the user-turn content, matching `rerank_clinical`'s own
`system_prompt` + separate user-turn split, not string-interpolated into
the system prompt). Content: instructs the model to classify only the 8
`StructuredDateIntent` fields from the customer's message, explicitly
forbidding it from computing or stating a date/weekday name itself
(spec.md ND-1's own "never computes... only structured classification
fields" requirement) — this is the actual safety property this whole
mechanism relies on, so the prompt states it as a hard constraint, not a
suggestion, matching `rag_answer.md`'s own existing tone for its
evidence-grounding rule.

### 5.3 `extract_parameters()`: opt-in LLM fallback, not a signature break

Direct inspection (`availability.py:80`) confirms `extract_parameters()`
is documented and relied upon as **pure, deterministic, no I/O** —
`test_appointment_availability_keywords.py`'s own file docstring states
this explicitly, and calls it directly with 1-2 positional args in ~20
existing test cases. `resolve_price_lookup()` also calls it but
**discards** `target_date`/`period_hours` entirely (its own docstring:
"date/period are irrelevant here and ignored") — calling the LLM fallback
there would be pure waste, not just a purity violation.

**Resolution:** a new keyword-only parameter,
`allow_llm_date_fallback: bool = False`, defaulting to `False` so every
existing call site and test keeps its exact current behavior (the
fallback branch is simply unreachable when the flag is `False` — no
provider is even looked up). Only `resolve_appointment_availability()`
passes `allow_llm_date_fallback=True`; `resolve_price_lookup()` does not.
The function's docstring is updated to describe the new conditional
behavior precisely, rather than silently leaving the "pure, no I/O" claim
inaccurate.

```python
def extract_parameters(query_text: str, reference_date: date | None = None, *, allow_llm_date_fallback: bool = False) -> ExtractedParameters:
    ...  # existing DATE_KEYWORDS/PERIOD_KEYWORDS matching, unchanged
    if target_date is None and allow_llm_date_fallback and _looks_like_a_date_expression(text):
        target_date, period_hours = _resolve_via_llm(text, today, period_hours)
    return ExtractedParameters(...)
```

`_looks_like_a_date_expression()` (new, private, pure): the cheap
pre-filter spec.md ND-2 calls for — presence of a weekday name, a month
name, a digit sequence matching a plausible day/date pattern, or a
relative-time word (`"daqui"`, `"próxim"`/`"proxim"`, `"semana"`, `"mês"`/
`"mes"`) not already caught by `DATE_KEYWORDS`. Exact heuristic is this
plan's own editorial task (spec.md's own explicit allowance) — false
positives only cost one extra LLM call that then likely returns an
all-`None` intent (harmless, falls through identically to today); false
negatives just mean ND doesn't help for a phrasing outside this list, an
acceptable degradation for a heuristic, not a correctness bug.

`_resolve_via_llm()` (new, private): calls
`configured_generation_provider().extract_date_intent(text, today)`
(`ai.providers` imported at module level in `scheduling/availability.py`
— confirmed safe, no import cycle: `ai/providers.py` only imports
`rag.service`/`shared.settings`, neither of which imports `scheduling.*`).
On a non-`None` intent, resolves it via the deterministic arithmetic in
§5.4; on `None` (provider failure or deterministic-test stand-in), returns
`(None, period_hours)` unchanged — ND-3's own explicit fallback contract.

### 5.4 Deterministic arithmetic (new, pure, no I/O — takes only the
already-extracted `StructuredDateIntent` and `today`)

New function `_resolve_date_intent(intent: StructuredDateIntent, today: date) -> tuple[date | None, tuple[int, int] | None]`
implementing spec.md ND-2's five rules exactly:

1. `relative_unit`+`relative_count` → `+N` days, `+N*7` days (weeks), or
   `+N` calendar months (day-of-month clamped via a small
   `_add_months()` helper — `date`'s own arithmetic doesn't support month
   addition natively).
2. `weekday` alone → `_next_weekday()` (reused verbatim);
   `weekday`+`relative_count>1` → repeat `_next_weekday()` that many
   times, each call using its own previous result as the new reference.
3. `nth_weekday_of_month`+`weekday` (+ optional `month`, defaulting to
   `today`'s own month) → iterate occurrences of that weekday within the
   target month, take the Nth; if already past, roll forward one month
   and repeat once (never invents a past date — if still not found,
   returns `None`, matching ND-3).
4. `day`+`month` → that date in `today`'s year, or next year if already
   passed.
5. `time_range_start`/`time_range_end` → returned as `period_hours`
   directly, independent of whether a date was also resolved (matches
   `PERIOD_KEYWORDS`'s own independence from `DATE_KEYWORDS` today).

Any rule that can't produce a valid, non-past date (out-of-range
`nth_weekday_of_month`, a `day` that doesn't exist in `month`, e.g. 31/04)
returns `(None, period_hours)` — ND-3's explicit "no new abstention
category, falls through to the existing insufficient-match behavior."

## 6. Module boundaries

- `documents/qa/qa-catalog.jsonl` — 6 new lines (SC).
- **New migration** `20260820_0003_v6_support_specialty_categories.py` (SC).
- **New migration** `20260820_0004_v6_support_specialties.py` (SS).
- `scheduling/availability.py` — `SPECIALTY_KEYWORDS` (+4 entries, SS);
  `extract_parameters()` extended (ND, §5.3); new `_looks_like_a_date_expression()`,
  `_resolve_via_llm()`, `_resolve_date_intent()`, `_add_months()` (ND);
  new top-level import `from customer_care.ai.providers import
  configured_generation_provider, StructuredDateIntent`.
- `scheduling/seeding.py` — new `ensure_wide_availability()`,
  `SeedWideResult` dataclass, `_WIDE_SEED_LOCK_KEY` (SV).
- `scheduling/router.py` — new `POST .../ensure-wide-availability` (SV).
- `ai/providers.py` — `StructuredDateIntent`, `GenerationProvider.extract_date_intent`,
  both implementations (ND).
- **New file** `prompts/date_intent.md` (ND).
- `frontend/src/main.tsx` — new "Preencher agenda ampla (até 2026-12-30)"
  button alongside the existing D+1/D+7 one (mirrors that button's own
  minimal UI — a click + a status message, no new form).

## 7. Test plan

- SC: retrieval test confirming a genuine nutrição/endocrinologia/
  fisioterapia question surfaces the new Q&A content (deterministic-test
  embeddings can't prove semantic relevance — this is a real-provider
  smoke-suite addition, matching every prior content-only change's own
  testing split).
- SS: `SPECIALTY_KEYWORDS` unit tests for the 4 new entries (word-boundary,
  non-collision); a resolver-level test confirming
  `resolve_price_lookup`/`resolve_appointment_availability` handle a new
  specialty identically to an existing one once seeded.
- SV: `ensure_wide_availability()` unit/integration tests — idempotency
  (second call creates zero), correct business-day/holiday exclusion,
  correct 45-minute spacing, covers a newly-added SS specialty
  automatically.
- ND: `_resolve_date_intent()` pure unit tests for all 5 rules plus the
  invalid/out-of-range cases (deterministic, no provider needed);
  `extract_parameters(..., allow_llm_date_fallback=True)` tests using a
  fake provider (matching `test_automatic_draft_status.py`'s fake-session
  style) to confirm the opt-in gating and pre-filter; a real-provider
  smoke-suite scenario for the four example phrases spec.md §8 outcome 5
  names.
- Regression: the full existing `test_appointment_availability_keywords.py`
  suite passes unmodified (spec.md outcome 7) — `allow_llm_date_fallback`
  defaults to `False`, so no existing call changes behavior.

## 8. Risks

- **Risk:** a real LLM call inside what was a pure/instant function could
  add latency to `resolve_appointment_availability`. **Mitigation:** only
  triggered by the cheap pre-filter failing to find a keyword match but
  still finding date-like language — the common case (a keyword match, or
  no date language at all) pays zero extra cost; this matches ND-2's own
  "tries existing tables first... zero regression risk" framing.
- **Risk:** SV's row volume (§4.1) could make the endpoint slow enough to
  hit a client/proxy timeout. **Mitigation:** documented as a known,
  accepted characteristic of a rare one-time action, not silently ignored;
  a future timeout finding is new scope, not this plan's to solve.
