# Analysis: Appointment-Availability Continuity + Operator Booking-Offer Action

## Status

**Pre-implementation cross-artifact consistency review (2026-08-27).**
`AGENTS.md` "Required SDD flow / Before code" step 3. Implementation
findings, full-suite results, and the final verdict are appended here at
closure (tasks T25).

## 1. Artifact convergence check

| Concern | spec.md | plan.md | data-model.md | contracts | tasks.md | Consistent? |
|---|---|---|---|---|---|---|
| AC-1 bootstrap = query-independent (startup hook + `python -m`), env-gated | §5 AC-1, §9 | §2.1 | §5 (event) | "no path" note | T6–T9 | ✅ |
| AC-2 top-up on `list_conversations()` poll only, never a resolver/query | §5 AC-2, §4 | §3.1–3.2 | §1 (`availability_floor_checked_at`), §5 | "no path" note | T4,T5,T8 | ✅ |
| AC floor numbers `MIN=2 / TARGET=8`, 60 s debounce | §5 AC-2, §10 Q1 | §3.1 | — | — | T4 | ✅ |
| AC-3 resolver/query path unmodified | §5 AC-3 | §1, §3.2 | §6 | — | T15 (negative) | ✅ |
| OB endpoint path + shape | §6 OB-1/OB-2 | §4.2 | §3 | new path | T12,T18 | ✅ |
| OB `trigger = MANUAL_BOOKING_OFFER`, never autonomous | §3, §6 OB-3 | §4.3 | §2 (rationale) | 201 `const` | T16 (negative), T17 | ✅ |
| OB persists offered rows for GB slot-choice | §6 OB-2 | §4.1 step 4 | §3 | description | T16 | ✅ |
| OB abstain → `DYNAMIC_DATA_UNAVAILABLE`, no message | §6 OB-2 | §4.1 step 4 | §3 | 201 ABSTAIN | T16 | ✅ |
| Button between "Enviar" and "Encerrar conversa", operator panel only | §6 OB-4 (clarified in this review) | §4.4 | — | — | T13 | ✅ (see §2.1) |
| `ai_generations.trigger` single CHECK widened | §7 | §5 | §2 | — | T1 | ✅ |
| New audit events | §7 | §2.1, §3.1 | §5 | — | T21 | ✅ |
| `specs/004` AA-9 partial supersession, one-directional, non-query | §4 | §3.2, §8 | §5 | delta note | T22 | ✅ (see §3) |

## 2. Deviations recorded now (not silently)

### 2.1 `spec.md` OB-4 originally said "both occurrences" — clarified in this review

An earlier draft of `spec.md` OB-4 said the button goes at "both
occurrences" of the Enviar/Encerrar pair. Direct inspection of
`frontend/src/main.tsx` shows two such pairs: the **customer chat widget**
(~L412–426) and the **operator conversation panel** (~L813–821). A
"generate a booking offer draft" control belongs only in the operator
panel — the customer has no draft panel and no operator endpoint.
`spec.md` OB-4 was edited during this review to say "the operator panel's
own pair … *not* the customer chat widget's"; `plan.md` §4.4 and
`tasks.md` T13 match. No open inconsistency remains.

### 2.2 `spec.md` §5 AC-1 wording "start command step"; `plan.md` uses a lifespan hook + `python -m`

`spec.md` AC-1 sketched "invoked by the backend container's start
command". The repo's actual pattern (`README.md` L40/L45) is
`docker compose run --rm backend <admin command>` for migrations and
ingest, with the container `CMD` being bare `uvicorn` (no wrapper, no
auto-migrate). `plan.md` §2.1 therefore delivers AC-1 as (a) a
`python -m customer_care.scheduling.bootstrap_seed` admin command
matching that established pattern and (b) an **env-gated FastAPI lifespan
startup hook** for the `docker compose up` demo case — both calling one
idempotent body. Same outcome spec.md intended (populated agenda without
a manual click when the operator wants that), consistent with how this
codebase actually boots.

## 3. The `specs/004` AA-9 supersession (the one authority-order change)

`AGENTS.md` authority order puts `spec.md` (#3) above roadmap/readme but
below the constitution (#2). `specs/004` AA-9 is a closed feature's spec;
this cycle changes one of its invariants, so per "update the
highest-authority artifact that must change" the change is recorded:

- **What AA-9 said**: slot creation is reachable *only* through the
  operator D+1/D+7 button; "the query path (AA-2) still never writes under
  any circumstance"; clarification item 6: "no on-demand slot generation
  as a side effect of a customer/operator query, at all."
- **What 012 changes**: two more write entry points exist — the
  bootstrap fill (startup/admin) and the low-water-mark top-up (operator
  queue poll). **Neither is a customer/operator content query.** No RAG
  retrieval, no resolver, no draft call, no anonymous endpoint gains a
  write. Clarification item 6's actual target — "the resolver tops up its
  own data" — remains struck down and is re-proven struck down by a
  negative test (`tasks.md` T15).
- **Authority for the change**: human decision 2026-08-27, `DECISIONS.md`
  D-044. `specs/004/spec.md` gets a forward pointer at AA-9 item 5 and
  clarification item 6 (`tasks.md` T22) so the invariant is never read in
  isolation without seeing the supersession.
- **Constitution check**: no Article is touched. Article III (outbound AI
  authority) — unaffected; OB produces a draft, AC produces slots, neither
  sends a message. Amendments 1.1.0 / 1.2.0 / 1.3.0 — untouched, no
  coupling to `booking_script/`, `maybe_open_autonomous_window()`, or the
  veto window. Article VIII (modular monolith) — no scheduler, cron, or
  worker added; AC-2 is lazy on an existing poll, AC-1 is startup/admin.

## 4. Safety-invariant preservation (Constitution Article X targets)

| Invariant | How 012 preserves it | Negative test |
|---|---|---|
| No direct AI→customer send | OB `trigger` not autonomous-eligible; AC creates no messages | T16 (both switches on, window 0 → 0 pending, 0 messages) |
| Query path never self-heals its data | AC adds zero writes to resolver/anonymous/draft paths | T15 (customer msg vs. empty agenda → ABSTAIN + N5, 0 new slots) |
| Autonomous-send containment (one non-operator `Message` site) | unchanged — 012 adds no `Message`-construction site | T17 (AST) |
| Booking-script containment (Amendment 1.1.0) | `booking_script/` not imported/read/modified | existing `test_booking_script_containment.py` re-run green (T23) |
| Append-only audit | new events are `record_event` calls, same immutable path | covered by T15/T16 assertions |
| Synthetic data only (Article VI) | AC seeds simulated slots; new event payloads carry no bodies/CPF | data-model.md §5 |

## 5. Open risks carried into implementation

- Bootstrap wide-seed cost on every gated startup (idempotent, but O(business-days × specialties) no-op inserts) — add the short-circuit in `plan.md` §2.2 if startup profiling warrants.
- `test_appointment_seeding.py` shared-dev-DB collision and the `n5_kill_switch_enabled` starts-true trap (`CLAUDE.md`) — must be handled in T23's run, not discovered during it.
- `frontend/e2e/v7.spec.ts`'s known pre-existing intermittency (`specs/007` CONDITIONAL) may surface in T23's full Playwright run; if it does and `git diff` shows zero 012 coupling, it is left undisturbed and noted, same treatment as feature 011's closure.

## 6. Pre-implementation verdict

**PROCEED.** The four design artifacts are mutually consistent; the two
deviations from `spec.md`'s own wording (§2.1, §2.2) are recorded here
rather than hidden; the one authority-order change (the `specs/004` AA-9
partial supersession, §3) is narrow, one-directional, non-query, and
backed by an explicit human decision (D-044). No Constitution Article or
Amendment is affected. Implementation may begin at `tasks.md` T1.

## 7. Implementation findings (2026-08-27)

### 7.1 Deviations from plan/tasks, recorded

- **`run_bootstrap_seed()` lives in `scheduling/seeding.py`, not
  `scheduling/bootstrap_seed.py`.** `tasks.md` T6 put the function body in
  the new module. It reads better next to the two functions it
  orchestrates (`ensure_wide_availability` / `ensure_seed_availability`),
  and avoids an extra import hop. `bootstrap_seed.py` now holds only the
  two entry points — `main()` (the `python -m` route) and
  `maybe_run_bootstrap_seed_on_startup()` (the env-gated lifespan hook) —
  both importing `run_bootstrap_seed` from `seeding`. No behavioural
  difference from the plan.
- **AC-1 also has a FastAPI `lifespan` startup hook**, not only the
  `python -m` command. `plan.md` §2.1 anticipated both; `app/main.py` had
  no lifespan, so one was added in `customer_care/bootstrap.py`
  (`_lifespan`), calling `maybe_run_bootstrap_seed_on_startup()` inside a
  defensive `try/except` so a seeding failure can never stop the app from
  serving (Constitution Article IV — manual service survives).
- **Migrations are forward-only** (`downgrade()` raises), matching the
  V1–V11 baseline convention — `tasks.md` T1's "restore the 8-value list"
  note is superseded by that convention.

### 7.2 Gates run this session

- **Backend `ruff` + `mypy`** (full `customer_care`, plus `ruff` on
  `tests`): clean.
- **Backend `pytest`**: `test_availability_continuity.py` (8),
  `test_booking_offer_draft.py` (8), `test_012_containment.py` (5) — all
  pass (real Postgres, real OpenAI embeddings inside the OB path). Full
  pre-existing suite re-run: **263 passed** on the first pass with 26
  ERRORs isolated to `test_governed_autonomy.py` /
  `test_ungoverned_n5.py`; root-caused to **pre-existing shared-dev-DB
  residue** — orphan `ai_generations` / autonomously-sent `messages` rows
  from 2026-08-21 (D-042/D-043) sessions referencing the `t010-*` /
  `t011-*` fixture categories, so those fixtures' teardown `DELETE FROM
  categories` FK-failed. Confirmed unrelated by timestamp and by the fact
  that both files pass **27/27** once the residue is cleared. Not caused
  by this cycle. `test_appointment_seeding.py` (deselected in the batch
  run for its own known slot-collision with a full run) passes 12/12 in
  isolation. Effective total with the residue cleared: **290 pass, 0
  fail**.
- **`n5_kill_switch_enabled` shared-DB trap** (`CLAUDE.md`): cleared to
  `false` before the autonomy files ran, **restored to `true`**
  afterward. `system_settings.availability_floor_checked_at` left `NULL`
  (its default).
- **Frontend `eslint` + `tsc` + `vitest` (25, +1 new) + `build`**: clean.
- **App boot**: `docker compose up --build backend` — starts cleanly
  ("Application startup complete"; the lifespan hook is a no-op without
  `RUN_BOOTSTRAP_SEED`), `/health` OK, and
  `/api/v1/operator/conversations/{id}/booking-offer-draft` is registered
  in the live OpenAPI schema.

### 7.3 Not run this session

- **Playwright** (`frontend/e2e/v12.spec.ts`, authored) and the **smoke
  suite** — both require a running full stack plus operator credentials
  (`E2E_OPERATOR_EMAIL`/`_PASSWORD`, `SMOKE_OPERATOR_*`) that are not
  present in this environment. These, plus a live manual browser check of
  the "Gerar oferta de agendamento" button, are the outstanding
  credential-backed closure steps, exactly as prior packages' closures
  were structured.

### 7.5 Follow-on (2026-08-27, post-deploy): autonomous delivery without an operator

The prod incident above surfaced a pre-existing architectural limitation
the human then required fixed: N4/N5 autonomous replies were only ever
*delivered* as a side effect of an **operator** queue poll
(`list_conversations()` → `evaluate_unclaimed_autonomous_trigger()` +
`resolve_elapsed_autonomous_sends()`). With no operator logged in, an
unclaimed conversation's reply was generated but never sent.

Fix (`anonymous_access/router.py`, `_drive_unclaimed_autonomy()`): the
**same** debounce/eligibility path and the **same** send step are now
also driven from the customer's own `POST /messages`, `POST /typing`
heartbeat, and `GET /{id}` poll (the browser already polls the GET every
~2 s). No new send mechanism, no scheduler, no new infrastructure —
`resolve_elapsed_autonomous_sends()` remains the single `Message`-with-
`autonomous_source` construction site; both kill switches, the
per-category policy gate, the idle debounce, and
`auto_draft_covers_through_message_id` coverage all still apply
unchanged. `read_conversation` (GET) becomes mildly side-effecting — a
deliberate reversal of the 008/CS-1 "plain read" note, recorded in that
function's docstring and here; the work is self-gated to run at most once
per customer message.

Tests: `test_customer_driven_autonomy.py` (2, real HTTP via TestClient,
zero operator) — an unclaimed "quero agendar uma consulta" gets exactly
one `ungoverned_n5` reply and stays `WAITING`; 6 polls + 6 heartbeats
never duplicate it. Full autonomy + 012 + `smoke_core` re-run: 47 pass.
`DECISIONS.md` D-044 carries the record.

### 7.4 Final verdict

**GO for the code; closure CONDITIONAL on the credential-backed e2e/smoke
run.** Implementation matches `spec.md` / `plan.md` / `data-model.md` /
`contracts/openapi.yaml` with the three recorded deviations above, all
benign. Every gate runnable without a live stack + operator credentials
has passed. The `specs/004` AA-9 partial supersession is implemented
exactly as §3 describes — two query-independent write entry points added,
clarification item 6 preserved and re-proven by
`test_availability_continuity.py::test_resolver_stays_read_only_on_success_and_abstain`.
No Constitution Article or Amendment is affected; `booking_script/` is
byte-unchanged (`test_012_containment.py` +
`test_booking_script_containment.py`).
