# CLAUDE.md — Claude Code Entry Point

Read and obey `AGENTS.md` first.

## Current lifecycle state

- V1 implementation and acceptance are complete (closure verdict: GO,
  2026-08-13) and fully committed/pushed.
- The human explicitly authorized V2 discovery/specification on 2026-08-11.
  Its package is `specs/002-v2-commercial-product-experience/`.
- **V2 implementation is DONE (2026-08-17).** All 11 phases in its
  `tasks.md` (T000-T131) passed their gates, `acceptance.md`'s Execution
  record covers all 11 `spec.md` §5 outcomes, and `analysis.md` §6 records
  the final cross-artifact convergence review. `PROJECT_STATE.md` is the
  authoritative summary. The V2 runtime (which supersedes V1's UI/API
  surface where V2 changed it, while preserving every V1 safety invariant)
  is now the executable baseline.
- Dynamic appointment availability is a separate future feature, not part
  of the completed V2 package, unless a later human decision explicitly
  authorizes it. The human made exactly one narrow combination into V2 on
  2026-08-12 (D-028): the `dynamic_data_required=true` safety correction
  (deterministic, database-driven chunk-pattern substitution via a
  server-side allowlist, no LLM rewrite) — V2 Phase 7 implemented and
  closed this. Appointment-booking operations remain excluded from V2, as
  before.
- The human authorized V3 ("Measured N2") discovery/specification during
  V2's post-deployment review. Its package is
  `specs/003-v3-measured-n2/`.
- **V3 implementation is DONE (2026-08-18).** All 13 phases in its
  `tasks.md` (T000-T134) passed their gates, `acceptance.md`'s Execution
  record covers all 13 `spec.md` §5 outcomes, and `analysis.md` §6 records
  the final cross-artifact convergence review. `PROJECT_STATE.md` is the
  authoritative summary. The V3 runtime (which supersedes V1/V2's UI/API
  surface where V3 changed it — the operator feedback taxonomy,
  quick-approve, guided knowledge-CRUD inputs, evaluation cases, read-only
  metrics, and the four client-only UX corrections — while preserving
  every V1/V2 safety invariant) is now the executable baseline. This cycle
  also produced one approved correction to a V2 mechanism (D-030: the V2-2
  rate limiter's client-key derivation) — see `DECISIONS.md`.
- Dynamic appointment availability, N3 governed autonomy/policy
  enforcement, the specialist-escalation workflow (V5), and an automated
  evaluation-case re-run mechanism all remain out of V3's scope, unchanged
  from prior exclusions, unless a later human decision explicitly
  authorizes them.

Read in this order:

1. `.specify/memory/constitution.md`
2. `PROJECT_STATE.md`
3. `CLAUDE_CODE_HANDOFF.md`
4. `specs/003-v3-measured-n2/spec.md`
5. the complete V1/V2 packages, especially their `spec.md`, `plan.md`,
   `tasks.md`, `data-model.md`, contract, acceptance, analysis, and
   checklists
6. `SDD_MANIFEST.md`, `ROADMAP.md`, and `DECISIONS.md`
7. root architecture/security/data/test/operations documents
8. ADRs as referenced by the plan
9. the current Git diff before changing any file

## Operating modes

### V1 baseline and pending worktree review

The V1 acceptance result is historical evidence, not permission to discard the
uncommitted refinements. Before committing or building on them:

- inspect the diff and verify it remains in V1 scope;
- run the relevant quality gates available in the environment, including the
  newly added generation-strategy tests and credential-backed E2E when
  credentials are supplied;
- preserve the explicit-send, audit, token, and citation boundaries;
- commit only when the human requests a commit.

`PROMPT_REVIEW_V1_CLAUDE.md` remains available if an additional independent,
read-only closure review is requested; its historic instruction not to start V2
does not override this newer human authorization.

### Approved V1 correction

Only perform a correction after explicit human authorization. Follow the
authority order in `AGENTS.md`: repair the highest-authority artifact that must
change, propagate the decision through plan/tasks when required, analyze again,
then implement and rerun the affected gates. Do not broaden a defect fix into
future scheduling behavior.

### Approved V2 correction

Only perform a correction after explicit human authorization, following the
same authority-order process as a V1 correction above. D-030 (the V2-2 rate
limiter's client-key fix) is the one V2 correction made so far, done during
the V3 cycle (`DECISIONS.md`, `specs/003-v3-measured-n2/analysis.md` §6).

### V2 specification cycle — complete

`specs/002-v2-commercial-product-experience/` is the closed V2 package.
V2 implementation is DONE (2026-08-17); no further V2 spec/plan/tasks
authoring is expected unless a new correction is authorized (see above).

### V3 specification cycle — complete

`specs/003-v3-measured-n2/` is the closed V3 package. V3 implementation is
DONE (2026-08-18); no further V3 spec/plan/tasks authoring is expected
unless a new correction is authorized, following the same
repair-the-highest-authority-artifact process as a V1/V2 correction.

## General Claude Code behavior

Use installed Spec Kit commands/skills when available. When a future
specification cycle (V4/V5/other) is authorized, begin a fresh SDD
lifecycle and run its analysis before implementation, per `AGENTS.md`.

If a `grill-me` style skill is available, do **not** run it for V1 unless a genuinely unresolved design decision blocks implementation. The V1 product decisions are frozen. Use grilling for future features before their specs are finalized.

## Stop conditions

Stop the affected implementation and repair design artifacts first if:

- direct AI-to-customer send appears necessary;
- a data model cannot preserve the applicable token, authorization, citation,
  traceability, or audit invariant;
- a future feature's scope conflicts with its own specification or a V1/V2/V3
  safety boundary;
- the OpenAPI contract conflicts with its governing specification;
- selected evidence/context cannot be durably traceable without persisting
  chain-of-thought;
- real patient data becomes necessary.
