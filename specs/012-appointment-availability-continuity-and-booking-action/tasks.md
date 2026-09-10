# Tasks: Appointment-Availability Continuity + Operator Booking-Offer Action

Governing: `spec.md`, `plan.md`, `data-model.md`, `contracts/openapi.yaml`.
Implement in dependency order.

## Phase 1 — Migrations and models

- **T1.** `20260827_0001_v12_ai_generations_trigger_manual_booking_offer.py`
  — drop/recreate `ai_generations_trigger_check` adding
  `'MANUAL_BOOKING_OFFER'` (data-model.md §2). `downgrade()` restores the
  8-value list.
- **T2.** `20260827_0002_v12_system_settings_availability_floor_checked_at.py`
  — `ALTER TABLE customer_service.system_settings ADD COLUMN
  availability_floor_checked_at timestamptz NULL` (data-model.md §1).
- **T3.** ORM (`infrastructure/models.py`):
  `SystemSettings.availability_floor_checked_at: Mapped[datetime | None]`.

## Phase 2 — AC: Availability Continuity

- **T4.** `scheduling/seeding.py`: add `AC_FLOOR_MIN = 2`,
  `AC_FLOOR_TARGET = 8`, `AC_FLOOR_CHECK_INTERVAL_SECONDS = 60`,
  `_FLOOR_LOCK_KEY = 725017003`, and
  `_count_available_future_on(session, target_date, specialty_id, now)`
  (like `count_available_on()` but also `starts_at >= now`).
- **T5.** `scheduling/seeding.py`: `ensure_generalist_floor(session) ->
  None` (plan.md §3.1) — time-gate on
  `settings.availability_floor_checked_at`; advisory lock; for D+1 and
  D+7 top up to `AC_FLOOR_TARGET` when `<= AC_FLOOR_MIN` via
  `create_slots_on()`; set the timestamp; emit
  `scheduling.availability_floor_topped_up` only when `created > 0`;
  `except Exception: session.rollback()` — never raises into the caller.
- **T6.** `scheduling/bootstrap_seed.py` (new):
  `run_bootstrap_seed(session)` (calls `ensure_wide_availability()` then
  `ensure_seed_availability()`, emits
  `scheduling.availability_bootstrap_seeded`, commits) and `main()`
  (opens a session via `get_session_factory()`, runs it unconditionally
  — the `python -m` entry point).
- **T7.** `app/main.py`: add a FastAPI `lifespan` (the file has none
  today) whose startup branch calls `run_bootstrap_seed()` **iff**
  `os.environ.get("RUN_BOOTSTRAP_SEED")` is truthy. Must not import
  anything that creates an import cycle with `scheduling/availability.py`
  (import inside the lifespan fn if needed).
- **T8.** `operator_workspace/router.py::list_conversations()`: one line —
  `ensure_generalist_floor(session)` after the
  `evaluate_unclaimed_autonomous_trigger` loop, before
  `resolve_elapsed_autonomous_sends(session)` (plan.md §3.2).
- **T9.** `docker-compose.yml`: add `RUN_BOOTSTRAP_SEED: ${RUN_BOOTSTRAP_SEED:-false}`
  to `backend.environment`. `README.md`: add the `python -m
  customer_care.scheduling.bootstrap_seed` line after the existing
  `alembic upgrade head` / `knowledge.ingest` steps.

## Phase 3 — OB: Operator Booking-Offer action

- **T10.** `ai/router.py`: extract `_trailing_customer_messages(session,
  conversation) -> list[Message]` from `_uncovered_customer_run()`'s
  inline walk; `_uncovered_customer_run()` calls it (no behavior change —
  same rows, same order).
- **T11.** `ai/router.py`: `generate_booking_offer_draft(session,
  operator_id, conversation, manual_search_text) -> tuple[AIGeneration,
  list[dict]]` (plan.md §4.1): N2 guard → `409`; build `query_text` from
  `_trailing_customer_messages` + `manual_search_text`; `retrieve(...)`;
  `resolve_appointment_availability()` in `try/except
  DynamicResolutionError`; persist the `AIGeneration`
  (`trigger="MANUAL_BOOKING_OFFER"`, fields per data-model.md §3);
  `persist_presented_offers()` on ANSWER; attribute one
  `AIGenerationSource` to the `appointment_availability` hit when present;
  `derive_category_slug()`; emit `ai.draft_generated`/`ai.draft_abstained`
  + `ai.dynamic_pattern_resolved`/`ai.dynamic_pattern_fallback`; wrap
  unexpected errors as a `FAILED` generation + `503`.
- **T12.** `ai/router.py`: `class BookingOfferDraftIn(BaseModel):
  manual_search_text: str = ""` and
  `@router.post("/operator/conversations/{conversation_id}/booking-offer-draft",
  status_code=201) def booking_offer_draft(...)` — `403` guard identical
  to `draft()`, calls T11, returns `generation_dict(session, generation,
  evidence)`.

## Phase 4 — Frontend

- **T13.** `frontend/src/main.tsx`: in the operator conversation panel
  (`selected.status === "ACTIVE"` block), add a `btn-secondary` button
  "Gerar oferta de agendamento" **between the reply `</form>` and the
  "Encerrar conversa" control** (plan.md §4.4). `disabled={!aiEligible}`.
  New async `generateBookingOffer()` next to `generate()` — `POST` the new
  endpoint with `{ manual_search_text: searchQuery.trim() }`, then
  `setDraft(data)` + `refreshSelected()`. No new state. Do **not** touch
  the customer widget's own Enviar/Encerrar pair.
- **T14.** `frontend/src/main.tsx`: type the new endpoint's response as
  the existing draft/generation type (no new interface — shape matches).

## Phase 5 — Tests

- **T15.** `app/tests/test_availability_continuity.py` (new) — plan.md §6:
  bootstrap empty→seeded + idempotent re-run; `ensure_generalist_floor`
  fires below floor / no-ops above; debounce (≤1 count query per
  interval); advisory-lock concurrency never exceeds target;
  query-independence negative test (customer message vs. empty agenda →
  `ABSTAIN` + N5 reply, zero new slot rows).
- **T16.** `app/tests/test_booking_offer_draft.py` (new) — plan.md §6:
  happy path (`MANUAL_BOOKING_OFFER` ANSWER + offer presentations + a
  follow-on `"opção 2"` resolves via `interpret_slot_choice`); hint
  narrows specialty/day/period; empty agenda → ABSTAIN, no message;
  **never autonomous** (both kill switches on, `window_seconds=0` → zero
  `pending_autonomous_sends`, zero OPERATOR `messages`); auth matrix
  (`401/403`, not-assigned `403`, CLOSED `409`).
- **T17.** `app/tests/test_012_containment.py` (new, AST-based) —
  `"MANUAL_BOOKING_OFFER"` constructed in exactly one function;
  `maybe_open_autonomous_window` eligibility set unchanged;
  `ensure_generalist_floor` / `run_bootstrap_seed` never imported by
  `ai/router.py`, `anonymous_access/router.py`,
  `scheduling/availability.py`.
- **T18.** `app/tests/` OpenAPI test: the new path is present and matches
  the handler's actual request/response and status codes.
- **T19.** `frontend/src/main.test.tsx`: button placement, disabled
  states, click → endpoint call → draft panel populated, no send.
- **T20.** `frontend/e2e/v12.spec.ts` (new): operator clicks "Gerar oferta
  de agendamento", sees the offer block, sends it, customer picks a slot,
  flow proceeds.

## Phase 6 — Docs, gates, convergence

- **T21.** `docs/architecture/EVENT_CATALOG.md`: add
  `scheduling.availability_bootstrap_seeded` and
  `scheduling.availability_floor_topped_up` (data-model.md §5).
- **T22.** `specs/004-dynamic-appointment-availability/spec.md`: one-line
  forward pointer at AA-9 item 5 and at clarification item 6 —
  "**Superseded in part, 2026-08-27:** see
  `specs/012-…/spec.md` §4 and `DECISIONS.md` D-044 — two additional
  query-independent write entry points (bootstrap fill, low-water-mark
  top-up); the no-slot-generation-as-a-query-side-effect rule is
  preserved."
- **T23.** Full backend `pytest` (real DB), full smoke suite, full
  Playwright suite — re-run, not assumed. Observe the `CLAUDE.md`
  `test_appointment_seeding.py` / `n5_kill_switch_enabled` shared-dev-DB
  isolation traps (clear/restore around the affected files).
- **T24.** `ruff` / `mypy` clean; frontend `eslint` / `tsc` / `vitest` /
  `build` clean.
- **T25.** `analysis.md`: finalize the cross-artifact convergence review
  with implementation findings + the AA-9 supersession note + full-suite
  results + verdict.
- **T26.** `acceptance.md`: outcome-by-outcome record against `spec.md`
  §8, final verdict.
- **T27.** `DECISIONS.md` (D-044 → Implemented/DONE), `ROADMAP.md`,
  `PROJECT_STATE.md`, `CLAUDE.md` lifecycle-state bullet — mark feature
  012 DONE.
