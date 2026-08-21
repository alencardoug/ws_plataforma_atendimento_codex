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
- Dynamic appointment availability is a separate feature, not part of
  the completed V2 package. The human made exactly one narrow combination into V2 on
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
- N3 governed autonomy/policy enforcement, the specialist-escalation
  workflow (V5), and an automated evaluation-case re-run mechanism all
  remain out of scope, unchanged from prior exclusions, unless a later
  human decision explicitly authorizes them.
- **Dynamic appointment availability is DONE (2026-08-19).** Its package
  is `specs/004-dynamic-appointment-availability/`; all 10 phases passed
  final acceptance and convergence. AA-10's fixed simulation is the sole
  Constitution Amendment 1.1.0 exception and is structurally contained.
  Real booking, holds, payment, identity persistence, and every
  `dynamic_resolver` name besides
  `appointment_availability` (`price_lookup`/`payment_simulator`/
  `insurance_lookup`) remain explicitly deferred — see that package's
  `spec.md` §6.
- **Dynamic pricing and guided booking selection is DONE (2026-08-19,
  D-032).** Its package is
  `specs/005-dynamic-pricing-and-guided-booking/`. Implements the
  `price_lookup` named resolver (deferred by 004), corrects the
  `preco`/`pagamento` Q&A content that previously described a payment
  mechanism the system never had, and adds embedding-assisted guided
  booking selection — slot-choice and confirmation-intent interpretation
  that stays entirely inside N2 (ordinary operator-reviewable drafts
  only). Constitution Amendment 1.1.0's AA-10 exception is unchanged and
  was not extended — a deliberate human decision, verified structurally
  (`booking_script/*` untouched, zero import coupling). `insurance_lookup`/
  `convenio` remains deferred — see that package's `spec.md` §6.
- The human authorized four specification cycles on 2026-08-20 (D-036,
  D-037, D-038, D-039), each registered in `ROADMAP.md`:
  `specs/006-specialty-scheduling-breadth/`,
  `specs/007-completed-booking-visibility/`,
  `specs/008-customer-facing-draft-status/`, and
  `specs/009-two-phase-clinical-evidence/`. Implemented in order
  009 → 008 → 007 → 006 (smallest/lowest-risk first), then closed with a
  full credential-backed batch (real Postgres, real embeddings, real LLM
  calls) the same day. **006/008/009 are DONE (verdict GO). 007 remains
  CONDITIONAL** — its own new `frontend/e2e/v7.spec.ts` has one
  unresolved intermittent failure (reproduces only in the full-suite
  context, not in isolation) found during closure; see
  `specs/007-completed-booking-visibility/acceptance.md`.
- **The human authorized V4 (N3 governed autonomy) and V9 (N4 HOTL) as a
  single cycle on 2026-08-20 (D-041)**, `specs/010-governed-autonomous-response/`,
  after a grill session (`docs/sdd/GRILL_GATE.md`) resolved the
  architecture the roadmap's own bullets had left undefined. **This is
  the first time the system can send an LLM-generated draft to a customer
  without a per-message operator click** — Constitution Amendment 1.2.0
  ratifies one narrow, bounded exception to Article III for it (never
  immediate by default, always evidence-gated, default-off at every
  level, mandatory global kill switch). **Implementation is DONE
  (2026-08-20)** — `spec.md`/`plan.md`/`data-model.md`/`tasks.md`/
  `acceptance.md`/`analysis.md` are complete, verdict **GO**, with
  credential-backed closure run the same session (not deferred). See
  `specs/010-governed-autonomous-response/acceptance.md` for the full
  outcome-by-outcome record, including two real UI regressions this
  cycle's own additions caused in pre-existing Playwright tests (found
  and fixed the same session) and one found-but-unrelated pre-existing
  `v3.spec.ts` fragility left undisturbed.
- **The human requested a second, independent autonomy exception on
  2026-08-21 (D-042)**, `specs/011-ungoverned-fictional-demo-autonomy-n5/`
  — "N5". The initial ask (a checkbox bypassing evidence-gating entirely
  for every message) was declined as first framed; the human then
  supplied the context that changes the calculus — this project is a
  technical-portfolio/interview-demonstration system, not a real clinical
  service — and the request was resolved through its own grill session
  into a formal, bounded exception rather than an ad hoc toggle.
  Constitution Amendment 1.3.0 ratifies it: N5 has its own independent
  kill switch (never implied by Amendment 1.2.0's), applies to every
  AUTOMATIC-eligible message when on (including overriding the
  never-autonomous-on-`ABSTAIN` rule, but only while N5's own switch is
  on), is purely additive (never overrides an already-grounded N3/N4
  answer), and is void without the customer-facing "fictional technical
  demonstration" disclaimer added as a prerequisite
  (`frontend/src/main.tsx`'s `.disclaimer-banner`). Also made the
  automatic-trigger idle debounce operator-configurable
  (`system_settings.automatic_trigger_idle_seconds`, shared by both
  mechanisms). **Implementation is DONE (2026-08-21)** —
  `spec.md`/`plan.md`/`data-model.md`/`tasks.md`/`acceptance.md`/
  `analysis.md` are complete, verdict **GO**, with credential-backed
  closure (real Postgres, real LLM generation, and a live manual browser
  verification) run the same session. See
  `specs/011-ungoverned-fictional-demo-autonomy-n5/acceptance.md` for the
  full outcome-by-outcome record, including one real UI regression this
  cycle's own addition caused (found and fixed the same session) and an
  update to `v7.spec.ts`'s already-known pre-existing intermittency
  (now also reproduces in isolation, not only full-suite context).
- **D-043 correction is DONE (2026-08-21).** Human-reported from a real
  conversation run against a rebuilt local Docker stack: N5 discarding an
  already-grounded answer for a fresh evidence-free one whenever the
  governed (010) kill switch was off; AA-10's `booking_script` racing
  ahead of GB's (005) own slot-choice step on a generic booking phrase;
  the resulting booking summary missing date/time (a direct consequence);
  and a genuine follow-up question left with no reply at all (two
  independent causes: a stale-offer-set detection gap once `booking_script`
  completed a booking, plus GB's own ordinal parser misreading common
  Portuguese words like "primeira" embedded in an unrelated sentence as a
  slot choice). See `DECISIONS.md` D-043 and `PROJECT_STATE.md` for full
  detail, including an accepted, human-confirmed consequence: AA-10's
  `booking_script` standalone HTTP entry point is now structurally
  unreachable in every real scenario (GB always wins) — `booking_script/
  service.py` itself is unmodified and Amendment 1.1.0's exception remains
  exactly as narrow as authorized.
- **D-043-2 correction is DONE (2026-08-21).** Second, immediate
  follow-on correction, human-reported from a second real conversation
  right after D-043 shipped, same root theme: a bare "Oi" autosent an
  entire unrelated clinical document (`full_parent_draft()`'s clinical
  shortcut had no relevance threshold at all — fixed with a real-score-
  calibrated `_AUTONOMOUS_CLINICAL_MIN_SCORE=0.40`, autonomous-send-only,
  N1/N2 manual drafting unaffected); and three customer replies GB
  correctly interpreted got no reply at all (GB's own generations never
  carried `trigger=="AUTOMATIC"`, so D-043's own extended N5 mechanism
  still excluded them — fixed by extending N5 only, never N3/N4, to also
  cover GB's own trigger values). See `DECISIONS.md` D-043-2 and
  `PROJECT_STATE.md` for full detail, including a noted pre-existing test-
  isolation gap: `test_governed_autonomy.py`/`test_ungoverned_n5.py`
  assume `n5_kill_switch_enabled` starts false, but this shared dev DB's
  own live/demo state has it true — clear it before running either file's
  full suite and restore afterward.

Read in this order:

1. `.specify/memory/constitution.md`
2. `PROJECT_STATE.md`
3. `CLAUDE_CODE_HANDOFF.md`
4. `specs/004-dynamic-appointment-availability/spec.md` (latest closed
   cycle)
5. the complete V1/V2/V3 packages, especially their `spec.md`, `plan.md`,
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

### Dynamic appointment availability — complete

`specs/004-dynamic-appointment-availability/` is a completed package. Its
`spec.md`, `plan.md`, `data-model.md`, `tasks.md`,
`acceptance.md`, and `analysis.md` are complete; Phases 0-10 are DONE and
the final verdict is GO (`analysis.md` §18). The implemented frontend
surface is the operator's bounded D+1/D+7 seed button/status plus the
optional autonomous-message transparency badge. Do not broaden AA-10 or
start a deferred scheduling feature without a new authorized package.

### Dynamic pricing and guided booking selection — complete

`specs/005-dynamic-pricing-and-guided-booking/` is a completed package
(D-032). Its `spec.md`, `plan.md`, `data-model.md`, `tasks.md`,
`acceptance.md`, and `analysis.md` are complete; all 8 phases are DONE and
the final verdict is GO (`analysis.md` §6). Implements `price_lookup`
(reusing 004's pricing data), corrects the `preco`/`pagamento` Q&A
content, and adds embedding-assisted guided booking selection (slot-choice
and confirmation-intent interpretation) fully inside N2 — no frontend
change was required (existing draft panel already renders the new
generation content). Do not extend Constitution Amendment 1.1.0's AA-10
exception, and do not implement `insurance_lookup`/`convenio` or real
payment behavior without a new authorized package.

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
