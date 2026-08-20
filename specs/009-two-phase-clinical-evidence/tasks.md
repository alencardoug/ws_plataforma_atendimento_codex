# Tasks: Two-Phase Clinical Evidence Selection

Governing: `spec.md`, `plan.md`, `data-model.md`. All tasks are in
`frontend/`; no backend task exists for this package (confirmed
frontend-only by `data-model.md`).

## Phase 1 — Component

- **T1.** Add `EvidenceCandidate` (plan.md §4) to `frontend/src/main.tsx`,
  replacing `ManualEvidence`. Check `frontend/src/main.test.tsx` for any
  direct `ManualEvidence` import before removing the export name; update
  or rename its imports/usages to `EvidenceCandidate`.
- **T2.** Add `revealedEvidenceIds` state and `revealDocument()` to
  `OperatorPage` (plan.md §5). Wire the reset into `clearDraftAndSearch()`,
  `open()`, and `closeConversation()` (plan.md §7 risk 1).
- **T3.** Switch both render call sites — `draft.evidence.map(...)`
  (`main.tsx:694`) and `searchEvidence.map(...)` (`main.tsx:697`) — to
  `EvidenceCandidate`, passing `revealed`/`onReveal`/`onSelect` per
  plan.md §5.
- **T4.** Change `selectEvidence()`'s post-select scroll from
  `window.scrollTo({top:0,...})` to scrolling `#operator-reply` into view
  (plan.md §5).

## Phase 2 — Frontend tests

- **T5.** `main.test.tsx`: `EvidenceCandidate` unit/component tests per
  plan.md §6 (child-excerpt-only default for `CLINICAL`, no `content` in
  DOM pre-reveal; reveal shows `content` with no new fetch; `ADMIN_QA`
  unchanged single-phase; `draft.evidence` renders as candidate cards, not
  inert labels).
- **T6.** `frontend/e2e/v3.spec.ts`: update the existing V3-10 test
  ("selecting evidence scrolls to top...") to assert the reply textarea
  scrolls into view instead of `window.scrollY` returning near 0. Rename
  the test and add an inline note linking `009-two-phase-clinical-
  evidence`/D-039 as the reason for the change.
- **T7.** New `frontend/e2e/v9.spec.ts`: scenarios per plan.md §6 —
  clinical search hit shows child-excerpt only by default; "Trazer
  documento" reveals the parent and scrolls to top; selecting the revealed
  parent scrolls to the reply textarea; an automatic draft's `CLINICAL`
  and `ADMIN_QA` evidence items are both independently selectable via
  `EvidenceCandidate`, and the draft panel's own "Usar sugestão"/"Usar
  documento completo" button is unaffected.

## Phase 3 — Gates and convergence

- **T8.** Run frontend lint, TypeScript, Vitest, production build.
- **T9.** Run the full Playwright suite (`v1.spec.ts`, `v2.spec.ts`,
  `v3.spec.ts`, `v9.spec.ts`) against a rebuilt Compose stack.
- **T10.** Run the full backend `pytest`/`ruff`/`mypy` and the complete
  `smoke_*.py` suite unmodified — confirms zero backend regression (no
  backend file is touched by this package).
- **T11.** Diff `alembic/versions/` and `contracts/openapi.yaml` against
  `main` — must be empty for this package, confirming data-model.md's "no
  data model impact" claim structurally, not just by assertion.
- **T12.** Author `acceptance.md` (Execution record covering spec.md §5's
  7 outcomes) and `analysis.md` (cross-artifact convergence review,
  verdict). Update `PROJECT_STATE.md`/`ROADMAP.md`/`DECISIONS.md` to mark
  `009-two-phase-clinical-evidence` DONE.
