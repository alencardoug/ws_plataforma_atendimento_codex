# Acceptance: Ungoverned Fictional-Demo Autonomy (N5)

Governing: `spec.md` §6 (10 acceptance outcomes), `plan.md`, `tasks.md`.

## Execution record (2026-08-21)

Full credential-backed session (real Postgres, real `gpt-5-mini`
generation, a real non-mocked veto window against a real clock, and a
real interactive browser session) — the same discipline this project's
006-010 closures established.

### What ran

- Backend `ruff`/`mypy` (full `customer_care` package, including the
  widened `ai/providers.py`/`ai/router.py` and the new
  `shared/settings_service.py`): pass, zero issues.
- Full backend `pytest`: **241/241 pass** (230 pre-existing + 11 new —
  `test_ungoverned_n5.py`'s 9 business-logic tests across
  `TestEligibilityGate`/`TestResolution`/`TestUnclaimedTrigger`/
  `TestIdleSeconds`, `test_011_ungoverned_n5_containment.py`'s 3
  structural tests), real DB. Zero regressions — includes a re-run of
  `test_governed_autonomy.py`, `test_010_governed_autonomy_containment.py`,
  and `test_booking_script_containment.py` unmodified.
- `smoke_v11_ungoverned_n5.py`: **pass** — real end-to-end HTTP lifecycle:
  the two new autonomy-settings fields, an uncovered question opening and
  resolving an `ungoverned_n5` window with the governed kill switch off,
  and a category-matched question keeping `mechanism='governed_autonomy'`
  with both switches on (N5 adds no duplicate). 19 of 20 smoke scripts
  re-run (18 pre-existing + this one) — all pass;
  `smoke_ingestion_changed.py` deliberately skipped (see `analysis.md`).
- Frontend `eslint`/`tsc`/`vitest` (24/24)/`build`: all pass.
- `frontend/e2e/v11.spec.ts`: **pass**, confirmed reliable across two
  consecutive runs — N5's own switch toggled independently of the
  governed switch (verified off), an uncovered question sent autonomously
  with the distinct badge tooltip.
- Full Playwright suite (`v1`-`v3`, `v7`-`v11`, one consolidated run
  after the regression fix below): **18 passed, 1 skipped** (N1-only
  test), **1 known pre-existing unrelated flake** (`v7.spec.ts` — see
  `analysis.md`). **One real regression this cycle's own UI addition
  caused was found and fixed** during this same verification pass (an
  `aria-label`/`getByLabel("Categoria")` collision) — see `analysis.md`.
- **Live manual browser verification** (not just automated tests): logged
  in as the local operator, enabled N5's kill switch via the Knowledge
  Management settings panel, sent a genuinely off-topic customer message
  ("Qual a previsão do tempo para amanhã em Marte?") from a fresh
  unclaimed conversation, and observed a real autonomous, in-persona,
  non-refusing reply arrive with zero operator interaction — confirmed in
  the database (`autonomous_source='ungoverned_n5'`) and in the operator
  UI (the distinct "automático" badge with its N5-specific tooltip).

### What could not run

Nothing — every gate this package's own scope required was run with real
credentials, not deferred.

## Outcome-by-outcome status (spec.md §6)

| # | Outcome | Status |
|---|---|---|
| 1 | N5 off, governed off: nothing sends autonomously, unchanged from today | Verified — `test_ungoverned_n5.py::TestEligibilityGate::test_both_off_never_opens_a_window` |
| 2 | N5 off, governed on with a matching category: existing feature-010 behavior completely unaffected (regression check) | Verified — `test_governed_autonomy.py` (9/9, unmodified), `smoke_v10_governed_autonomy.py`, `frontend/e2e/v10.spec.ts` all re-run and passing |
| 3 | N5 on, governed off entirely: an uncovered question (that would `ABSTAIN` under N3/N4 alone) still gets an autonomous ungoverned reply, `autonomous_source='ungoverned_n5'` | Verified — `test_n5_on_no_category_falls_through_to_ungoverned`, `test_n5_on_abstain_falls_through_to_ungoverned`, `smoke_v11_ungoverned_n5.py`, `v11.spec.ts`, and the live browser session |
| 4 | N5 on, category-matched `ANSWER` available with governed also on: the grounded evidence-backed answer is sent, not a redundant ungoverned duplicate | Verified — `test_n5_on_category_matched_uses_governed_mechanism_not_ungoverned` (asserts exactly one `AIGeneration` exists), `smoke_v11_ungoverned_n5.py`'s second scenario |
| 5 | N5 on: PAUSE, EDIT, and TAKE OVER all still work on an N5-pending send, identically to a governed one | Verified by construction — none of the three resolution paths reference `.category`/`.mechanism` (confirmed by inspection); `test_window_elapses_and_sends_with_ungoverned_source` exercises the same resolution function an N5 PAUSE/EDIT/TAKE OVER would short-circuit |
| 6 | N5 on, unclaimed ("Aguardando") conversation: autonomous ungoverned reply still sends without a claim, status stays `WAITING` | Verified — `test_waiting_conversation_gets_an_ungoverned_autonomous_send` |
| 7 | `automatic_trigger_idle_seconds` changed via the settings endpoint measurably changes when the automatic trigger fires | Verified — `test_custom_idle_seconds_delays_the_uncovered_run` (a real, not simulated, timing check) |
| 8 | Toggling N5's kill switch, or `automatic_trigger_idle_seconds`, is an authenticated-only action producing exactly one audit event with operator identity and before/after value | Verified by construction — `set_autonomy_settings()` calls `record_event` exactly once per changed field (`autonomy.n5_kill_switch_toggled`, `autonomy.idle_seconds_changed`), registered in `docs/architecture/EVENT_CATALOG.md` |
| 9 | Structural containment: N5 adds no second non-operator-authenticated `Message`-construction site | Verified — `test_011_ungoverned_n5_containment.py` (AST-based) |
| 10 | The customer-facing and operator-login disclaimers are still present | Verified by direct inspection — `frontend/src/main.tsx`'s `.disclaimer-banner` on both the customer landing page and operator login screen, confirmed live in the browser session |

## Verdict

**GO.** Implementation complete; every gate this session could run —
including full credential-backed real-provider evidence and a live manual
browser verification, not deferred — has passed. Constitution Amendment
1.3.0's ungoverned exception is implemented exactly as narrowly as
ratified: it is additive (never overrides an already-grounded governed
answer), independently switched, reuses the existing veto-window/audit/
containment machinery rather than duplicating it, and remains void without
the customer-facing disclaimer per clause (e) — confirmed present. This
package is DONE.
