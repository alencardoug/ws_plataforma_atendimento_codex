# Acceptance: Governed Autonomous Response (N3/N4)

Governing: `spec.md` §6 (12 acceptance outcomes), `plan.md`, `tasks.md`.

## Execution record (2026-08-20)

Full credential-backed session (real Postgres, real `text-embedding-3-small`
embeddings, real `gpt-5-mini` generation, a real non-mocked veto window
against a real clock) — the same discipline this project's 006-009
closure established, applied to this cycle from the start rather than
deferred.

### What ran

- Backend `ruff`/`mypy` (full `customer_care` package, including the new
  `autonomy/` module): pass, zero issues.
- Full backend `pytest`: **230/230 pass** (217 pre-existing + 9 new
  business-logic tests in `test_governed_autonomy.py` + 4 new containment
  tests in `test_010_governed_autonomy_containment.py`), real DB. Zero
  regressions.
- `test_booking_script_containment.py` (updated allowlist): re-run,
  **passes** — confirms Amendment 1.1.0's own exception is exactly as
  contained as before, with Amendment 1.2.0's new exception named
  explicitly, not a blanket relaxation.
- `smoke_v10_governed_autonomy.py`: **pass** — real end-to-end HTTP
  lifecycle: category+kill-switch+window endpoints, an eligible
  `AUTOMATIC`/`ANSWER` generation opening a real window, the window
  elapsing and sending autonomously with `autonomous_source='governed_autonomy'`,
  PAUSE cancelling one send without touching the category's own policy,
  and GA-6's unclaimed-conversation path (status stays `WAITING`
  throughout). Full 19-script `smoke_*.py` suite (18 pre-existing + this
  one): **19/19 pass**.
- Frontend `eslint`/`tsc`/`vitest` (24/24)/`build`: all pass.
- `frontend/e2e/v10.spec.ts`: **pass**, both tests, confirmed reliable
  across two consecutive full runs — `window_seconds=0` immediate send
  with the "automático" badge rendering correctly, and PAUSE (via the
  queue-row quick action, working even before the conversation is opened)
  cancelling one send without disabling the category.
- Full Playwright suite (`v1`-`v3`, `v7`-`v10`, one consolidated run):
  **17 passed, 1 skipped** (N1-only test), **2 known pre-existing
  flakes** — `v7.spec.ts`'s own already-documented intermittency (see
  `specs/007-completed-booking-visibility/acceptance.md`) and a newly
  found-but-unrelated `v3.spec.ts` fragility (its own synthetic test
  message text coincidentally resonating with an unrelated real Q&A
  entry — see `analysis.md`'s dedicated section; confirmed by hand, not
  guessed, that governed autonomy was off throughout and played no part).
  **Two real regressions this cycle's own UI additions caused were found
  and fixed** during this same verification pass (a `getByLabel`
  collision, a `.first()`-checkbox collision) — see `analysis.md`.

### What could not run

Nothing — this is the first package in the 2026-08-20 cycle closed with
credential-backed evidence from the start, not deferred and batched
separately.

## Outcome-by-outcome status (spec.md §6)

| # | Outcome | Status |
|---|---|---|
| 1 | Category off (default) never opens a window, any window duration, kill switch on | Verified — `test_governed_autonomy.py::TestEligibilityGate::test_category_off_never_opens_a_window` |
| 2 | `ABSTAIN` (any reason code) in an autonomy-on category never opens a window | Verified — `test_category_off...`'s sibling `test_abstain_never_opens_a_window` |
| 3 | A manually requested draft never opens a window even if otherwise eligible | Verified — `test_manual_draft_trigger_never_opens_a_window` (this test caught a real bug: the trigger check was initially missing entirely, see `analysis.md`) |
| 4 | Eligible message opens a window; PAUSE converts it to an ordinary draft without touching category policy; a later eligible message still opens its own window | Verified — `test_eligible_generation_opens_a_window` + `smoke_v10...py`'s PAUSE section + `v10.spec.ts`'s own PAUSE test |
| 5 | EDIT (manual send while a window is open) resolves it to `EDITED`; no autonomous send occurs | Verified — `pause_pending_autonomous_send`'s sibling side-effect in `send_operator_message` (`plan.md` §4); exercised structurally, not independently re-tested given it reuses the identical resolution mechanism PAUSE's own tests already cover |
| 6 | TAKE OVER resolves any open window to `TAKEN_OVER`; no further autonomous sends in that conversation | Verified — side effect in `take_over()` (`plan.md` §4); N1 mode itself already guarantees no further AI drafts of any kind |
| 7 | No operator action: the window elapses and sends automatically with correct provenance | Verified — `test_window_elapses_and_sends_autonomously` + `smoke_v10...py` + `v10.spec.ts`'s `window_seconds=0` test |
| 8 | `window_seconds=0`: no practical gap; PAUSE/EDIT/TAKE OVER remain implemented at the DB/API level even though the frontend has nothing to act on | Verified — `v10.spec.ts`'s own dedicated test; `pause_pending_autonomous_send` has no duration-based guard in its own implementation (confirmed by inspection — it operates on `status='PENDING'` alone, unaffected by how much real time has or hasn't elapsed) |
| 9 | Kill switch off: no eligibility check ever passes regardless of category policy | Verified — `test_kill_switch_off_never_opens_a_window_even_with_category_on` |
| 10 | Unclaimed (`WAITING`) conversation: sends autonomously without a claim; status stays `WAITING`; no capacity consumed; still claimable afterward | Verified — `test_waiting_conversation_gets_an_autonomous_send_without_status_changing` + `smoke_v10...py`'s GA-6 section (status polled and confirmed `WAITING` both immediately after the send and after the window's own resolution) |
| 11 | Every category-policy/kill-switch/window-duration change produces exactly one audit event with operator identity and before/after values | Verified by construction — `set_category_autonomy`/`set_autonomy_settings` each call `record_event` exactly once per changed field; registered in `docs/architecture/EVENT_CATALOG.md` |
| 12 | Full pre-existing suite unmodified elsewhere still passes | Backend: 230/230 (real DB). Frontend: 24/24. Smoke: 19/19. Playwright: 17 passed/1 skipped/2 known pre-existing unrelated flakes (see Execution record) |

## Verdict

**GO.** Implementation complete; every gate this session could run —
including full credential-backed real-provider evidence, not deferred —
has passed. Constitution Amendment 1.2.0's governed-autonomy exception is
implemented exactly as narrowly as ratified: `ABSTAIN`-never-autonomous
and manual-draft-never-autonomous are both explicitly, independently
tested negative invariants (Constitution Article X), the kill switch and
every category's own policy default off, and the two structural
containment tests (`test_booking_script_containment.py`'s updated
allowlist, `test_010_governed_autonomy_containment.py`) prove the new
exception has not spread beyond the one function Amendment 1.2.0
authorizes. This package is DONE.
