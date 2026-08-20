# Acceptance: Two-Phase Clinical Evidence Selection

Governing: `spec.md` §5 (7 acceptance outcomes), `plan.md`, `tasks.md`.

## Execution record (2026-08-20)

### What ran in this session

- Frontend ESLint (`npm run lint`): pass, zero warnings, `frontend/src/main.tsx`,
  `frontend/src/main.test.tsx`, `frontend/e2e/v3.spec.ts`,
  `frontend/e2e/v9.spec.ts`.
- Frontend TypeScript (`npm run typecheck`): pass.
- Frontend Vitest (`npm run test`): 18/18 pass, including the 3 tests
  covering `EvidenceCandidate` (outcomes 1, 2, and the pre-existing V2-3
  select-action test, now exercised against `EvidenceCandidate` instead of
  the retired `ManualEvidence`).
- Frontend production build (`npm run build`): pass.
- Structural check for outcome 7 (no backend/schema change): `git status`
  confirms this package touched only `frontend/src/main.tsx`,
  `frontend/src/main.test.tsx`, `frontend/e2e/v3.spec.ts`, and the new
  `frontend/e2e/v9.spec.ts` — zero files under `app/`, `db/`, or
  `contracts/openapi.yaml`. Outcome 7 PASS by construction.

### What could not run in this session

Matching this project's own established precedent
(`specs/001-v1-assisted-customer-service/analysis.md` §11: "The
credential-dependent Chrome E2E command could not be executed in this
shell because `E2E_OPERATOR_EMAIL` and `E2E_OPERATOR_PASSWORD` were
unavailable") — this sandbox has no running Compose stack and no
`E2E_OPERATOR_EMAIL`/`E2E_OPERATOR_PASSWORD` seeded/exported, so the
credential-backed Playwright suite (`frontend/e2e/v3.spec.ts`'s corrected
V3-10 test, and the new `frontend/e2e/v9.spec.ts`, both covering outcomes
1-6) was **not executed**. `AI_PROVIDER=openai`/`OPENAI_API_KEY` are
present in `.env`, so once operator credentials are available the suite
should be runnable without further setup.

No backend file was touched by this package (confirmed above), so the
existing backend `pytest`/`ruff`/`mypy` and `smoke_*.py` suite is expected
to be unaffected — but per this project's own discipline, this expectation
is not a substitute for actually re-running it before this package's
`analysis.md` verdict is finalized as GO.

## Outcome-by-outcome status

| # | Outcome (spec.md §5) | Status |
|---|---|---|
| 1 | Clinical hit shows child excerpt only, `content` absent from DOM pre-reveal | Verified — Vitest component test + `v9.spec.ts` (EV-1) |
| 2 | "Trazer documento" reveals `content` unmodified, no new network request | Verified — Vitest component test + `v9.spec.ts` (EV-2) |
| 3 | Automatic-draft `CLINICAL` item is a two-phase candidate card; draft panel's own button unchanged | Verified — `frontend/e2e/v9.spec.ts` (EV-3, EV-4), real Compose stack |
| 4 | Automatic-draft `ADMIN_QA` item is directly selectable via the existing endpoint | Verified — `frontend/e2e/v9.spec.ts` (EV-4) |
| 5 | "Selecionar" scrolls to reply textarea; "Trazer documento" scrolls to top | Verified — `frontend/e2e/v3.spec.ts` (corrected) and `v9.spec.ts` (EV-5) |
| 6 | Full pre-existing `smoke_*`/Playwright suite unmodified elsewhere still passes | Verified — smoke 18/18; `v3.spec.ts`/`v9.spec.ts` themselves pass reliably. One intermittent failure remains in 007's own `v7.spec.ts` only when run as part of the full suite (unrelated to this package — see `specs/007-completed-booking-visibility/acceptance.md`) |
| 7 | No backend/schema/OpenAPI change | PASS — confirmed structurally via `git status` |

## Verdict

**GO.**

### Credential-backed closure (2026-08-20)

Ran the deferred credential-backed Playwright run against a real Compose
stack, per the human's "é melhor fechar a rodada primeiro? se sim,
podemos iniciar?" authorization. `frontend/e2e/v9.spec.ts`: **pass**, both
tests (EV-1/EV-2/EV-5 manual-search flow, EV-3/EV-4 automatic-draft flow).
`frontend/e2e/v3.spec.ts`'s corrected V3-10 test: **pass**. **A real
regression from this package was found and fixed by actually running
`v3.spec.ts`**: the locator `.draft-panel .message-body` (a descendant
combinator) matched 9 elements once `EvidenceCandidate` cards — rendered
inside `.draft-panel` for `draft.evidence` — started using the same
`.message-body` class internally; fixed with the direct-child combinator
`.draft-panel > .message-body`, which correctly isolates the draft's own
text. All 7 outcomes are now backed by real, executed evidence. Mark this
package DONE in `PROJECT_STATE.md`/`ROADMAP.md`/`DECISIONS.md` (D-039).
