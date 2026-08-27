# Acceptance: Appointment-Availability Continuity + Operator Booking-Offer Action

Governing: `spec.md` §8 (12 acceptance outcomes), `plan.md`, `tasks.md`.

## Status

**Implemented 2026-08-27; closure CONDITIONAL** on a credential-backed
e2e/smoke run (Playwright/smoke need a running stack + operator
credentials not available in the implementation session). All backend +
frontend-unit + lint/type/build gates are green and the app boots with
the new route registered.

## Outcome checklist (spec.md §8)

| # | Outcome | Evidence | Status |
|---|---|---|---|
| 1 | AC bootstrap guarantees the generalist D1 (≥1) / D7 (≥3) minimum; re-run = 0 new rows, event payload counts all 0 | `test_availability_continuity.py::test_bootstrap_guarantees_generalist_minimum_and_is_idempotent` (wide fill stubbed — full volume is smoke territory) + `::test_startup_hook_is_a_noop_without_the_env_flag` | ✅ unit |
| 2 | AC top-up fires below floor → `AC_FLOOR_TARGET`, one `scheduling.availability_floor_topped_up`; above floor → nothing | `::test_floor_tops_up_when_at_or_below_min`, `::test_floor_is_a_noop_when_inventory_is_healthy` | ✅ unit |
| 3 | AC top-up debounced: a re-call inside `AC_FLOOR_CHECK_INTERVAL_SECONDS` runs no counting query | `::test_floor_check_is_debounced` (monkeypatched counter) | ✅ unit |
| 4 | AC query-independence: resolving availability (success or abstain) creates no slot; query/anonymous modules never import a seeding entry point | `::test_resolver_stays_read_only_on_success_and_abstain`; `test_012_containment.py::test_ac_seed_entrypoints_not_imported_by_query_or_anonymous_modules`, `::test_ai_router_does_not_create_slots` | ✅ unit |
| 5 | AC concurrency: two `ensure_generalist_floor()` calls never exceed `AC_FLOOR_TARGET` | `::test_concurrent_floor_calls_never_exceed_target` (threaded advisory-lock) | ✅ unit |
| 6 | OB happy path: `MANUAL_BOOKING_OFFER` `ANSWER` + `appointment_offer_presentations`; a later `"opção 1"` resolves via `interpret_slot_choice()` unchanged | `test_booking_offer_draft.py::test_offer_then_slot_choice_flow` | ✅ unit / ⧗ e2e `v12.spec.ts` |
| 7 | OB hint narrows to a named specialty | `::test_hint_narrows_to_named_specialty` | ✅ unit |
| 8 | OB abstains cleanly: no matching agenda → `ABSTAIN` / `DYNAMIC_DATA_UNAVAILABLE`, no OPERATOR message | `::test_empty_agenda_abstains_without_a_customer_message` | ✅ unit |
| 9 | OB never autonomous: both kill switches on, `autonomy_window_seconds=0` → no `pending_autonomous_sends`, no customer-visible message; `MANUAL_BOOKING_OFFER` absent from `maybe_open_autonomous_window` | `::test_never_opens_an_autonomous_send_even_with_both_kill_switches_on`; `test_012_containment.py::test_manual_booking_offer_is_not_autonomous_eligible`, `::test_manual_booking_offer_trigger_has_one_construction_function` | ✅ unit |
| 10 | OB auth: unauthenticated → 401/403; non-active/non-N2 → 409; new path in OpenAPI schema. (Not-assigned → 403 is `draft()`'s byte-identical guard.) | `::test_endpoint_requires_authentication`, `::test_rejects_non_active_or_non_n2_conversation`, `::test_openapi_schema_exposes_the_new_path` | ✅ unit |
| 11 | Frontend: button between "Enviar" and "Encerrar conversa" in the operator panel; enabled only for a claimed ACTIVE-N2 conversation; click populates the draft panel, sends nothing | `frontend/src/main.test.tsx` ("generates an appointment-availability offer as a draft, between Enviar and Encerrar conversa, sending nothing") | ✅ unit / ⧗ e2e `v12.spec.ts` |
| 12 | Regression: full backend `pytest`; `test_booking_script_containment.py` / `test_010_governed_autonomy_containment.py` unchanged and green; smoke suites | backend **290 pass, 0 fail** (`analysis.md` §7.2 — 26 first-pass ERRORs were pre-existing 2026-08-21 shared-DB residue, root-caused, cleared, both autonomy files 27/27) | ✅ pytest / ⧗ smoke |

## Execution record (2026-08-27)

Full detail in `analysis.md` §7.2. Summary:

- Backend `ruff`/`mypy` clean. `pytest`: 21 new tests
  (`test_availability_continuity.py` 8, `test_booking_offer_draft.py` 8,
  `test_012_containment.py` 5) pass against real Postgres + real OpenAI
  embeddings. Full pre-existing suite **290 pass, 0 fail** — the 26
  first-pass ERRORs were 2026-08-21 (D-042/D-043) shared-DB fixture
  residue (orphan `ai_generations`/autonomous `messages` referencing
  `t010-*`/`t011-*` categories); cleared, both files re-run **27/27**.
  `test_appointment_seeding.py` 12/12 in isolation.
- `n5_kill_switch_enabled` cleared for the autonomy-file run, **restored
  to `true`** afterward.
- Frontend `eslint`/`tsc`/`vitest` (25, +1 new)/`build` clean.
- App boots (`docker compose up --build backend`) — startup complete,
  `/health` ok, `POST /api/v1/operator/conversations/{id}/booking-offer-draft`
  registered in the live OpenAPI schema, lifespan bootstrap hook a safe
  no-op without `RUN_BOOTSTRAP_SEED`.

### Outstanding (credential-backed)

`frontend/e2e/v12.spec.ts` (authored, not run) and the smoke suite need a
running full stack + `E2E_OPERATOR_*` / `SMOKE_OPERATOR_*` credentials not
present in this environment, plus a live manual browser check of the
"Gerar oferta de agendamento" button.

## Verdict

**GO for the code; closure CONDITIONAL on the credential-backed e2e/smoke
run** (`analysis.md` §7.4). Implementation matches
`spec.md`/`plan.md`/`data-model.md`/`contracts/openapi.yaml` with three
recorded benign deviations (`analysis.md` §7.1). The `specs/004` AA-9
partial supersession is exactly as scoped — two query-independent write
entry points, clarification item 6 preserved and re-proven by test. No
Constitution Article or Amendment affected; `booking_script/`
byte-unchanged.
