# Tasks: Governed Autonomous Response (N3/N4)

Governing: `spec.md`, `plan.md`, `data-model.md`.

## Phase 1 — Migrations and models

- **T1.** `20260820_0005_v10_category_autonomy.py` — add
  `content.categories.autonomy_enabled` (data-model.md §1).
- **T2.** `20260820_0006_v10_system_settings.py` — create
  `customer_service.system_settings`, seed the singleton row
  (data-model.md §2).
- **T3.** `20260820_0007_v10_pending_autonomous_sends.py` — create
  `customer_service.pending_autonomous_sends`, both indexes
  (data-model.md §3).
- **T4.** `20260820_0008_v10_generation_operator_nullable.py` — drop
  `ai_generations.operator_id`'s `NOT NULL` (data-model.md §4).
- **T5.** ORM: `Category.autonomy_enabled`; new `SystemSettings`,
  `PendingAutonomousSend` classes; widen
  `AIGeneration.operator_id: Mapped[UUID | None]`
  (`infrastructure/models.py`).

## Phase 2 — Eligibility and window-opening logic

- **T6.** `maybe_open_autonomous_window(session, generation, conversation)`
  in `ai/router.py` (plan.md §3) — status/kill-switch/category checks,
  inserts the `PendingAutonomousSend` row.
- **T7.** One added call to `maybe_open_autonomous_window()` at the end of
  `evaluate_automatic_trigger()`'s successful `generate_draft()` branch —
  `evaluate_automatic_trigger()`'s own existing logic is otherwise
  untouched (plan.md §2, zero regression risk for claimed conversations).
- **T8.** `evaluate_unclaimed_autonomous_trigger(session, conversation)`
  — new function, mirrors `evaluate_automatic_trigger()`'s idle-timeout/
  uncovered-message/idempotency logic without the assigned-operator
  requirement, requires `status == "WAITING"`, calls
  `generate_draft(..., operator_id=None, allow_unclaimed=True, trigger="AUTOMATIC")`
  then `maybe_open_autonomous_window()` (plan.md §2).
- **T9.** `generate_draft()` gains `allow_unclaimed: bool = False`;
  status guard becomes conditional on it (plan.md §2). `operator_id`
  parameter type widens to `UUID | None`.
- **T10.** One added call to `evaluate_unclaimed_autonomous_trigger()`
  per `WAITING` row inside `list_conversations()`
  (`operator_workspace/router.py`, plan.md §2.4).

## Phase 3 — Resolution paths

- **T11.** `resolve_elapsed_autonomous_sends(session)` in `ai/router.py`
  — selects `PENDING` rows with `resolves_at <= now()`, sends the
  message (`author_type="OPERATOR"`, `operator_id=None`,
  `autonomous_source="governed_autonomy"`), updates
  `status="SENT", resolved_at=now()` guarded by `WHERE status='PENDING'`
  (plan.md §4, data-model.md §3's partial-unique-index race guard).
- **T12.** Call `resolve_elapsed_autonomous_sends()` from both
  `list_conversations()` (T10's call site) and
  `operator_conversation_detail()` (existing per-conversation poll).
- **T13.** `POST /operator/conversations/{id}/pending-autonomous-send/{pending_id}/pause`
  — new endpoint, `status="PAUSED"` (plan.md §4).
- **T14.** Existing manual-send endpoint
  (`POST /operator/conversations/{id}/messages`) resolves any `PENDING`
  row on that conversation to `status="EDITED"` as a side effect on
  success (plan.md §4).
- **T15.** Existing `POST /operator/conversations/{id}/take-over`
  resolves any `PENDING` row to `status="TAKEN_OVER"` as a side effect
  on success (plan.md §4).

## Phase 4 — Policy/settings endpoints and audit

- **T16.** `POST /operator/knowledge/categories/{slug}/autonomy` —
  toggles `autonomy_enabled`, records `autonomy.category_policy_changed`
  (data-model.md §6).
- **T17.** `GET`/`POST /operator/autonomy-settings` — reads/writes
  `system_settings.autonomy_window_seconds`/`autonomy_kill_switch_enabled`,
  records `autonomy.window_duration_changed`/`autonomy.kill_switch_toggled`
  as appropriate (data-model.md §6).
- **T18.** `docs/architecture/EVENT_CATALOG.md` — register the three new
  event types.

## Phase 5 — Read-side fields

- **T19.** `PendingAutonomousSend` surfaced on
  `operator_conversation_detail()`'s response (pending row for the open
  conversation, if any — status, `resolves_at`).
- **T20.** `ConversationSummaryOut`/`summary()` gains a lightweight
  pending-indicator (queue-item countdown, plan.md §5) — category and
  `resolves_at` only, not the full draft text (kept out of the list
  response for the same reason `automatic_draft_seconds_remaining`
  already is — payload size on a 2s-polled endpoint).

## Phase 6 — Frontend

- **T21.** Queue-item countdown badge for a pending autonomous send
  (plan.md §5).
- **T22.** Conversation-view pending panel: read-only draft preview,
  Pausar / Editar / Assumir controle buttons (plan.md §5).
- **T23.** Autonomy settings panel: category ON/OFF list, window-seconds
  input (0 allowed), kill switch (plan.md §5).
- **T24.** Generalize the existing `autonomous_source === "booking_script"`
  badge check to any non-null value, with source-specific title text
  (plan.md §5).

## Phase 7 — Backend tests

- **T25.** `test_governed_autonomy.py` — every `spec.md` §6 acceptance
  outcome, real-DB integration style (matching
  `test_guided_booking.py`/`test_appointment_wide_seeding.py`). Explicit
  negative tests (Constitution Article X) for: category off, kill switch
  off, `ABSTAIN`, manual-trigger — each its own test, zero
  `pending_autonomous_sends` rows produced.
- **T26.** `test_unclaimed_autonomous_trigger.py` (or folded into T25) —
  GA-6: `WAITING` status preserved through an autonomous send, capacity
  unaffected, later claim still works normally.

## Phase 8 — Smoke and E2E

- **T27.** `smoke_v10_governed_autonomy.py` — real-provider HTTP smoke,
  full lifecycle including an unclaimed-conversation send and a
  real-clock short-window (e.g. 2s) elapse-and-send case.
- **T28.** `frontend/e2e/v10.spec.ts` — PAUSE/EDIT/TAKE OVER and the
  `window_seconds=0` immediate-send case; reuse the deadlock-retry
  `psql()` pattern from `v7`/`v8`/`v9.spec.ts`.

## Phase 9 — Gates and convergence

- **T29.** Backend `ruff`/`mypy`/full `pytest` (real DB).
- **T30.** Frontend `eslint`/`tsc`/`vitest`/build.
- **T31.** Full `smoke_*.py` suite (all packages) — confirm zero
  regression for every conversation whose category policy/kill switch
  stay at their defaults.
- **T32.** Full Playwright suite (`v1`-`v3`, `v7`-`v10`) — one
  consolidated run.
- **T33.** `analysis.md` — cross-artifact convergence review, spec/plan/
  data-model/tasks consistency, regression-risk assessment.
- **T34.** `acceptance.md` — Execution record covering `spec.md` §6's
  12 outcomes with real evidence.
