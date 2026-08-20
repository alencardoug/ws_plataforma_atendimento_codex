# Analysis: Two-Phase Clinical Evidence Selection

## Cross-artifact convergence review (2026-08-20)

- `spec.md` §1's direct-inspection claims (both `content` and
  `matched_child_excerpt` already present on every `CLINICAL` `Evidence`
  item; `select_evidence()` generic by `retrieval_hit_id`) were re-verified
  against the actual code before `plan.md` was written (`rag/service.py:75`,
  `ai/router.py:387-440`) — confirmed accurate, no drift.
- `plan.md`'s `EvidenceCandidate` design was implemented essentially
  verbatim in `frontend/src/main.tsx`; the one deviation is naming
  (`revealDocument`/`revealedEvidenceIds` match plan.md §5 exactly) — no
  substantive divergence between plan and code.
- `tasks.md` T1-T4 (component + wiring) are complete. T5 (Vitest) is
  complete and passing. T6 (correct the existing V3-10 test) and T7 (new
  `v9.spec.ts`) are written but **not executed** — see `acceptance.md`'s
  "What could not run in this session" section. T8 (frontend gates) is
  complete and passing. T9 (Playwright run) and T10 (backend gates) are
  **not executed** — no Compose stack available in this session. T11
  (empty alembic/openapi diff) is confirmed. T12 (this document) is in
  progress — finalization is blocked on T9/T10.
- No spec/plan/tasks contradiction found. No documentation drift requiring
  a repair to a higher-authority artifact (`AGENTS.md`'s authority order)
  was found during this review.

## Regression risk assessment

The one deliberate behavior change (EV-5's scroll-target correction to
V3-10) is the only place this package could plausibly regress prior
acceptance evidence. It is scoped to a single existing test
(`frontend/e2e/v3.spec.ts`'s V3-10 scenario), which this package updates in
place rather than leaving stale — so a future run either passes with the
corrected assertion or fails loudly, it cannot silently pass against
outdated expectations.

Every other change is additive (a new component replacing two call sites
that already existed) with no deletion of prior behavior for `ADMIN_QA`
evidence (EV-6) — low regression surface.

## Verdict

**GO** — implementation matches spec/plan with no drift found. The
credential-backed batch run (2026-08-20, see `acceptance.md`) confirms all
gates pass against a real Compose stack, including `v9.spec.ts` (new) and
`v3.spec.ts`'s corrected V3-10 test — which also surfaced and fixed one
real CSS-locator regression this package introduced (a descendant-vs-
direct-child combinator ambiguity once `EvidenceCandidate` cards started
nesting `.message-body` inside `.draft-panel`; see `acceptance.md`'s
closure section). This package is DONE (D-039) in
`PROJECT_STATE.md`/`ROADMAP.md`/`DECISIONS.md`, closing together with
006/007/008.
