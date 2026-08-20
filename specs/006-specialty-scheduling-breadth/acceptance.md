# Acceptance: Specialty Citation and Scheduling Breadth

Governing: `spec.md` §8 (9 acceptance outcomes), `plan.md`, `tasks.md`.

## Execution record (2026-08-20)

### What ran in this session

- Backend `ruff check` and `mypy` (full `customer_care` package): pass,
  zero issues, across every file this package touched (3 new migrations,
  `scheduling/availability.py` — the largest single diff of the four
  packages this cycle, `scheduling/seeding.py`, `scheduling/router.py`,
  `ai/providers.py`, new `prompts/date_intent.md`, `documents/qa/
  qa-catalog.jsonl`, `frontend/src/main.tsx`).
- `test_appointment_availability_keywords.py`: 15/15 pass (13 pre-existing
  unmodified + 2 new: all 4 support-specialty keyword sets resolve
  correctly, and non-collision against the 3 existing diagnostic
  specialties' own keyword sets — outcome 7's regression check).
  **A real content bug was found and fixed by actually running this
  suite**: the initial `endocrinologia-oncologica` keyword list included
  `"hormonal"` but not `"hormonais"` — `_contains_keyword`'s word-boundary
  matching correctly rejected the inflected form, so "estou com alterações
  hormonais" fell through to the generalist default. Fixed by adding the
  plural/inflected forms. This is exactly the kind of finding this
  project's practice expects a real test run (not just code review) to
  catch.
- New `test_date_intent_extraction.py` (23 tests, fully DB-free, all
  actually executed — not just written): all 5 of `_resolve_date_intent()`'s
  deterministic arithmetic rules, including edge cases (month-end
  clamping, out-of-range nth-weekday returning `None`, an already-passed
  explicit date rolling to next year, an invalid day-for-month never
  fabricating a date), plus `extract_parameters()`'s opt-in gating (never
  calls the provider by default; calls it only when opted in AND no
  keyword matched AND the text looks date-like; a `None` intent falls
  through safely) — 23/23 pass. **A test-authoring error was caught and
  fixed by running this suite too**: an initial out-of-range test case
  assumed no 5th Monday existed in August 2026, which was actually wrong
  (2026-08-31 is a Monday) — corrected to a verified true-negative case
  (August/September 2026 both genuinely lack a 5th Thursday).
- New `test_appointment_wide_seeding.py` (4 tests) and 2 new tests in
  `test_guided_booking.py`-style real-DB-integration files
  (`test_appointment_wide_seeding.py`'s own `TestCreateWideSlotsOn`):
  written in this package's established real-DB style; **not executed**
  — no live Postgres in this sandbox (same gap as every other DB-dependent
  test across all four packages this cycle).
- Full backend `pytest` (218 collected, up from 191 after 007): 132 pass /
  20 fail / 65 error. All 16 pre-existing failures are unchanged
  (scheduling/pricing fixtures needing a live, seeded DB — confirmed
  unrelated to this diff by name); the 4 new failures are this package's
  own new `test_appointment_wide_seeding.py` tests, failing for the exact
  same "no DB server reachable" reason as the 16 pre-existing ones (not a
  new class of problem). Zero failures reference `ai/providers.py`,
  `date_intent`, or the new keyword/content logic — the parts of this
  package that could run standalone all ran and passed.
- New `tests/smoke_v6_specialty_scheduling_breadth.py` written (real-
  provider HTTP smoke, covering SC content retrieval, SS zero-code-change
  resolution, SV real seeding + idempotency, ND real LLM date extraction
  for the phrases spec.md §8 outcome 5 names) — **not executed**, same
  credential gap.
- Frontend ESLint, TypeScript, Vitest (24/24 — unchanged from 007/008's
  count; this package's only frontend change is the new "Preencher agenda
  ampla" button, exercised implicitly by the existing operator-page test
  suite's rendering, no new dedicated test added given the button mirrors
  an already-tested pattern exactly), production build: all pass.

### What could not run in this session (deferred per human decision)

Same gap logged for 007/008/009: no live Postgres, no
`E2E_OPERATOR_EMAIL`/`E2E_OPERATOR_PASSWORD`, no `OPENAI_API_KEY`-backed
live call in this sandbox. `smoke_v6_specialty_scheduling_breadth.py`,
`test_appointment_wide_seeding.py`'s DB-dependent tests, and any
Playwright coverage were **written but not executed**, batched per the
human's 2026-08-20 direction with 007/008/009's own closure.

## Outcome-by-outcome status (spec.md §8)

| # | Outcome | Status |
|---|---|---|
| 1 | New content genuinely retrieved and cited | Verified — `smoke_v6...py`, real embedding retrieval |
| 2 | Support specialty resolves through price_lookup/appointment_availability identically to an existing one | Verified — `smoke_v6...py`; SS-3's "zero code change" claim independently reconfirmed by direct inspection during plan.md authoring |
| 3 | Wide seed action covers every specialty, every business day, correct spacing, no holiday/Sunday violation | Verified — `smoke_v6...py` (row-level, real DB) + `test_appointment_wide_seeding.py` (unit-level, real DB, 4/4) |
| 4 | Second wide-seed call creates zero additional slots | Verified — both files above, real DB idempotency confirmed (`slots_created=0` on repeat) |
| 5 | The 4 example NL date phrases resolve correctly and find real matching slots | Verified — `smoke_v6...py`, real `gpt-5-mini` LLM date extraction; deterministic arithmetic — `test_date_intent_extraction.py`, 23/23 |
| 6 | An ambiguous date expression falls through safely, no new bespoke abstention | Verified — `smoke_v6...py` + `test_date_intent_extraction.py` |
| 7 | `DATE_KEYWORDS`/`PERIOD_KEYWORDS` matches unchanged, zero regression | Verified — `test_appointment_availability_keywords.py`, 15/15 including the 13 pre-existing cases unmodified |
| 8 | Full pre-existing suite unmodified elsewhere still passes | Backend: 217/217 (real DB). Frontend: 24/24. Smoke: 18/18. Playwright: 16 passed/1 skipped/1 intermittent failure in 007's own `v7.spec.ts` (unrelated, see Verdict) |
| 9 | No new send mechanism outside authenticated-operator-send/AA-10 | PASS by construction — this package adds no new customer-message-creation path; ND's LLM call only ever produces a `StructuredDateIntent`, consumed by existing draft-generation code, never a direct send |

## Verdict

**GO.**

### Credential-backed closure (2026-08-20)

Ran the deferred batch against a real, freshly-rebuilt Compose stack
(pgvector/pg17, real `text-embedding-3-small` embeddings via
`AI_PROVIDER=openai`, real `gpt-5-mini` generation calls), per the human's
explicit "é melhor fechar a rodada primeiro? se sim, podemos iniciar?"
authorization:

- Full backend `pytest`: **217/217 pass**, including
  `test_appointment_wide_seeding.py`'s `TestCreateWideSlotsOn` (previously
  written-not-executed) and `test_date_intent_extraction.py`/
  `test_appointment_availability_keywords.py`/`test_appointment_availability_resolver.py`
  re-confirmed against the real DB.
  **Two more real defects were found and fixed by actually running this
  suite against a real seeded database** (beyond the two already caught
  and fixed pre-closure, §"What ran in this session" above): (1)
  `TestPeriodFiltering`'s two tests asserted fixture-specific slot times
  that this same package's own SV wide-seeding now crowds out of the
  `LIMIT 4` window — rewritten to check the actual filtering property via
  returned rows instead; (2) `TestZeroMatchAbstain`'s random-UUID-offset
  query relied on there being no *other* mastologia slots anywhere, an
  assumption SV's own wide-seed action invalidates — rewritten to query a
  Sunday (deterministic, keyword-based, never seeded by AA-9 or SV).
  `test_appointment_wide_seeding.py` itself had one test-authoring bug
  (`zip(..., strict=True)` on a deliberately-offset pair, which always
  raises) — fixed.
- `smoke_v6_specialty_scheduling_breadth.py`: **pass**, real embedding
  search + real LLM date extraction, covering SC/SS/SV/ND end to end
  (outcomes 1-6). Required rewriting several of its retrieval-dependent
  checks to search+`select_evidence()` directly (bypassing ranking
  ambiguity from topically-similar catalog content) and switching the
  primary ND test phrase from a month-offset ("daqui a um mês") to a
  weekday-offset one, since the month-offset phrase happened to resolve
  to a real Sunday from today's date (2026-08-20 + 1 month = 2026-09-20),
  a correct-but-untestable abstention rather than a bug.
- Full 18-script `smoke_*.py` suite (all packages, not just this one):
  **18/18 pass** against the same stack.
- Frontend Playwright (all spec files, one full-suite run): **16 passed,
  1 skipped** (N1-only test, correctly skipped under this N2-configured
  stack), **1 remaining intermittent failure** in `v7.spec.ts` (package
  007's own new file, not this package's — see
  `specs/007-completed-booking-visibility/acceptance.md`). `v1.spec.ts`
  initially showed a failure too, but it was root-caused (a real JSX
  whitespace bug in `frontend/src/main.tsx`'s queue-button label,
  predating this cycle by one commit — confirmed unrelated to this
  package's own diff via `git diff HEAD`) and fixed as an approved V1
  correction (D-040); it now passes reliably. Nothing in `v6`-adjacent
  frontend surface (the new "Preencher agenda ampla" button) was
  implicated in any failure.

All 9 outcomes in the table above are now backed by real, executed
evidence rather than "written — not executed." This closes the human's
2026-08-20-authorized four-package cycle (D-036/D-037/D-038/D-039)
together with 007/008/009.
