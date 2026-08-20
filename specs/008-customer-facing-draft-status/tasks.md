# Tasks: Customer-Facing Draft Status

Governing: `spec.md`, `plan.md`, `data-model.md`.

## Phase 1 — Backend

- **T1.** Add `customer_draft_status()` to
  `app/customer_care/anonymous_access/router.py` (spec.md CS-1, verbatim).
- **T2.** Add `preparing_response: bool = False` to `ConversationOut`
  (`shared/schemas.py`).
- **T3.** Compose `customer_draft_status()` into `read_conversation()`
  only (plan.md §2).

## Phase 2 — Backend tests

- **T4.** New backend test(s) covering spec.md §6 outcomes 1-4: eligible
  → `True`; ineligible → `False`; N1/no-operator → always `False`; no
  `seconds_remaining` or other internal field leaks into the response.

## Phase 3 — Frontend

- **T5.** `CustomerConversation` gains `preparing_response: boolean`
  (`frontend/src/main.tsx`).
- **T6.** Render the new cue per plan.md §3 (own line, after the messages
  section, before the form — not sharing the "Digitando…" span).

## Phase 4 — Frontend tests

- **T7.** `main.test.tsx`: cue renders only when `preparing_response:
  true`; does not appear alongside/instead of "Digitando…" in a way that's
  ambiguous (outcome distinctness check).
- **T8.** New `frontend/e2e/v8.spec.ts` (continuing the v4/v5/v9
  package-number naming convention) covering spec.md §6 outcomes 1, 2, 5,
  6.

## Phase 5 — Gates and convergence

- **T9.** Backend `pytest`/`ruff`/`mypy`.
- **T10.** Frontend lint/typecheck/Vitest/build.
- **T11.** Diff `alembic/versions/` — must be empty; `contracts/
  openapi.yaml` gains exactly one field (`preparing_response`) on
  `ConversationOut`.
- **T12.** Playwright (`v1`-`v3`, `v8`, `v9`) + full `smoke_*.py` suite —
  requires a credential-backed Compose stack (see
  `009-two-phase-clinical-evidence/acceptance.md`'s same noted gap; not
  assumed available in every session).
- **T13.** Author `acceptance.md`/`analysis.md`; update
  `PROJECT_STATE.md`/`ROADMAP.md`/`DECISIONS.md` once T12 passes.
