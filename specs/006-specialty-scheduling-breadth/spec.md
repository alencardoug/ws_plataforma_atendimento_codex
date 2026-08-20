# Feature Specification: Specialty Citation and Scheduling Breadth

**Feature ID:** `006-specialty-scheduling-breadth`
**Status:** Draft — authorized for specification 2026-08-20
**Authorized for specification:** 2026-08-20 (human, this conversation),
registered 2026-08-19 in `ROADMAP.md`
**Scope:** four bundled, related changes the human registered together
under one `ROADMAP.md` section: (SC) encourage generated answers to cite
psico-oncologia/nutrição/endocrinologia/fisioterapia oncológica when
genuinely connected to the customer's message; (SS) make those four
specialties real bookable options via the existing `price_lookup`/
`appointment_availability` resolvers; (SV) a one-time wide-window
availability seed through **2026-12-30** for every specialty, replacing
today's narrow D+1/D+7 pattern for this purpose; (ND) richer
natural-language date/time understanding for `extract_parameters` (AA-3),
so a customer can actually reach a far-future SV-seeded slot by naming a
specific date in plain language. See §6 for what this cycle does **not**
authorize.

## 1. Purpose

Today `scheduling.specialties` has exactly four rows —
`mastologia-oncologica`, `cirurgia-colorretal`, `segunda-opiniao`,
`oncologia-geral` (the AA-3a generalist default) — seeded by
`app/alembic/versions/20260819_0001_v4_scheduling_schema.py` and
`20260819_0002_v4_generalist_specialty.py`. `resolve_appointment_availability`
(AA-2) and `resolve_price_lookup` (005/PL-1..PL-4) are both already fully
generic over `specialty_slug` — neither has any hardcoded specialty
allowlist — so a new specialty becomes bookable/priceable the moment it has
`scheduling.specialties`/`scheduling.professional_specialties`/
`scheduling.schedule_slots` rows, with **zero resolver code change**. The
one place specialty coverage *is* hardcoded is
`app/customer_care/scheduling/availability.py`'s `SPECIALTY_KEYWORDS`
table (AA-3's deterministic keyword-to-slug map), which a customer message
must match for `extract_parameters()` to return anything other than the
`GENERALIST_SLUG` fallback.

Separately, `teste_humano.md`/the human's own use of the system found the
existing citation of psico-oncologia (QA-080/QA-081,
`documents/clinical/mama/apoio-emocional.md`) only appears when a customer's
message happens to retrieve those specific records — there is no equivalent
content connecting nutrição, endocrinologia, or fisioterapia oncológica to
any customer-facing question yet, so a generated answer can never cite them
no matter how relevant the customer's message is.

Finally, once SV widens the seeded window out to 2026-12-30, a customer
still has no way to *reach* a slot in, say, November by typing a plain-language
date — `extract_parameters()`'s `DATE_KEYWORDS` table only understands a
short fixed list (`amanhã`, `sábado`, `domingo`, `semana que vem`) and no
explicit calendar date or richer relative expression at all (confirmed by
direct inspection, and previously logged as an open question in
`ROADMAP.md`/D-035).

## 2. Definitions

- **Support specialty** — this cycle's term for the four specialties added
  by SS-1: `psico-oncologia`, `nutricao-oncologica`,
  `endocrinologia-oncologica`, `fisioterapia-oncologica`. Distinguished
  from the four existing **diagnostic specialties**
  (`mastologia-oncologica`, `cirurgia-colorretal`, `segunda-opiniao`,
  `oncologia-geral`) only by editorial framing (first-line diagnostic care
  vs. ongoing supportive care) — technically identical rows in
  `scheduling.specialties`/`professional_specialties`, no schema
  distinction.
- **Structured date intent** — ND's new LLM-produced JSON object (§5, ND-1)
  that a customer's free-text date/time expression is turned into before
  any arithmetic happens. Never a date string itself — only classification
  fields the deterministic code below it consumes.
- Existing terms (`dynamic_resolver`, `NAMED_RESOLVERS`,
  `dynamic_data_required`, `ExtractedParameters`, `SPECIALTY_KEYWORDS`,
  `next_business_day()`, N1/N2, `AIGeneration`, explicit operator send) are
  unchanged from V1/004/005 and `.specify/memory/constitution.md`.

## 3. Functional requirements — citation content (SC)

### SC-1 — New Q&A/clinical content connecting the three uncovered support specialties

Following the exact pattern `apoio-emocional.md`/QA-080/QA-081 already
established for psico-oncologia, author new Q&A entries (`content.qa_entries`,
next available `QA-###` IDs) and/or a new clinical document for
`nutricao-oncologica`, `endocrinologia-oncologica`, and
`fisioterapia-oncologica`, each grounded in a genuine customer-facing
question (e.g. appetite/weight loss during treatment for nutrição, hormonal
symptoms for endocrinologia, mobility/lymphedema for fisioterapia) — not a
generic "we also offer X" filler entry, since the prompt's evidence rule
(`prompts/rag_answer.md`: "every organization-specific factual claim...
must be supportable by one or more used_source_ids") means a citation can
only ever come from genuine retrieval relevance, never from a prompt
instruction alone. This is a content-authoring task (exact wording,
question phrasing, and count of new entries per specialty are
implementation-time editorial decisions, matching 005/PM-2's own
precedent), not a retrieval-mechanism change.

### SC-2 — No change to retrieval ranking, the reranker, or the prompt template

`rag/service.py`'s retrieval/ranking, `providers.py`'s `rerank_clinical`
(D-034), and `prompts/rag_answer.md` are unchanged by SC-1 — new content
competes for retrieval exactly like every existing Q&A/clinical entry
already does. "Encourage" citation means *making the grounding available*,
not steering the model to mention a specialty it has no evidence for.

## 4. Functional requirements — specialty and scheduling breadth (SS)

### SS-1 — Four new `scheduling.specialties` rows, following the existing migration pattern

A new forward-only Alembic migration (matching
`20260819_0002_v4_generalist_specialty.py`'s exact shape: raw SQL `INSERT`s,
`downgrade()` raises `RuntimeError`) adds:

- 4 new `scheduling.specialties` rows (slugs above), each with a
  `display_name`/`description` following the existing
  `"... (simulação)"` convention;
- 3 new synthetic `scheduling.professionals` rows per specialty (12 total),
  following the existing `"Dr./Dra. <name> (simulação)"` /
  `"CRM-SP 0000NN (simulação)"` convention, continuing the UUID/CRM
  numbering sequence already in use;
- matching `scheduling.professional_specialties` rows
  (`fixed_price_cents`, `appointment_duration_minutes` per specialty —
  exact pricing/duration is an implementation-time editorial decision,
  matching 005/PL-3's existing price-formatting/`format_price_brl()`
  mechanics, no new pricing logic).

No `scheduling.schedule_slots` rows are created by this migration itself —
slot creation is exclusively SV's job (§4b), matching AA-9's own
"migrations seed reference data, seeding actions seed slots" split.

### SS-2 — `SPECIALTY_KEYWORDS` gains four new entries

`availability.py`'s `SPECIALTY_KEYWORDS` dict (currently 4 entries, one
per diagnostic specialty plus the generalist fallback) gains one new
`slug: (keywords...)` entry per support specialty, matching the existing
`_contains_keyword()` word-boundary matching — e.g.
`"psico-oncologia": ("psico-oncologia", "psico oncologia", "apoio psicológico", "psicólogo", "psicologa")`,
and similarly for `nutricao-oncologica`, `endocrinologia-oncologica`,
`fisioterapia-oncologica`. Exact keyword lists are an implementation-time
editorial task, constrained only by: word-boundary-safe (no accidental
substring matches, same false-positive class `_contains_keyword`'s own
docstring already documents for "manhã" inside "amanhã"), and specific
enough not to collide with the four existing specialties' own keyword sets.

### SS-3 — `price_lookup`/`appointment_availability` need no code change

Confirmed by direct inspection of `resolve_price_lookup`/
`resolve_appointment_availability` (`availability.py`): both query purely
by `params.specialty_slug` against `scheduling.professional_specialties`/
`scheduling.schedule_slots`, with no specialty allowlist beyond
`extract_parameters()`'s own `SPECIALTY_KEYWORDS` (SS-2). Once SS-1 (rows
exist) and SV (slots exist) land, a customer's price/availability question
about a support specialty resolves through the exact same code path as an
existing diagnostic specialty — this requirement exists only to make that
explicit as an acceptance outcome (§7), not to describe new code.

## 4b. Functional requirements — seeding volume (SV)

### SV-1 — A new, separate wide-window seed action (not an AA-9 extension)

AA-9 (`ensure_seed_availability()`, `scheduling/seeding.py`) was
deliberately narrowed to the generalist specialty only by a 2026-08-19
correction (its own docstring: "faça este botão ir para a oncologia
geral") specifically because a flat D+1/D+7 target across every specialty
kept starving all but one. Widening its *scope* back out while also
widening its *date range* would reintroduce exactly that failure mode at
larger scale. This cycle instead adds a new, separate, explicitly-triggered
operator action — `ensure_wide_availability()` — for the human's own
stated one-time bulk-fill intent, leaving AA-9's existing D+1/D+7
generalist-only button untouched.

### SV-2 — Every specialty, every business day through 2026-12-30, 08:00–18:00, 45-minute spacing

For every row in `scheduling.specialties` (the 4 existing + SS-1's 4 new —
read from the table at call time, not a hardcoded list, so this action
automatically covers any specialty that exists by the time it runs), and
for every business day from tomorrow through **2026-12-30** inclusive
(`scheduling.next_business_day()` — already skips Sundays and any row in
`scheduling.holidays` with `is_business_day=false`; already seeded through
all of 2026 by `20260819_0001`'s own `INSERT`, so **no new holiday
infrastructure or data is needed** — confirmed by direct inspection),
create `schedule_slots` rows at 45-minute intervals from 08:00 up to (but
not including, matching AA-9's own `SEED_HOUR_END`-exclusive convention)
18:00 — 13 slots/day/professional (08:00, 08:45, ..., 17:15) — for every
active professional in that specialty, `ON CONFLICT DO NOTHING` on the
existing `(professional_id, starts_at)` unique constraint (idempotent,
matching AA-9's own insert pattern exactly — `create_slots_on()`'s
structure is reused, only its hour-increment and specialty-loop-scope
change).

### SV-3 — One-time, idempotent, explicit-trigger, same advisory-lock discipline as AA-9

Reachable only through one new gated operator endpoint (mirroring AA-9's
own `POST /operator/scheduling/ensure-availability` pattern exactly — new
route, e.g. `POST /operator/scheduling/ensure-wide-availability`), holding
the same `pg_advisory_xact_lock` discipline AA-9 already uses (a new, fixed
lock key, distinct from AA-9's own `_SEED_LOCK_KEY`) so two concurrent
clicks cannot double-create. Re-running it after slots already exist is a
safe no-op for those slots (`ON CONFLICT DO NOTHING`) — it does not need
AA-9's own `already_sufficient` short-circuit, since "insert whatever's
missing, skip what exists" is already idempotent by construction; the
response reports a total created-slot count instead.

### SV-4 — Audit event

Emits a new `scheduling.wide_availability_seeded` audit event (payload:
specialty count, business-day count, slots-created count), following
`scheduling.availability_seeded`'s (AA-9) existing shape and
`docs/architecture/EVENT_CATALOG.md` documentation convention.

## 5. Functional requirements — natural-language date/time (ND)

### ND-1 — Structured date intent, fixed JSON shape

A new `GenerationProvider` protocol method (alongside `generate`/
`rerank_clinical` in `ai/providers.py`), `extract_date_intent(customer_text,
reference_date) -> StructuredDateIntent | None`, returns:

```python
@dataclass(frozen=True)
class StructuredDateIntent:
    relative_unit: str | None       # "day" | "week" | "month"
    relative_count: int | None      # the N in "daqui a N <unit>"
    weekday: int | None             # 0=Monday..6=Sunday, matching _WEEKDAY_PT/_next_weekday
    nth_weekday_of_month: int | None  # 1-5, e.g. "terceira" = 3
    month: int | None               # 1-12
    day: int | None                 # explicit day-of-month, e.g. "23" in "23/11"
    time_range_start: int | None    # hour, 0-23
    time_range_end: int | None      # hour, 0-23 (exclusive, matching PERIOD_KEYWORDS convention)
```

The LLM fills in **only** the fields the customer's phrase actually states
(every field independently optional — e.g. "daqui a um mês" sets only
`relative_unit="month", relative_count=1`; "terceira quinta de outubro
entre 10 da manhã e 2 da tarde" sets `nth_weekday_of_month=3, weekday=3,
month=10, time_range_start=10, time_range_end=14`; "23/11/2026" sets
`day=23, month=11`). The LLM never computes, states, or outputs a date or
weekday name itself — only these structured classification fields,
matching this codebase's existing determinism-for-computation precedent
(AA-5/D-028's "no LLM rewrite" rule, GB-2's ordinal-parser-before-embedding
precedent). The system prompt for this call is a new file under `prompts/`
(e.g. `prompts/date_intent.md`), loaded via the existing `load_prompt()`
(`ai/prompts.py`) so it gets the same content-hash-based `prompt_version`
tracking every other prompt already has.

### ND-2 — Deterministic arithmetic, extending `extract_parameters()`

`extract_parameters()` tries its existing `DATE_KEYWORDS`/`PERIOD_KEYWORDS`
matching first (unchanged, zero regression risk — cheap, no LLM call, and
already covers the common cases). Only when neither table matches
anything **and** the message contains apparent date/time language (a cheap
pre-filter, e.g. presence of a weekday name, month name, digit sequence, or
relative-time word — exact heuristic is an implementation-time detail) does
it call `extract_date_intent()` and, if a non-null intent comes back,
resolve it deterministically in new pure code (no DB, no I/O, matching
`extract_parameters()`'s own existing purity contract):

- `relative_unit`+`relative_count` alone → `reference_date + N` days/weeks
  (weeks: `N*7` days, matching `DATE_KEYWORDS`'s own "semana que vem"
  arithmetic) or `N` calendar months forward (day-of-month clamped to the
  target month's last valid day);
- `weekday` alone → next occurrence strictly after `reference_date`,
  reusing `_next_weekday()` verbatim; `weekday` + `relative_count` > 1 →
  repeat `_next_weekday()` that many times (e.g. "daqui a 2 terças-feira" =
  the second Tuesday from now, not the first);
- `nth_weekday_of_month` + `weekday` (+ optional `month`, defaulting to the
  reference date's own month if absent) → the Nth occurrence of that
  weekday within that month; if the computed date has already passed, roll
  forward to the same nth-weekday in the next month (never invents a past
  date);
- `day` + `month` (explicit calendar date) → that date in the reference
  year, or the next year if that date has already passed this year;
- `time_range_start`/`time_range_end` → same role as today's
  `PERIOD_KEYWORDS` tuple, just with LLM-extracted bounds instead of the
  fixed manhã(0,12)/tarde(12,24) pair — feeds `ExtractedParameters.period_hours`
  unchanged downstream.

The resolved `target_date`/`period_hours` feed into the existing
`ExtractedParameters` dataclass and `resolve_appointment_availability`
query exactly as today — no change to the resolver itself, matching SS-3's
own "no resolver code change" finding.

### ND-3 — Fallback: falls through to the existing clarification path, never a fabricated date

**Decided 2026-08-20 (human, this conversation).** When `extract_date_intent`
returns `None`, returns an intent with no fields set, or the deterministic
arithmetic above cannot produce a valid, non-past date (e.g. an
out-of-range `nth_weekday_of_month`, a `day` that doesn't exist in `month`),
`extract_parameters()` returns `target_date=None` exactly as it already
does today for any unmatched date expression — `resolve_appointment_availability`
proceeds unfiltered on date (matching its own existing behavior when no
date keyword matches at all), and if that still yields no slots, the
existing `DynamicResolutionError` → manual-fallback path (AA-8's
precedent) handles it. **No new abstention category, no new customer-facing
wording** — this is a deliberate reuse of the existing insufficient-match
behavior, not a new "I didn't understand the date" response.

### ND-4 — New prompt version, new audit trace

Like every other LLM call in this codebase, the `extract_date_intent` call
is tracked: its `prompts/date_intent.md` content-hash `prompt_version` is
recorded (exact field/table is a `data-model.md`/`plan.md` decision — most
likely a new nullable column on the eventual `AIGeneration` row this
extraction contributes to, or a dedicated field on `RetrievalRun`, mirroring
how `prompt_version` already flows through `generate_draft`/
`resolve_manual_evidence`). No hidden reasoning is persisted (Constitution
Article V) — only the structured intent fields themselves.

## 6. What this cycle does **not** authorize

- Any change to Constitution Amendment 1.1.0 / AA-10's autonomous-send
  exception — this cycle touches only retrieval content (SC), reference
  data + a new seed action (SS/SV), and `extract_parameters()` (ND); no
  code path in this feature calls `send_scripted_message()` or anything
  that creates a customer-visible message outside the existing
  explicit-operator-send/draft model.
- A scheduling-data CRUD admin UI — still deferred, unchanged from 004's
  own deferral (`ROADMAP.md`).
- `insurance_lookup`/`convenio` — untouched, unchanged from 005/PM-4.
- Real booking, holds, identity/payment persistence — unchanged from
  004 §6/005 §6; SS/SV only add reference data and availability rows, they
  do not touch `ScheduleSlot.status` transitions or any booking-completion
  mechanism (that is `007-completed-booking-visibility`'s separate scope).
- Extending GB (005) to interpret support-specialty-specific replies any
  differently than existing specialties — GB-2's ordinal/embedding
  matching is specialty-agnostic already and needs no change.
- Removing or renaming any of the 4 existing specialties, professionals,
  or their seeded slots — this cycle is additive only.
- A general-purpose calendar/NLP library or dependency — ND-1/ND-2 reuse
  the existing `GenerationProvider`/prompt-versioning machinery and
  `datetime`/`zoneinfo` stdlib only, matching Constitution Article VIII
  (no new infrastructure without a measured requirement).

## 7. Data model impact (elaborated in `data-model.md`)

- 4 new `scheduling.specialties` rows, 12 new `scheduling.professionals`
  rows, 12 new `scheduling.professional_specialties` rows — one forward-only
  migration, data-only (SS-1).
- Up to several hundred thousand new `scheduling.schedule_slots` rows from
  SV-2 (4 existing + 4 new specialties × up to 12 professionals × ~13
  slots/day × ~90 remaining business days through 2026-12-30 from a
  2026-08-20 authorization date — exact count is a `plan.md`/acceptance-time
  calculation, not pinned here) — no schema change, reuses the existing
  `schedule_slots` table/constraint exactly as AA-9 already does.
- No change to `scheduling.holidays` — already covers the full seeding
  window (confirmed: seeded through 2027-12-25 by `20260819_0001`).
- A new field to carry ND-1's `prompt_version` for the date-intent
  extraction call (exact column/table TBD in `data-model.md` — see ND-4).
- `content.qa_entries`: several new rows for SC-1 (exact count is an
  implementation-time editorial decision) — no schema change, same
  content-hash-driven re-embedding path (`knowledge/ingest.py`) every
  existing Q&A edit already uses.

## 8. Acceptance outcomes to develop into executable tests

1. A customer message genuinely connected to nutrição/endocrinologia/
   fisioterapia oncológica context (matching SC-1's new content) retrieves
   that content and the generated `ANSWER` cites the relevant support
   specialty — grounded, not templated.
2. A customer message asking the price of, or availability for, any of the
   4 new support specialties resolves through `price_lookup`/
   `appointment_availability` exactly like an existing diagnostic
   specialty — no code branch distinguishes them (SS-3).
3. After running the new wide-availability seed action once, every
   specialty (8 total) has bookable slots on every business day through
   2026-12-30, none on a `scheduling.holidays` non-business-day row or a
   Sunday, spaced 45 minutes 08:00–17:15 — verified by direct query, not
   just a success message.
4. Re-running the wide-availability seed action a second time creates zero
   additional slots (idempotent) and still reports success.
5. A customer message using each of the newly-supported NL date
   expressions (at minimum: "daqui a 2 terças-feira", "daqui a um mês",
   "terceira quinta de outubro entre 10 da manhã e 2 da tarde", and one
   explicit `DD/MM/YYYY`-style date) resolves to the exact intended
   calendar date/time-range and, combined with SV's wide seeding, actually
   returns a matching slot when one exists on that date.
6. A genuinely ambiguous or unresolvable date expression falls through to
   the existing manual/insufficient-evidence path — never a fabricated or
   incorrect date, never a new bespoke "couldn't understand the date"
   message (ND-3).
7. `extract_parameters()`'s pre-existing `DATE_KEYWORDS`/`PERIOD_KEYWORDS`
   matches (amanhã, sábado, domingo, semana que vem, manhã, tarde) are
   unchanged — zero regression, verified by the existing 004 test suite
   passing unmodified.
8. The full pre-existing `smoke_*` suite and `v1/v2/v3/v4` Playwright suite
   continue passing unmodified.
9. No new customer-visible message is ever created outside an
   authenticated-operator-send call chain or AA-10's own unchanged
   autonomous path — this feature adds no new send mechanism.

## 9. Decisions resolved with the human (2026-08-20)

1. **Structured date-intent shape** — the fixed JSON shape in §5/ND-1
   (`relative_unit`, `relative_count`, `weekday`, `nth_weekday_of_month`,
   `month`, `day`, `time_range_start`, `time_range_end`), all fields
   independently optional, LLM classifies only — chosen over leaving the
   shape open until `plan.md`, so `plan.md`/`data-model.md` can design
   directly against a fixed contract.
2. **Fallback behavior on low-confidence/unresolvable date parsing** —
   falls through to the existing manual/clarification path exactly as any
   other insufficient-match case today; explicitly **not** a new
   differentiated "I didn't understand the date" abstention category
   (§5/ND-3) — chosen to avoid a new response category needing its own
   design/copy/testing for a case the existing safe-fallback behavior
   already covers correctly.
3. **SV is a new, separate seed action, not an AA-9 extension** — implicit
   in the human's own framing ("a seeding-volume/date-range decision,
   separate from... extract_parameters", `ROADMAP.md`) and confirmed by
   this spec's own SV-1 finding that AA-9 was deliberately narrowed to
   single-specialty scope by a recent correction; widening it back out
   would reintroduce the failure mode that correction fixed.
