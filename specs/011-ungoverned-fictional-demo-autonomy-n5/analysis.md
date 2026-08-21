# Analysis: Ungoverned Fictional-Demo Autonomy (N5)

## Cross-artifact convergence review (2026-08-21)

- `plan.md` §2 originally sketched reusing `rag_answer.md`'s existing
  prompt content plus one appended instruction for the ungoverned
  completion. Direct inspection of that file during implementation found
  its entire contract is built around evidence grounding and an `ABSTAIN`
  option — reusing it verbatim would have instructed the model to abstain
  and to only claim evidence-backed facts, directly contradicting
  `generate_ungoverned`'s purpose. Corrected in place
  (`ai/providers.py`'s `UNGOVERNED_N5_SYSTEM_PROMPT`, a small dedicated
  prompt, not file-backed) rather than left as a silent deviation from the
  plan — the comment at that constant's definition documents the
  correction and points back here.
- `plan.md` §6 anticipated moving `get_system_settings()` to a new shared
  module to avoid a circular import between `ai/router.py` and
  `operator_workspace/router.py`. Implemented exactly as planned
  (`customer_care/shared/settings_service.py`) — no deviation.
- `data-model.md` §2's `pending_autonomous_sends.mechanism` migration
  (`NOT NULL DEFAULT 'governed_autonomy'`, then drop the default) applied
  and verified against the real local database — every pre-existing row
  backfilled correctly, matching what the migration's own comment claims.
- `tasks.md` T1-T33 are all complete.

## The structural containment finding (Constitution Article X in practice)

`test_011_ungoverned_n5_containment.py` proves two things by AST
introspection, not behavior: (1) `generate_ungoverned_reply` is the only
site anywhere that constructs an `AIGeneration` with
`provider="ungoverned-n5"`; (2) `resolve_elapsed_autonomous_sends`
remains the *only* non-operator-authenticated `Message`-construction site
in the codebase — unchanged in count from feature 010. This is the
intended shape: N5 adds a second *upstream generation path*, not a second
*send mechanism* — both `governed_autonomy` and `ungoverned_n5` pending
rows resolve through the identical, already-reviewed
`resolve_elapsed_autonomous_sends()` function. A third, explicit AST test
(`test_generate_ungoverned_reply_never_attaches_evidence_sources`) proves
the ungoverned path never fabricates an `AIGenerationSource` row — an
ungoverned generation genuinely has no evidence to attribute, and the
test makes that a checked invariant rather than an assumption.

## Regression risk assessment

- **`maybe_open_autonomous_window()`'s governed branch is behaviorally
  identical to feature 010's original function** — same five conditions,
  same `_open_pending()` call, same early `return` once a window opens.
  The N5 branch is only ever reached when that branch's `if` did not
  already return, so no existing governed-autonomy test's behavior
  changes for any conversation whose category policy is off (the
  default) or N5's own switch is off (also the default).
- **`AUTOMATIC_TRIGGER_IDLE_SECONDS` → `system_settings.automatic_trigger_idle_seconds`**:
  the migration's `DEFAULT 8` exactly matches the deleted constant's
  value (confirmed by direct inspection before writing the migration, not
  assumed) — every existing deployment's behavior is unchanged until an
  operator explicitly changes the new setting. `test_automatic_draft_status.py`'s
  fake session needed a `.get()` method added (it previously only needed
  `.scalar()`) — a mechanical test-fixture update, not a behavior change,
  since the real value it returns matches the deleted constant exactly.
- **`pending_autonomous_sends.category` widened to nullable**: never
  narrows an existing constraint: `messages.autonomous_source`'s two
  independent CHECK constraints both widened again (the same two feature
  010 found and widened for `'governed_autonomy'`), following the exact
  same migration shape.
- **Full backend `pytest`: 241/241** (230 pre-existing + 11 new — 6
  business-logic tests in `test_ungoverned_n5.py`'s `TestEligibilityGate`/
  `TestResolution`/`TestIdleSeconds`, 2 in `TestUnclaimedTrigger`, 3
  containment tests), real DB, zero regressions.
- **Full smoke suite**: 19 of 20 scripts re-run (18 pre-existing +
  `smoke_v11_ungoverned_n5.py`), all pass — `smoke_ingestion_changed.py`
  deliberately skipped (it re-ingests the full catalog with deterministic
  test embeddings against this project's one shared dev database,
  corrupting real embedding-based retrieval for everything run afterward;
  a standing operational trap documented in `PROJECT_STATE.md`, unrelated
  to this cycle and out of scope to fix here).

## One real UI regression found and fixed during this cycle's own full-suite verification

The N5 kill-switch checkbox's *visible* label text ("Autonomia sem filtro
de evidência — N5 (demonstração fictícia, sem categoria/evidência
necessária)") contains the lowercase word "categoria" — Playwright's
`getByLabel("Categoria")` matches case-insensitively by substring against
the computed accessible name, so this collided with `v2.spec.ts`'s own
pre-existing category-`<select>` queries on the same Knowledge Management
page (2 tests broke: T126, T127). This is the identical collision class
feature 010 already hit once for the per-category autonomy checkboxes.
Fixed the same way: an explicit `aria-label` on the N5 checkbox
("Autonomia sem filtro de evidência (N5)"), decoupling its accessible
name from the human-readable label text entirely. Re-ran the full `v2`/
`v10`/`v11` set after the fix — all pass. Caught by actually re-running
the full pre-existing Playwright suite, not assumed safe from code review
alone — the same discipline this project's closure practice has used
since 006-009.

## A found-live, pre-existing test fragility unrelated to this cycle

`frontend/e2e/v7.spec.ts`'s guided-booking-completion test failed twice
during this cycle's own verification runs — at two *different* points
each time (once inside `sendCustomerMessage`'s own visibility assertion,
once inside `draftAndSend`'s checkbox interaction). This is
`specs/007-completed-booking-visibility/acceptance.md`'s already-known,
already-CONDITIONAL intermittent failure — confirmed unrelated to this
cycle by direct inspection: `git diff` against `app/customer_care/booking_script/`,
`app/customer_care/scheduling/guided_booking.py`, and
`frontend/e2e/v7.spec.ts` itself all show zero changes from this package.
One update to that issue's known characterization: it was previously
observed to reproduce "only in full-suite context, not in isolation" —
this session's runs found it reproducing in isolation too. Left
undisturbed, the same treatment `v1.spec.ts`'s original flake and this
project's other known pre-existing fragilities have received — not this
cycle's to fix without separate authorization.

## Verdict

**GO** — implementation matches `spec.md`/`plan.md`/`data-model.md`, with
the one plan-level correction (the dedicated N5 system prompt) documented
at the point it was found, not silently patched. Every gate this session
could run has passed: backend `pytest` 241/241, 19/20 smoke scripts (one
deliberately skipped for a documented, unrelated operational reason), and
the full Playwright suite (18 passed, 1 skipped, 1 known pre-existing
unrelated flake in `v7.spec.ts` — not newly introduced by this cycle,
root-caused by hand, not this cycle's to fix without separate
authorization). `v11.spec.ts` itself (this package's own acceptance test)
passed reliably across repeated runs, both alone and alongside `v10.spec.ts`.
Constitution Amendment 1.3.0's ungoverned exception is implemented exactly
as narrowly as ratified — see `acceptance.md` for the outcome-by-outcome
evidence. This was also verified live in a real browser session (not just
automated tests): a genuinely off-topic customer question
("Qual a previsão do tempo para amanhã em Marte?") in an unclaimed
conversation received a real, in-persona, non-refusing autonomous reply
with zero operator involvement, correctly tagged
`autonomous_source='ungoverned_n5'` in the database and shown with the
distinct badge tooltip in the operator UI.
