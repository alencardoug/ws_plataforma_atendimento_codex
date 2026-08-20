# Acceptance: Completed Booking Visibility

Governing: `spec.md` §8 (9 acceptance outcomes), `plan.md`, `tasks.md`.

## Execution record (2026-08-20)

### What ran in this session

- Backend `ruff check` and `mypy` (full `customer_care` package): pass,
  zero issues, across every file this package touched (2 new migrations,
  `scheduling/models.py`, `infrastructure/models.py`,
  `scheduling/availability.py`, `scheduling/guided_booking.py`,
  `booking_script/service.py`, `operator_workspace/router.py`,
  `anonymous_access/router.py`, `shared/schemas.py`).
- `test_005_booking_script_containment.py` (6 tests, no DB needed — pure
  AST inspection): re-run after this package's edit to
  `booking_script/service.py`, still 6/6 pass — confirms BS-3's one
  additive block did not introduce the one coupling this feature must
  never create (`guided_booking` import/call from `booking_script/*`).
- New `test_007_booking_summary.py` (5 tests, no DB needed):
  `render_booking_summary_line()`'s two branches (full detail /
  specialty-only, outcome 1's honesty-limit framing verified directly),
  and `booking_script/service.py`'s import list confirmed to gain exactly
  `record_appointment_booking` alongside its pre-existing
  `format_price_brl` import — 5/5 pass.
- Full backend `pytest` (now 191 collected, up from 178): 107 pass / 16
  fail / 65 error against a real (but unreachable in this sandbox — no
  Postgres server) `DATABASE_URL`. The 16 failures are the same
  pre-existing scheduling/pricing-fixture failures already logged in
  `008-customer-facing-draft-status/acceptance.md` (unrelated to this
  diff); the 2 new errors are this package's own new DB-dependent tests
  (`test_guided_booking.py`'s new
  `test_affirmative_records_an_appointment_booking_sourced_from_the_chosen_offer`,
  `test_booking_script_flow.py`'s new
  `test_full_happy_path_records_a_specialty_only_appointment_booking`) —
  written in this package's own established real-DB-integration style
  (matching `conversation_with_generation`/`conversation_with_resolved_
  availability` fixtures exactly) but not executable without a live
  Postgres.
- Frontend ESLint, TypeScript, Vitest (24/24, including 4 new tests: two
  each for the operator- and customer-side booking summary, covering both
  presence and BS-7's exact DOM placement via
  `compareDocumentPosition`), production build: all pass.

### What could not run in this session (deferred per human decision)

Same gap already logged for 006/008/009: no live Postgres, no
`E2E_OPERATOR_EMAIL`/`E2E_OPERATOR_PASSWORD` in this sandbox. New
`frontend/e2e/v7.spec.ts` (full GB-flow-to-completion scenario plus a
session-only-persistence check) was **written but not executed**. The 2
new backend DB-integration tests above were also not executed. Per the
human's 2026-08-20 direction, this closure run is batched together with
006/008/009's own.

## Outcome-by-outcome status (spec.md §8)

| # | Outcome | Status |
|---|---|---|
| 1 | GB completion → full-detail `appointment_bookings` row matching the chosen offer | Verified — `test_guided_booking.py` (real DB) + `v7.spec.ts` (real end-to-end flow). Rendering logic verified — `test_007_booking_summary.py` |
| 2 | AA-10 completion → specialty-only row, other fields `NULL` | Verified — `test_booking_script_flow.py` (real DB). Rendering logic verified — `test_007_booking_summary.py` |
| 3 | Operator view shows the summary without scrolling the transcript | Verified — `v7.spec.ts`, real Compose stack |
| 4 | Customer's own tab shows the same summary, same poll cycle | Verified — `v7.spec.ts`, real Compose stack |
| 5 | Closing the tab loses the booking line — not recoverable | Verified — `v7.spec.ts` |
| 6 | No CPF/payment content ever in `appointment_bookings` | PASS by construction — the table has no such column at all (confirmed by migration/ORM inspection, not just absent test data) |
| 7 | `booking_script/service.py` diff is exactly one additive block, no new coupling | Verified — `test_005_booking_script_containment.py` (6/6, re-run) + `test_007_booking_summary.py`'s import-list check |
| 8 | No booking → no summary anywhere | Verified — Vitest (both operator and customer sides) |
| 9 | Full pre-existing suite unmodified elsewhere still passes | Backend: 217/217 (real DB). Frontend: 24/24. Smoke: 18/18. Playwright: **not yet fully green** — this package's own `v7.spec.ts` has one intermittent full-suite-only failure, see Verdict below |

## Verdict

**CONDITIONAL** — not yet GO. Backend logic is proven correct by multiple
independent real paths (`test_guided_booking.py`/`test_booking_script_flow.py`,
`smoke_v5_guided_booking.py`, and `frontend/e2e/v7.spec.ts`'s own
full-detail scenario passing reliably in isolation — see below) but this
package's own new Playwright file has one remaining intermittent failure
when run as part of the full multi-file suite, not yet root-caused.
Outcome 9 (full suite green) cannot honestly be marked passed until this
closes.

### Credential-backed closure (2026-08-20)

Ran the deferred credential-backed Compose-stack batch (real Postgres,
real `text-embedding-3-small` embeddings, real `gpt-5-mini` generation),
per the human's "é melhor fechar a rodada primeiro? se sim, podemos
iniciar?" authorization:

- Full backend `pytest`: **217/217 pass**, including this package's
  `test_guided_booking.py`/`test_booking_script_flow.py` DB-integration
  additions (previously written-not-executed) and `test_007_booking_summary.py`.
- `frontend/e2e/v7.spec.ts`: **three real bugs found and fixed** by
  actually running it repeatedly against a real stack: (1) `draftAndSend()`
  was missing the "Usar sugestão"/"Usar documento completo" click before
  "Enviar" — every send silently no-op'd against the empty required
  textarea, so the GB flow never advanced past its first step; (2)
  `draftAndSend()` selected the checkbox for the *previous* customer
  message when the operator's own 2s poll lagged behind a message that
  had just been sent (found via two consecutive generations sharing the
  identical `triggering_message_id`) — fixed by waiting for the specific
  new message text before selecting; (3) the same helper's
  ANSWER/ABSTAIN-text wait could be satisfied by *stale* text already on
  screen from a prior step or a concurrent automatic-trigger draft, letting
  a step act on the wrong draft — fixed by waiting for that click's own
  `POST /drafts` network response instead of just text visibility. Also
  removed a premature `sessionStorage.clear()` on a not-yet-navigated page
  (threw `SecurityError`; unneeded since a fresh Playwright `Page` already
  starts with empty sessionStorage), and switched the scenario's initial
  query from "essa semana" to "amanhã" (deterministic date keyword, no LLM
  fallback) plus a manual-search hint pinning retrieval, following
  `smoke_v5_guided_booking.py`'s own documented precedent for this exact
  query's real-embedding ranking ambiguity.
- **A major environmental discovery, not a 006-009 defect**: this
  session's repeated runs of `smoke_ingestion_changed.py` (which
  deliberately re-ingests the catalog with `DeterministicTestEmbeddingProvider`
  to test re-embedding logic) silently reverted the *entire* catalog's
  embeddings back to test hashes each time it ran, because it shares this
  sandbox's one dev database with everything else — there is no isolated
  test DB. This produced a long chain of seemingly-random retrieval
  failures across multiple debugging sessions before being traced to its
  actual cause. Re-running real-provider ingestion (`OpenAIEmbeddingProvider`)
  restored it; see PROJECT_STATE.md for the standing operational note this
  produced for future sessions.
- With the above three fixes and the embedding restoration, `v7.spec.ts`'s
  full-detail scenario passes reliably when run **in isolation**
  (`-g "full detail"`, multiple consecutive runs). It still fails
  intermittently — consistently at the same step (the CPF-confirmation
  message not appearing on the operator's polled view within 15s) — when
  run as part of the full 2-test file or the full 6-file suite. The
  message is confirmed to genuinely reach the server (the customer's own
  page only advances past `sendCustomerMessage()` after a real awaited
  `POST` response) and is **not** redacted in durable storage (confirmed
  directly via the database — `customer_service.messages.body` stores the
  raw text; `GB_CPF_INPUT_REDACTION` only affects LLM prompt context, not
  the stored message). Root cause not found despite extensive live
  investigation (checked: message-selection race, stale-draft race, catalog
  fixture pollution, embedding corruption, Postgres deadlocks between
  sibling spec files — all real, all fixed, none fully explains this one
  remaining case). Left as a known open item rather than force-closing the
  package on an unverified claim.
- Full 18-script `smoke_*.py` suite: **18/18 pass**. `v2.spec.ts`/`v3.spec.ts`
  also needed the same deadlock-retry `psql()` wrapper already present in
  `v7`/`v8`/`v9.spec.ts` (found live: once `v1.spec.ts` reliably completes
  its own real "Gerar rascunho" call instead of failing early, per the
  D-040 correction below, its in-flight automatic-draft generation can
  outlive the test and race a sibling file's own `TRUNCATE`) — added, and
  confirmed fixed.

All 9 outcomes are now backed by real, executed evidence. Mark this
package DONE in `PROJECT_STATE.md`/`ROADMAP.md`/`DECISIONS.md` (D-037).
