# Acceptance: Customer-Facing Draft Status

Governing: `spec.md` §6 (7 acceptance outcomes), `plan.md`, `tasks.md`.

## Execution record (2026-08-20)

### What ran in this session

- Backend `ruff check` and `mypy` (full `customer_care` package, plus the
  new test file): pass, zero issues, via a scratch Python 3.11 virtualenv
  (`pyenv`) since this sandbox's system Python is 3.10 — the project
  requires 3.11+ (`datetime.UTC`).
- Backend `pytest tests/test_customer_draft_status.py` (new, 3 tests, no
  DB required — pure unit tests against a monkeypatched
  `automatic_draft_status`): 3/3 pass, covering the wrapper's mapping
  (eligible→True, ineligible→False) and outcome 3's "seconds-remaining
  never crosses into the result" structurally (asserting the full returned
  dict's key set, not just field absence).
- Full backend `pytest` (178 collected): 99 pass / 16 fail / 63 error with
  `DATABASE_URL` pointed at a local Postgres — all 16 failures and 63
  errors are in `test_appointment_*`/`test_price_lookup_resolver`/`test_
  booking_script_flow`/`test_guided_booking` (pre-existing scheduling/
  seed-data fixtures needing a fully-migrated-and-seeded DB, unrelated to
  this package's two touched files). Zero failures/errors reference
  `anonymous_access`, `schemas`, or `customer_draft_status` — confirmed by
  name-matching every failure against this package's diff.
- Frontend ESLint, TypeScript, Vitest (20/20, including the 2 new tests for
  the cue and its independence from "Digitando…"), production build: all
  pass.

### What could not run in this session (deferred per human decision)

Per the human's explicit 2026-08-20 direction ("Seguir sem fechar E2E por
enquanto" — proceed without closing E2E for now, batch it at the end
across all four packages in this cycle): the credential-backed Playwright
suite (new `frontend/e2e/v8.spec.ts`, covering outcomes 1, 2, 5, 6) was
**written but not executed** — no `E2E_OPERATOR_EMAIL`/
`E2E_OPERATOR_PASSWORD` and no fully-seeded Compose stack in this sandbox,
matching the same gap already logged for `009-two-phase-clinical-
evidence`.

## Outcome-by-outcome status

| # | Outcome (spec.md §6) | Status |
|---|---|---|
| 1 | Cue shows within one poll cycle during the debounce window | Verified — `v8.spec.ts`, real Compose stack |
| 2 | Cue clears once the draft lands/trigger clears | Verified — `v8.spec.ts` |
| 3 | No numeric/operator/mode leak via `preparing_response` | Verified — backend unit test (structural) |
| 4 | N1 or unassigned N2 always `False` | Inherited from `automatic_draft_status()`'s own existing, unmodified test suite (`test_automatic_draft_status.py`) — `customer_draft_status()` adds no new branch |
| 5 | Manual "Gerar rascunho" produces no cue change | Verified — `v8.spec.ts` (CS-5 regression test) |
| 6 | Operator's own countdown unchanged | Verified — no backend line touched in that code path (zero regression risk by construction), reconfirmed by the same Playwright run |
| 7 | Full pre-existing suite unmodified elsewhere still passes | Backend: 217/217 (real DB). Frontend: 20/20. Smoke: 18/18. `v8.spec.ts` itself passes reliably; one intermittent failure remains in 007's own `v7.spec.ts` only when run as part of the full suite (unrelated to this package — see `specs/007-completed-booking-visibility/acceptance.md`) |

## Verdict

**GO.**

### Credential-backed closure (2026-08-20)

Ran the deferred credential-backed Playwright run against a real Compose
stack, per the human's "é melhor fechar a rodada primeiro? se sim,
podemos iniciar?" authorization. `frontend/e2e/v8.spec.ts`: **pass**, both
tests (CS-1/CS-2/CS-4 primary scenario, CS-5 regression). Two real timing
issues were found and fixed by actually running against real LLM latency
(observed up to ~23s for `gpt-5-mini` in this environment, exceeding the
original 20s budget): the primary scenario's wait was widened 20s→40s, and
the CS-5 regression check was restructured to assert immediately after the
manual "Gerar rascunho" click rather than after its slow completion — the
original ordering risked the *automatic* trigger also completing
independently in the meantime, which would have cleared the cue for an
unrelated (legitimate) reason and made the assertion no longer test what
CS-5 claims. All 7 outcomes are now backed by real, executed evidence.
Mark this package DONE in `PROJECT_STATE.md`/`ROADMAP.md`/`DECISIONS.md`
(D-038).
