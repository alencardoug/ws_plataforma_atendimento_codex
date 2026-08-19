# Tasks: Dynamic Appointment Availability

Execution rule: complete in dependency order. No task in this package writes
to `scheduling.appointments`/`appointment_events`, `identity.*`, or
`billing.*`, or implements `price_lookup`/`payment_simulator`/
`insurance_lookup` — those remain out of scope per `spec.md` §6. The query
path (`scheduling/availability.py`) never writes anything, under any
circumstance. There are exactly five places anything is written in this
feature: T008's one-time migration (creating the `scheduling` schema itself
plus the original 3 specialties' seed data — correction, `data-model.md`
§5, found 2026-08-19 during the post-V3 production sync: neither
`db/init/001_schema.sql` nor `002_seed_and_schedule.sql` was ever wired
into any automated init path, confirmed against both the local and
production databases), T009's one-time migration (seeding the new
generalist specialty), T090's one-time migration (the booking-script
columns — all three applied once by Alembic, not a runtime code path),
`scheduling/seeding.py` (reachable only through the one new operator
endpoint, Phase 4), and `booking_script/service.py`'s
`send_scripted_message()` (reachable only through
`advance_booking_script()`, Phase 9 — the one function in the whole
codebase authorized to send a customer-visible message without an operator
click, Constitution Amendment 1.1.0/D-031). No other task writes anything.

Legend: `[P]` parallelizable after its listed dependency;
`[AA-x]` primary confirmed-outcome mapping (`spec.md` §3).

## Phase 0 — SDD gates

- [x] **T000** Read the constitution, `spec.md`, `plan.md`, `data-model.md`,
  V1/V2's own `plan.md`/`data-model.md` sections on the legacy `scheduling`
  schema, and the current `ai/router.py`/`knowledge/dynamic_binding.py`
  implementation this plan extends. Confirm every table/column/function
  name `plan.md` cites against the real `db/init/001_schema.sql`/
  `002_seed_and_schedule.sql` source, not from memory. Done during
  `plan.md`/`data-model.md` authoring — every cited name was confirmed
  against the real source, not guessed (`analysis.md` §3).
- [x] **T001** Run cross-artifact review of `spec.md` vs `plan.md` vs
  `data-model.md`; record findings/repairs in this package's `analysis.md`
  before implementation starts. Done 2026-08-18, revised three times more
  the same day: after the second round split the design into a read-only
  query path (AA-2, revised) and a new explicit operator-triggered seed
  action (AA-9); after the fourth round corrected "no specialty named" to
  mean a seeded generalist specialty (AA-3a); after the fifth round added
  AA-10 (the booking script) and, with it, Constitution Amendment 1.1.0 —
  `analysis.md` §10 covers this latest, largest revision, including a
  dedicated review of the autonomous-send exception's containment. 1
  finding repaired pre-revision (`Professional.active` filtering),
  re-confirmed still correct in the current `scheduling/seeding.py`.

**Gate:** `analysis.md`'s pre-implementation section shows no unresolved
contradiction. **Passed.**

## Phase 1 — Scheduling schema creation + read model + generalist specialty [AA-2, AA-3a]

- [x] **T008** New Alembic migration (`data-model.md` §5, correction found
  2026-08-19): creates the `scheduling` schema itself, scoped to only what
  this feature uses — the `slot_status` enum, `units`, `specialties`,
  `professionals`, `professional_specialties`, `holidays` (+ its
  natural-key unique index), `schedule_slots`, and the
  `next_business_day()` function, ported from `db/init/001_schema.sql` —
  plus the original 3 specialties/9 professionals/holidays seed data,
  ported from `002_seed_and_schedule.sql`. Deliberately excludes
  `slot_offers`, `available_offers`, `ensure_demo_availability()`,
  `appointments`, `appointment_events`, and every `identity.*`/
  `billing.*`/`governance.*` object (D-024, still dormant). Uses `CREATE
  ... IF NOT EXISTS`/bare `ON CONFLICT DO NOTHING` throughout. Forward-only,
  `downgrade()` raises. Evidence: `app/alembic/versions/20260819_0001_v4_scheduling_schema.py`;
  `alembic upgrade head` applied cleanly against the local Docker Compose
  database (which had zero pre-existing `scheduling` objects, matching
  production's actual starting state).
- [x] **T009** New Alembic migration (`data-model.md` §6), chained after
  T008: seed the `oncologia-geral` generalist specialty, its 3
  professionals, and their `professional_specialties` rows, exact values
  as specified. Data-only, forward-only, `downgrade()` raises (matching
  this codebase's convention). Evidence:
  `app/alembic/versions/20260819_0002_v4_generalist_specialty.py`, applied
  cleanly immediately after T008 in the same `alembic upgrade head` run.
- [x] **T010** `app/customer_care/scheduling/__init__.py`,
  `scheduling/models.py` — `Specialty`, `Professional`,
  `ProfessionalSpecialty`, `Unit`, `ScheduleSlot` ORM classes
  (`data-model.md` §1). No schema migration for these — only T008/T009's.
- [x] **T011 [P]** `app/tests/test_appointment_availability_models.py` —
  5 real-database tests: all 4 specialties round-trip (original 3 +
  `oncologia-geral`); all 12 professionals round-trip and join through
  `professional_specialties`; the generalist specialty is confirmed
  cheaper (R$600 < R$980) and shorter (45min < 60min) than every
  diagnosis-specific specialty; the seeded unit round-trips
  (`timezone == "America/Sao_Paulo"`); `schedule_slots` FK joins resolve.
  All 5 pass against the real local database.

**Gate:** backend `ruff`/`mypy`/`pytest` — all pass (`ruff check`: "All
checks passed!"; `mypy customer_care`: "Success: no issues found in 42
source files"; full suite: "60 passed" including the 5 new T011 tests, 0
regressions). Both migrations applied cleanly on top of a database with no
prior `scheduling` schema, matching production's actual starting state,
not assumed to already have it.

## Phase 2 — Deterministic parameter extraction [AA-3, AA-3a]

- [x] **T020** `scheduling/availability.py`: `GENERALIST_SLUG`,
  `SPECIALTY_KEYWORDS`, `DATE_KEYWORDS`, `PERIOD_KEYWORDS`,
  `extract_parameters(query_text) -> ExtractedParameters` (`plan.md` §5).
  Pure function, no database, no I/O. `specialty_slug` always resolves to
  a real slug — defaults to `GENERALIST_SLUG` when no diagnosis-specific
  keyword matches, never `None`/unfiltered. `target_date`/`period_hours`
  resolution and `ExtractedParameters`'s exact shape (left as `...` in
  `plan.md`'s pseudocode) were designed at implementation time: weekday
  keywords (`sábado`/`domingo`) resolve to the first future occurrence of
  that weekday, never today itself, via a small `_next_weekday()` helper;
  `reference_date` is an optional keyword parameter (defaulting to real
  "now" in `America/Sao_Paulo`) so the function stays pure/directly
  testable, matching `anonymous_access/rate_limit.py`'s existing `_now()`
  injectability convention.
- [x] **T021 [P]** `test_appointment_availability_keywords.py` — 12 tests:
  every diagnosis-specific keyword; explicit generalist keywords; **a
  query with no known specialty keyword at all resolves to
  `GENERALIST_SLUG`**; mixed case; realistic full customer sentences per
  specialty; date-keyword resolution (`amanhã`/`semana que vem`/weekday
  names, including the "today is the weekday itself" edge case resolving
  to next week, not today); period-keyword resolution; the no-match cases
  for both leave the field `None`. All pass with no database.

**Gate:** T021 passes (12/12); no database required for this phase's
tests — confirmed by running the full backend suite (`ruff`/`mypy`/
`pytest`, 72 passed, 0 regressions) with `DATABASE_URL` pointed at the
same already-migrated local database Phase 1 used.

## Phase 3 — Query resolver, purely read-only [AA-1, AA-4, AA-5, AA-8]

- [x] **T030** `scheduling/availability.py`:
  `resolve_appointment_availability(session, query_text) -> DynamicResolution`
  (`plan.md` §4) — a single `SELECT` against `schedule_slots` (joined to
  `Specialty`/`Professional`/`ProfessionalSpecialty`/`Unit`), always
  filtered by `extract_parameters()`'s (T020) resolved `specialty_slug`
  (never unfiltered), further narrowed by `target_date`/`period_hours` when
  present, rendering the deterministic 2-line-per-slot template
  (`plan.md` §6: specialty/professional/unit line, then
  weekday/date/time/price line, joined blank-line-separated, up to 4
  slots), raising `DynamicResolutionError` (reusing
  `knowledge/dynamic_binding.py`'s existing exception type) on zero
  matches. **Contains no `INSERT`/`UPDATE`/`DELETE` statement and never
  imports `scheduling/seeding.py`** — this is the core invariant the
  human's second clarification round introduced. Implementation-time
  finding: `ScheduleSlot.status` had to be mapped as a real
  `sqlalchemy.dialects.postgresql.ENUM("available", "held", "booked",
  "blocked", name="slot_status", schema="scheduling", create_type=False)`
  (`scheduling/models.py`), not plain `Text` as `plan.md` §3's simplified
  pseudocode showed — Postgres rejects an untyped `VARCHAR` comparison
  against a real enum column (`operator does not exist: slot_status =
  character varying`), caught by T031 immediately.
- [x] **T031 [P]** `test_appointment_availability_resolver.py` — 9 real-
  database integration tests: specialty filter correctness (mastologia
  keyword returns only mastologia slots); **a query with no specialty
  keyword returns only the generalist's slots, never a mix of the other
  3**; period (manhã/tarde) filter correctness (2 tests); zero-match
  raises with a diagnostic (never customer-facing) cause; rendered text
  contains no raw table/column name and correctly marks every price
  "(simulação)"; **a structural test asserts the `scheduling.availability`
  module source contains no `insert(`/`update(`/`delete(`/`pg_insert(`
  construct** (acceptance outcome 4), and a second structural test that no
  `import`/`from` line in the module references `seeding`. All 9 pass
  against a dedicated collision-free far-future fixture (random day 300-500
  days out, cleaned up unconditionally in fixture teardown) so this test
  file never collides with Phase 4's real D+1/D+7 seed action.

**Gate:** backend `ruff`/`mypy`/`pytest` all pass (81 passed total, 0
regressions). T031 passes (9/9) against the real local database; the
structural no-write test passes; rendered output spot-checked to contain
no internal implementation detail (`schedule_slots`/`specialty_id`/
`professional_id`/`SELECT`/`scheduling.` all absent from rendered text).

## Phase 4 — Seed action: the AA-9 write path [AA-9]

**Correction (2026-08-19, after Phase 5, human decision: "faça este botão
ir para a oncologia geral"):** T040-T043's evidence below predates this
correction. `count_available_on()`/`active_professional_specialty_pairs()`/
`create_slots_on()` all gained a `specialty_id` parameter and are now
scoped to the generalist specialty specifically (previously flat across
all 4 specialties, which meant the button always seeded
`mastologia-oncologica` only — `analysis.md` §14 has the full revision
review). Re-verified after the fix: `ruff`/`mypy`/`pytest` all still pass
(92 passed); live HTTP re-check shows all 4 slots now land on
`oncologia-geral`, and a real no-keyword customer query resolves against
them end-to-end. `test_appointment_seeding.py`'s deactivated-professional
test was repointed from a mastologia professional to a generalist one
(the only kind the seed action considers now).

- [x] **T040** `scheduling/seeding.py`: `ensure_seed_availability(session)
  -> SeedResult`, `count_available_on()`, `create_slots_on()` (`plan.md`
  §4b) — computes `d1`/`d7` via `scheduling.next_business_day()`, counts
  available slots on each, creates only what's missing (bounded to
  `1×D+1`/`3×D+7`) within 08:00-18:00, only for `active=true` professionals
  (`analysis.md` finding 1, re-applied here since this is now where that
  logic lives). Implementation-time addition beyond `plan.md`'s pseudocode:
  a transaction-scoped `pg_advisory_xact_lock` at the start of
  `ensure_seed_availability()` — without it, two genuinely concurrent
  calls could each independently compute a stale "missing" count and both
  successfully insert (into *different* candidate slots — `ON CONFLICT DO
  NOTHING` alone only prevents inserting the *same* slot twice, it does
  not prevent two different concurrent inserts from together exceeding the
  target), which would have silently broken `data-model.md` §4's claimed
  concurrency guarantee. Added proactively (reasoning through the race,
  not from an observed failure) before writing T041's concurrency test;
  that test now passes with the lock in place and is the mechanism that
  would catch a regression if the lock were ever removed. Uses an
  existing Postgres primitive, not new infrastructure (Article VIII).
  `count_available_on()` also uses an explicit São Paulo day-boundary
  comparison rather than Postgres `date()`, which depends on the session's
  `TimeZone` setting — avoids a latent off-by-one-day risk near midnight.
- [x] **T041 [P]** `test_appointment_seeding.py` — 8 real-database
  integration tests: from zero, creates exactly 1×D+1/3×D+7 within
  08:00-18:00; a second immediate call creates zero more and reports
  `already_sufficient=True`; a partial state creates exactly what's
  missing; a deactivated professional never receives a generated slot
  (verified by ID, not just by count); `next_business_day()` correctly
  skips a Sunday and a seeded national holiday, and confirms Saturday
  stays a business day; **two genuinely concurrent calls (real threads,
  synchronized with a `threading.Barrier`) never together exceed the
  target** (`data-model.md` §4) — the test that verifies T040's advisory
  lock actually delivers the guarantee `data-model.md` §4 claims, not just
  a restatement of the sequential case. All 8 pass.
- [x] **T042** `scheduling/router.py`: `POST
  /operator/scheduling/ensure-availability` (`CurrentOperator`-gated, not
  conversation-scoped) calling T040, emitting the new
  `scheduling.availability_seeded` audit event, returning the exact
  Portuguese message the human specified ("Já tem 4 vagas disponíveis." /
  a created-count message). Registered in `bootstrap.py`.
- [x] **T043 [P]** `EVENT_CATALOG.md` gained one new row for
  `scheduling.availability_seeded`. `contracts/openapi.yaml` already
  documented the one new route exactly matching the real response shape
  (`created_d1`/`created_d7`/`already_sufficient`/`message`) — written
  correctly during the spec phase, no change needed.

**Gate:** backend `ruff`/`mypy`/`pytest` all pass (89 passed, 0
regressions). T041 passes (8/8). Live HTTP verification against a rebuilt
backend container (`docker compose build backend && docker compose up -d
backend`): an anonymous credential gets `401`; a real operator's first
call returns `{"created_d1": 1, "created_d7": 3, "already_sufficient":
false, "message": "Criadas 4 vaga(s): 1 em D+1, 3 em D+7."}`; the
immediate second call returns `{"created_d1": 0, "created_d7": 0,
"already_sufficient": true, "message": "Já tem 4 vagas disponíveis."}` —
both `scheduling.availability_seeded` audit events confirmed in
`customer_service.audit_events` with the exact payload shape. Test
data/operator cleaned up afterward.

## Phase 5 — Wire the query path into `ai/router.py` [AA-1]

- [x] **T050** `dynamic_pattern_result()` gains the `NAMED_RESOLVERS`
  dispatch and a `query_text` parameter (`plan.md` §2); both call sites
  (`generate_draft()`, `select_evidence()`) updated to pass the right text
  (the already-built `query` string, and the originating
  `RetrievalRun.query_text` fetched via `hit.retrieval_run_id`,
  respectively). Return shape extended from a 3-tuple to a 4-tuple
  (`result, dynamic_used, dynamic_cause, audit_extra`) so T051's
  `specialty_slug`/`slot_count` can flow through without adding a second
  return path; `DynamicResolution` (`knowledge/dynamic_binding.py`) gained
  the two new optional fields, defaulting to `None` for the generic
  `qa_dynamic_bindings` path.
- [x] **T051** `ai.dynamic_pattern_resolved`'s audit payload gains optional
  `specialty_slug`/`slot_count` when the resolver used is
  `appointment_availability` (`plan.md` §7), via `resolve_appointment_availability()`
  populating `DynamicResolution`'s new fields and both `record_event` call
  sites spreading `dynamic_extra` into the payload. Live-verified: a real
  resolution's audit row shows
  `{"slot_count": 1, "specialty_slug": "mastologia-oncologica",
  "ai_generation_id": "..."}`.
- [x] **T052 [P]** `test_dynamic_pattern_dispatch.py` — 2 real-database
  regression tests: a QA entry with `dynamic_resolver='price_lookup'`
  (unimplemented, no `NAMED_RESOLVERS` entry, no `qa_dynamic_bindings`
  row) still abstains through `dynamic_pattern_result()` exactly as
  before (acceptance outcome 8); a QA entry using the pre-existing generic
  `qa_dynamic_bindings` mechanism (`dynamic_resolver=NULL`) still resolves
  exactly as before, with `audit_extra=None` (proving the dispatch change
  is additive, not a replacement). `smoke_v2_dynamic_pattern.py` re-run
  directly (`python -m tests.smoke_v2_dynamic_pattern`) and passes
  unmodified.
- **Real bug found and fixed during live verification** (not present in
  any unit test, since T021's fixture sentences never combined "amanhã"
  with a bare morning/afternoon check): `PERIOD_KEYWORDS`'s "manhã" is a
  literal substring of `DATE_KEYWORDS`'s "amanhã" ("a-manhã"), so *any*
  message mentioning "amanhã" was also false-positive-matching the
  morning-only period filter, silently narrowing (and in one live test,
  zeroing) real results. A live `POST /operator/knowledge/evidence/{id}/select`
  call against QA-012 ("Existe consulta disponível amanhã?") — one of the
  actual pre-seeded `agenda` corpus entries this feature targets, not a
  synthetic fixture — abstained instead of answering, which is what
  surfaced it. Fixed in `scheduling/availability.py` with a
  `_contains_keyword()` helper using `\b{keyword}\b` word-boundary regex
  matching for all three keyword dictionaries, not just the one collision
  caught; `plan.md` §5 corrected from "substring search" to
  "word-boundary-aware substring search"; `test_appointment_availability_keywords.py`
  gained a dedicated regression test for this exact case.

**Gate:** backend `ruff`/`mypy`/`pytest` all pass (92 passed, 0
regressions, after the word-boundary fix). T052 passes (2/2). Live HTTP
verification against a rebuilt backend container, using the real seeded
corpus (not a synthetic fixture): manual search for "Tem vaga de
mastologia amanhã?" retrieves QA-012 via real embeddings; selecting it
after Phase 4's seed endpoint had run returns `status=ANSWER`,
`model=not-applicable`, `dynamic_pattern_used=true`,
`draft_text="Mastologia oncológica — Dra. Helena Martins (simulação),
Unidade Central (simulação)\nquinta-feira 20/08 às 08:00
(America/São_Paulo) — R$ 980,00 (simulação)"` — real synthetic slot data,
zero LLM calls. (Note: the seed action's flat, not-specialty-scoped count
— `spec.md` AA-9 item 2, an explicit human decision — means which
specialty actually gets seeded data depends on professional-UUID
ordering; this run happened to seed `mastologia-oncologica`, which is why
verification used that specialty rather than the generalist default.)
Test data cleaned up afterward.

## Phase 6 — Operator-workspace button [AA-9 UI]

- [x] **T060** `frontend/src/main.tsx`: `ensureAvailability()` handler +
  one new button + `role="status"`/`aria-live="polite"` status line
  (`availabilityMessage` state), added inside `<aside aria-label="Fila de
  conversas">` below the queue list — a sibling of the
  `{selected ? ... : ...}` section, not inside it, so it renders and works
  with no conversation selected (`plan.md` §4b).
- [x] **T061 [P]** `frontend/src/main.test.tsx` gained one new test: click
  calls `POST /operator/scheduling/ensure-availability` and renders the
  returned created-count message, with no conversation selected (empty
  queue, mirroring the existing "empty queue state" test's setup); a
  second click against a mocked no-op response shows the exact idempotent
  "Já tem 4 vagas disponíveis." message. 17/17 tests pass (16 pre-existing
  + 1 new).

**Gate:** frontend `eslint`/`tsc --noEmit`/`vitest`/`vite build` all pass.
Manual verification against the rebuilt containers (`docker compose build
frontend && docker compose up -d frontend`): the built JS bundle contains
the button label and `role="status"` element; the `/api/**` nginx proxy
correctly forwards `POST /operator/scheduling/ensure-availability` to the
backend (confirmed via a `401` for an unauthenticated request, matching
the backend's own gating) — combined with T061's real interaction test
(click → fetch → rendered message) and Phase 4/5's own live-HTTP proof of
the same endpoint's exact behavior, this constitutes the button's
end-to-end verification; no Playwright run available in this session.

## Phase 7 — Q&A content cleanup [spec.md §5 item 3]

- [x] **T070** Evaluated all 27 seeded `agenda` entries (QA-011..QA-024
  `appointment_availability`, QA-025..QA-037 unimplemented resolvers)
  against the real resolver built in Phases 1-5, using their full stored
  text, not just titles. Final disposition, via `documents/qa/qa-catalog.jsonl`
  (the real source of truth `knowledge/ingest.py` reads —
  `dynamic_resolver`/`dynamic_data_required` are not settable through the
  operator CRUD form at all, confirmed by reading `CreateQAIn`/`UpdateQAIn`;
  those fields only ever came from corpus ingest) plus a one-off script
  (`scripts/cleanup_agenda_qa_004.py`) for `is_active` deactivation (which
  *is* CRUD-only, matching the original plan):
  - **Stays dynamic** (`appointment_availability`, real "show me slots"
    queries): QA-011 (edited — removed a name/contact/CPF-at-reservation
    claim this feature doesn't implement), QA-012, QA-013 (unchanged),
    QA-018 (edited — removed an inaccurate Saturday-morning-only claim,
    kept as the period-filter demo), plus the 2 new generalist entries
    (`plan.md` §8, authored verbatim, seeded as QA-087/QA-088 — confirmed
    neither's wording matches any of the 3 diagnosis-specific
    `SPECIALTY_KEYWORDS` terms, so both correctly resolve to
    `GENERALIST_SLUG`).
  - **Converted to static** (policy/meta questions the resolver's
    slot-list rendering doesn't actually answer, and for QA-019/QA-020,
    would mostly abstain in practice since Saturday is rarely the seeded
    d1/d7 date and Sunday never is): QA-014 (accurate as-is), QA-015 and
    QA-019 (both edited — found and fixed a real content-accuracy bug: the
    stored text claimed "Sábados... 8h às 12h," but this feature's actual
    seed action creates slots 08:00-18:00 uniformly on any business day,
    Saturday included — carried over unexamined from the old, unused
    `ensure_demo_availability()` SQL function), QA-020 (accurate as-is).
  - **Soft-deactivated** (`is_active = false`, describes booking/hold/
    identity/payment/professional-choice behavior this feature does not
    implement): QA-016, QA-021, QA-022, QA-023, QA-024 — the human's
    original 5 (`spec.md` §5 item 3) — plus **QA-017**, added during this
    re-evaluation: its stored text claims "A busca pode filtrar
    profissional... apresenta outros especialistas," but
    `extract_parameters()` has no professional-name keyword at all.
  - **Implementation-time bug found and fixed**: `knowledge/ingest.py`'s
    re-ingest change-detection keyed only on `content_hash` (question+
    answer text) — a source edit changing only
    `dynamic_data_required`/`dynamic_resolver`/`category`/`metadata`,
    with question/answer text left untouched, was silently never applied
    on re-ingest. Caught converting QA-020 (accurate text, field-only
    change) to static. Fixed to also diff those fields.
  - **Operational incident found and fixed, unrelated to this feature's
    own correctness but discovered while verifying it**: an earlier
    `smoke_ingestion_changed.py` run this session used
    `DeterministicTestEmbeddingProvider` against this *same shared* local
    Postgres (that script only isolates the corpus directory, not the
    database) — its `needs_reembedding()` check then detected a
    provider mismatch on every entry and silently overwrote every real
    OpenAI embedding in the corpus with fake sha256-based ones, including
    QA-012's. This surfaced as QA-012 vanishing from live search results
    entirely. Fixed by re-running the real `python -m
    customer_care.knowledge.ingest --corpus-root ../documents` (confirmed
    `QA-012.embedding_provider == "openai"` afterward). Flagging for
    future sessions: **do not run `smoke_ingestion_changed.py` against a
    shared, non-disposable local database** — it has no test-database
    isolation of its own.
  - Also found and deactivated 29 unrelated stale `content.qa_entries`
    rows (`question LIKE '%fixture e2e%'`) — leftover Playwright E2E test
    fixtures from an unrelated prior test run, competing in retrieval
    ranking; deactivated rather than hard-deleted (FK-referenced from
    `retrieval_hits`).
  - `tests/smoke_ingestion_changed.py`'s hardcoded fresh-corpus count
    updated `656` → `658` (the 2 new QA-087/088 entries) — verified
    against a truly fresh ingest inside the rebuilt container.
- [x] **T071 [P]** `smoke_v4_appointment_availability.py` — real
  end-to-end HTTP smoke against the rebuilt containers: calls Phase 4's
  seed endpoint to guarantee real data, then uses manual search + explicit
  evidence selection (V2-3 "Buscar evidências," not the message-context
  draft flow) so the outcome depends on this feature's own resolver, not
  on this shared corpus's current retrieval ranking — `status=ANSWER`,
  `model="not-applicable"`, `dynamic_pattern_used=true`, real synthetic
  slot data in `draft_text`, no raw table/column names, `duration_ms <
  1000` as the zero-LLM-call signal (matches `acceptance.md` §A.2's
  documented alternative to a provider spy); a second case (QA-025,
  `price_lookup`) confirms unimplemented resolvers still abstain exactly
  as before (`ABSTAIN`/`DYNAMIC_DATA_UNAVAILABLE`/empty `draft_text`).
  Closes both conversations it creates (a real `CAPACITY_EXCEEDED` was hit
  once during development from accumulated unclosed conversations across
  this session's many live-verification rounds). Passes.

**Gate:** backend `ruff`/`mypy`/`pytest` all pass (92 passed, 0
regressions). T071 passes. Regression spot-check against the rebuilt
container: `smoke_v2_dynamic_pattern.py`, `smoke_v3_knowledge_guided.py`,
and `smoke_v3_satisfaction.py` all pass unmodified. `smoke_core.py`/
`smoke_n2.py`/`smoke_v3_taxonomy_hcr.py` need a pre-seeded "exactly 4
active conversations" fixture this session doesn't have set up (not
something this phase's own work invalidated — a session/environment
precondition, not a code regression); running the complete historical
`smoke_*` suite with its full fixture setup is explicitly Phase 10's job
per this file's own Handoff note, to avoid duplicating that
execution-heavy pass here.

## Phase 8 — Booking-script foundation [AA-10]

This phase and Phase 9 implement the one exception to Constitution Article
III (Amendment 1.1.0, `DECISIONS.md` D-031) — extra scrutiny applies to
every task here, matching `plan.md` §8b/§13's own emphasis.

- [x] **T090** New Alembic migration
  (`app/alembic/versions/20260819_0003_v4_booking_script_columns.py`,
  `data-model.md` §8): `conversations.booking_script_step` and
  `messages.autonomous_source`, both nullable `text` with a `CHECK`
  constraint enumerating their only legal values at the database level.
  Additive, forward-only, `downgrade()` raises. ORM mappings added to
  `infrastructure/models.py`'s existing `Conversation`/`Message` classes
  (no new model file — these are pre-existing V1-baseline tables gaining
  columns, unlike Phase 1's brand-new `scheduling` schema). Applied
  cleanly on top of `20260819_0002`.
- [x] **T091** `app/customer_care/booking_script/__init__.py`,
  `parsing.py` — `extract_cpf()` (Pydantic-validated, digit-count-only,
  never the real CPF algorithm — verified against a CPF that fails the
  real check-digit algorithm but has 11 digits, still passes), 
  `extract_payment_confirmation()` (word-boundary sim/não regex),
  `detect_booking_intent()` (`plan.md` §8b). Pure functions, no database,
  no I/O. Also made `scheduling/availability.py`'s price-formatting
  helper public (`format_price_brl`, was `_format_price_brl`) for
  Phase 9's `service.py` to reuse without duplicating it.
- [x] **T092 [P]** `test_booking_script_parsing.py` — 16 tests: the
  human's own two CPF examples and two payment examples verbatim
  (independently confirmed via direct interpreter run before writing the
  formal test, matching the exact expected outputs in `spec.md`'s script),
  plus 10/11/12-digit inputs, the real-CPF-algorithm-would-reject-this
  case, sim/não case variants, a message matching neither or both
  (ambiguous → `None`), 10 consecutive non-affirmative replies all
  correctly staying unconfirmed (no hidden retry cap), a word-boundary
  false-positive check ("simples"/similar), and booking-intent
  positive/negative examples. All pass with no database.

**Gate:** backend `ruff`/`mypy`/`pytest` all pass (108 passed, 0
regressions — 16 new). Migration applies cleanly. T092 passes (16/16)
with no database required.

## Phase 9 — Booking-script service, wiring, and containment [AA-10]

- [x] **T093** `booking_script/service.py`: `send_scripted_message()` (the
  one function in the codebase allowed to create a customer-visible
  `Message` with no operator-auth dependency, `plan.md` §8b),
  `advance_booking_script()` (the state machine), `has_recent_resolved_availability()`,
  `lookup_recent_specialty_price()`. Every send emits
  `booking_script.autonomous_message_sent` (`data-model.md` §9) — no raw
  CPF/payment-reply text in the payload, ever.
  `has_recent_resolved_availability()`/`lookup_recent_specialty_price()`
  both key off the `ai.dynamic_pattern_resolved` audit event's own
  `specialty_slug` payload field (Phase 5) rather than inventing a new
  place to store "which specialty was this about" — reuses an existing
  durable fact instead of adding state.
  - **Correction found during implementation:** a pre-existing V1-baseline
    `messages_check` CHECK constraint —
    `(author_type='CUSTOMER' AND operator_id IS NULL) OR
    (author_type='OPERATOR' AND operator_id IS NOT NULL)` — rejected
    `send_scripted_message()`'s insert outright, since that call has no
    operator in context by design. New migration `20260819_0004` widens it
    with exactly one more disjunct, gated on `autonomous_source =
    'booking_script'` — itself a structural enforcement of the amendment's
    narrow scope, not just a permissive loosening (`data-model.md` §8).
  - **Second correction found during implementation:** Postgres's `now()`
    is constant for the whole transaction, so the 2-3 messages one
    `advance_booking_script()` call sends would get an *identical*
    `created_at` — and the real message-list ordering
    (`conversations/projections.py`, `ORDER BY created_at, id`) would then
    tie-break on a random UUID, risking the script displaying out of
    order to the customer. `send_scripted_message()` now sets `created_at`
    explicitly from Python's wall clock. Found via a flaky full-suite test
    run, not by inspection — see T095.
- [x] **T094** `anonymous_access/router.py`'s `send_customer_message()`
  gains the one call to `advance_booking_script()`, in the same
  transaction, before `session.commit()` (`plan.md` §8b "Trigger"). Not
  wired into the typing-heartbeat endpoint or any GET/poll path — confirmed
  structurally by T096.
- [x] **T095 [P]** `test_booking_script_flow.py` — 7 real-database
  integration tests: the full happy-path script verbatim (including the
  exact rendered price line); the invalid-CPF-then-valid branch; the
  não-then-sim branch (question repeats verbatim); no prior resolved
  availability → script never starts; a second booking-intent message
  after a completed flow starts a fresh one; every sent message carries
  `autonomous_source = "booking_script"` and its audit event
  (`actor_type="SYSTEM"`); the raw CPF and payment-reply text are absent
  from every operator message body and every audit payload afterward (the
  one exception, by design: the *formatted* CPF legitimately appears in
  the "CPF ... confirmado" customer-visible message itself — that is the
  script's specified output, not a persistence violation). This test
  file's first run (before the `created_at` fix above) is what surfaced
  the timestamp-collision bug, failing only under full-suite timing, not
  in isolation.
- [x] **T096 [P]** `test_booking_script_containment.py` — 4 AST-based
  structural tests (source introspection, not behavioral): every
  `Message(author_type="OPERATOR", ...)` construction site outside
  `booking_script/` requires a `CurrentOperator`-annotated parameter in
  its enclosing function (found exactly one:
  `operator_workspace/router.py`'s `send_operator_message`);
  `booking_script/` itself contains exactly one such site
  (`send_scripted_message`); `send_scripted_message` is imported nowhere
  outside `booking_script/`; `advance_booking_script` is called from
  exactly one place, `send_customer_message`.
- [x] **T097 [P]** `docs/architecture/EVENT_CATALOG.md` gained the new
  `booking_script.autonomous_message_sent` row, flagged ⚠ as the one event
  type marking a non-operator-gated send. `smoke_v4_booking_script.py` —
  real end-to-end HTTP smoke: real availability resolution (via manual
  search + `select_evidence`, immune to the shared corpus's retrieval
  ranking — Phase 7's lesson applied here too), a real booking-intent
  customer message, the script's exact messages appear with zero operator
  action through both retry branches, the exact final message confirmed,
  and `identity.patients`/`billing.payments`/`scheduling.appointments`/
  `scheduling.appointment_events` confirmed empty-or-nonexistent
  afterward (all four are in fact nonexistent tables, per T008's
  correction — the strongest possible proof).
- [x] **T098 [P, optional]** Implemented. Found the backend gap this
  needed first: `conversations/projections.py`'s `customer_projection()`
  (shared by both `/public/*` and `/operator/*` conversation reads) never
  included `autonomous_source` in its message dict at all — added one
  line. The customer-facing `/public/conversations/{id}` route's
  `response_model=ConversationOut` Pydantic schema silently drops it
  (matches the intent — this is an operator-only transparency cue, not
  something that needed a customer-facing schema change); the operator
  detail route returns a raw dict, so it passes through untouched.
  `frontend/src/main.tsx`: `Message.autonomous_source` field, one
  conditional `<span className="badge">automático</span>` next to the
  message-author label, with a `title` tooltip explaining what it means.

**Gate:** backend `ruff`/`mypy`/`pytest` all pass (119 passed, 0
regressions). Frontend `eslint`/`tsc --noEmit`/`vitest` (17/17)/`vite
build` all pass. T095 (7/7)/T096 (4/4) pass. Live HTTP verification
against rebuilt backend+frontend containers reproduces the human's exact
script verbatim, including both retry branches, through real HTTP calls
(`smoke_v4_booking_script.py`) — confirmed via direct DB query: 10
`booking_script.autonomous_message_sent` audit events, all
`actor_type="SYSTEM"`, no raw CPF/payment text in any payload. The
containment test (T096) passes, proving the exception has not spread
beyond `booking_script/`. Test conversations closed afterward.

## Phase 10 — Acceptance automation and DONE

**Handoff note (human decision, 2026-08-18):** Phases 1-9 (the actual
implementation) are done in this same session/tool. This phase — the
long-running, mostly-mechanical verification pass (full `smoke_*` suite,
full Playwright suite, live Docker rebuilds, real-provider latency) — is
intended to be picked up by a different coding agent (Codex) in a fresh
session, to save tokens on work that is execution-heavy rather than
design-heavy. Whoever/whatever executes this phase should:

1. Read `AGENTS.md`, `CLAUDE.md`, `.specify/memory/constitution.md`
   (including Amendment 1.1.0), and this package's full artifact set
   (`spec.md`, `plan.md`, `data-model.md`, `acceptance.md`, `analysis.md`,
   `checklists/*`) before starting — do not rely on any prior conversation
   context, there is none available.
2. Confirm Phases 1-9's own gates all show `[x]` with real evidence in
   this file before starting T080-T082 — if any phase's evidence looks
   incomplete or the described tests don't actually exist/pass, stop and
   flag it rather than writing acceptance.md around a gap.
3. Hold AA-10 to the same standard as every other outcome, not a lighter
   one, even though it's the fastest/most tempting to rubber-stamp: T082
   must independently re-run the containment test
   (`test_booking_script_containment.py`) and confirm its own read of the
   result, not just trust that it was green when Phase 9 finished.
4. Follow this project's established conventions throughout this
   package's own history: real Postgres/Docker, no mocked integration
   tests, commit with detailed evidence per task (matching every prior
   phase's commit messages), update `tasks.md` checkboxes with real
   evidence (not just "done"), and do not push without being asked.

- [ ] **T080** Write `acceptance.md` covering `spec.md` §4's 15 acceptance
  outcomes as executable scenarios, following V1/V2/V3's Execution-record
  format.
- [ ] **T081** `checklists/{requirements,security,traceability}.md`
  finalized against the implemented state.
- [ ] **T082** `analysis.md` — final post-implementation cross-artifact
  convergence review (spec/plan/data-model/tasks/acceptance), following
  V2 §6 / V3 §6's method: diff against the real implementation, not just
  against each other. **Explicitly re-verify AA-10's containment** — the
  autonomous-send exception must be provably scoped to exactly one
  function, reachable from exactly one trigger. Update
  `PROJECT_STATE.md`/`ROADMAP.md`/`DECISIONS.md` to record this feature's
  closure (and D-031's move from "specification pending" to
  "implemented").

**Gate:** backend `ruff`/`mypy`/`pytest`; frontend
`eslint`/`tsc --noEmit`/`vitest`/`vite build` (this feature now has a real
frontend surface, unlike the first plan draft — Phase 6's button, and
optionally Phase 9's badge); the full `smoke_*` suite (pre-existing + this
feature's new scripts) all pass; `acceptance.md`'s Execution record covers
all 15 `spec.md` §4 outcomes.

## Dependency summary

```text
Phase 0 (SDD gates)
  -> Phase 1 (schema-creation migration + generalist-specialty migration
       + scheduling read model)
  -> Phase 2 (parameter extraction) [P, independent of Phase 1 — GENERALIST_SLUG
       is a Python constant, not a DB lookup; only Phase 3's query and Phase 7's
       Q&A seeding actually need T009's migration to have run]
  -> Phase 3 (query resolver, read-only, needs Phase 1 + Phase 2)
  -> Phase 4 (seed action, one of two write paths, needs Phase 1)
       [P, independent of Phase 3 — different files, disjoint concerns]
  -> Phase 5 (wire query path into ai/router.py, needs Phase 3)
  -> Phase 6 (operator button, needs Phase 4's endpoint to exist)
  -> Phase 7 (Q&A content cleanup, needs Phase 5 + Phase 6 working end-to-end
       so the demo has real data to answer from)
  -> Phase 8 (booking-script foundation: migration + parsing, needs Phase 1
       for scheduling models the price lookup will need in Phase 9)
  -> Phase 9 (booking-script service + wiring, needs Phase 8 + Phase 5
       working end-to-end — advance_booking_script's
       has_recent_resolved_availability() reads real AA-1..AA-9 generations)
  -> Phase 10 (acceptance automation + DONE)
```
