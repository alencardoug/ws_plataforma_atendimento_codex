# Tasks: Ungoverned Fictional-Demo Autonomy (N5)

Governing: `spec.md`, `plan.md`, `data-model.md`.

## Phase 0 — Prerequisite (already done, ahead of this spec)

- **T0.** Customer-facing and operator-login disclaimer banners
  (`frontend/src/main.tsx` `.disclaimer-banner`, `frontend/src/styles.css`)
  — Amendment 1.3.0 clause (e)'s load-bearing precondition. Confirm still
  present at Phase 9 closure (spec.md N5-6).

## Phase 1 — Migrations and models

- **T1.** `20260821_0001_v11_system_settings_n5.py` — add
  `system_settings.n5_kill_switch_enabled` and
  `.automatic_trigger_idle_seconds` (data-model.md §1).
- **T2.** `20260821_0002_v11_pending_category_nullable.py` — drop
  `pending_autonomous_sends.category`'s `NOT NULL` (data-model.md §2).
- **T3.** `20260821_0003_v11_pending_mechanism.py` — add
  `pending_autonomous_sends.mechanism` (`NOT NULL DEFAULT
  'governed_autonomy'` then drop the default), its CHECK constraint
  (data-model.md §2).
- **T4.** `20260821_0004_v11_widen_autonomous_source_check.py` — widen
  `messages_autonomous_source_check` for `'ungoverned_n5'`
  (data-model.md §3).
- **T5.** `20260821_0005_v11_widen_messages_check.py` — widen
  `messages_check` for `'ungoverned_n5'` (data-model.md §3).
- **T6.** ORM: `SystemSettings.n5_kill_switch_enabled`,
  `.automatic_trigger_idle_seconds`; `PendingAutonomousSend.category:
  Mapped[str | None]`, `.mechanism: Mapped[str]` (`infrastructure/models.py`).

## Phase 2 — Provider and ungoverned generation

- **T7.** `GenerationProvider.generate_ungoverned(history, system_prompt)
  -> str` added to the `Protocol` (`ai/providers.py`, plan.md §2).
- **T8.** `OpenAIGenerationProvider.generate_ungoverned` — plain chat
  completion, no evidence, no JSON schema, always returns text
  (plan.md §2).
- **T9.** `DeterministicTestGenerationProvider.generate_ungoverned` —
  fixed deterministic text (plan.md §2).
- **T10.** `generate_ungoverned_reply(session, conversation,
  prior_generation) -> AIGeneration` — new function, `ai/router.py`
  (plan.md §3): builds history from `prior_generation`'s own selection,
  calls `generate_ungoverned`, persists the new `AIGeneration` row
  (`provider="ungoverned-n5"`, `category_slug=None`,
  `prior_generation_id=prior_generation.id`,
  `retrieval_run_id=prior_generation.retrieval_run_id`), records
  `ai.draft_generated` and `autonomy.n5_ungoverned_reply_generated`.

## Phase 3 — Eligibility and window-opening logic

- **T11.** `customer_care/shared/settings_service.py` (new) —
  `get_system_settings(session)`, moved verbatim from
  `operator_workspace/router.py` (plan.md §6); that module re-imports it
  for its own existing call sites.
- **T12.** `maybe_open_autonomous_window()` restructured into the two-branch
  form (plan.md §4): extract `_open_pending(session, generation,
  conversation, *, category, mechanism, window_seconds)` from the existing
  row-construction logic (byte-for-byte same fields, now parameterized);
  N3/N4 branch calls it with `mechanism="governed_autonomy"` and returns;
  N5 branch (only reached if N3/N4's branch didn't open a window) calls
  `generate_ungoverned_reply()` then `_open_pending(...,
  mechanism="ungoverned_n5", category=None)` when
  `settings.n5_kill_switch_enabled`.
- **T13.** `automatic_draft_status()` and `_uncovered_customer_run()` read
  `get_system_settings(session).automatic_trigger_idle_seconds` instead of
  the module constant `AUTOMATIC_TRIGGER_IDLE_SECONDS`, which is deleted
  (plan.md §6).

## Phase 4 — Resolution paths

- **T14.** `resolve_elapsed_autonomous_sends()`
  (`autonomy/service.py`): `autonomous_source="governed_autonomy"`
  (hardcoded) → `autonomous_source=pending.mechanism` (plan.md §5). Add
  `mechanism` to the `autonomy.message_sent` payload (data-model.md §5).
- **T15.** Confirm (no code change expected, verify by direct test): PAUSE
  (`pause_pending_autonomous_send`), EDIT (`send_operator_message`'s
  pending-resolution side effect), and TAKE OVER (`take_over`'s own side
  effect) all resolve an N5-mechanism pending row identically to a
  governed-autonomy one — none of the three reference `.category`.

## Phase 5 — Policy/settings endpoints and audit

- **T16.** `SetAutonomySettingsIn` gains `n5_kill_switch_enabled: bool |
  None`, `automatic_trigger_idle_seconds: int | None`
  (`operator_workspace/router.py`).
- **T17.** `set_autonomy_settings()` — two more branches, each its own
  audit event (`autonomy.n5_kill_switch_toggled`,
  `autonomy.idle_seconds_changed`), matching the two existing branches'
  pattern exactly (plan.md §7). Validate
  `automatic_trigger_idle_seconds >= 0`, same style as the existing
  `window_seconds >= 0` check.
- **T18.** `autonomy_settings_dict()` — include both new fields in the
  `GET /operator/autonomy-settings` response.

## Phase 6 — Read-side fields

- **T19.** `pending_autonomous_send_summaries()` and
  `pending_autonomous_send_fields()` (`operator_workspace/router.py`) —
  include `mechanism` in both dict outputs (already handle a `None`
  `category` correctly via plain passthrough — confirm, don't assume).
- **T20.** `PendingAutonomousSendSummary` (`shared/schemas.py`) —
  `category: str | None` (was `str`); add `mechanism: Literal["governed_autonomy",
  "ungoverned_n5"]`.

## Phase 7 — Frontend

- **T21.** Settings panel (Knowledge Management page, next to the
  existing window/kill-switch controls): number input for
  `automatic_trigger_idle_seconds`, checkbox for
  `n5_kill_switch_enabled` — label makes the demo-only scope explicit
  (plan.md §7).
- **T22.** `PendingAutonomousSendSummary`/`PendingAutonomousSend`
  TypeScript interfaces: `category: string | null`, add `mechanism`.
- **T23.** Badge tooltip branches on `mechanism`/`autonomous_source`:
  distinct text for `'ungoverned_n5'` (plan.md §7). `Message.autonomous_source`
  type widens to include `"ungoverned_n5"`.

## Phase 8 — Backend tests

- **T24.** `test_ungoverned_n5.py` — the eight scenarios in plan.md §8's
  test-plan list, same fixture-cleanup discipline (dedicated category,
  explicit FK-ordered teardown) as `test_governed_autonomy.py`.
- **T25.** `test_011_ungoverned_n5_containment.py` — AST-based: exactly
  one `provider="ungoverned-n5"` construction site
  (`generate_ungoverned_reply`); `resolve_elapsed_autonomous_sends()`
  remains the only non-operator-authenticated `Message`-construction site
  (count unchanged from feature 010 — Article X).
- **T26.** Re-run `test_governed_autonomy.py`,
  `test_010_governed_autonomy_containment.py`,
  `test_booking_script_containment.py` unmodified — zero regressions
  (plan.md §8).

## Phase 9 — Smoke, E2E, gates and convergence

- **T27.** `smoke_v11_ungoverned_n5.py` — real end-to-end HTTP: a
  genuinely uncovered question still gets an autonomous reply with N5 on/
  N3/N4 off; `mechanism`/`autonomous_source` values confirmed via the API
  response, not just the DB.
- **T28.** `frontend/e2e/v11.spec.ts` — N5 checkbox independent of N3/N4's;
  distinct badge tooltip on an N5-sent message.
- **T29.** Full backend `pytest`, full smoke suite, full Playwright suite
  — re-run, not assumed safe (matches feature 010's own closure
  discipline).
- **T30.** Confirm T0's disclaimer banners are still present by direct
  inspection (spec.md N5-6) — part of `analysis.md`, not a runtime
  assertion.
- **T31.** `analysis.md` — cross-artifact convergence review, any findings
  from T29's full-suite re-run, final verdict.
- **T32.** `acceptance.md` — outcome-by-outcome record against spec.md §6,
  final verdict.
- **T33.** `PROJECT_STATE.md`/`ROADMAP.md`/`DECISIONS.md` (D-042
  status)/`CLAUDE.md` — mark feature 011 DONE.
