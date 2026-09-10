# Implementation Plan: Appointment-Availability Continuity + Operator Booking-Offer Action

Governing: `spec.md`. Data shapes: `data-model.md`. API surface:
`contracts/openapi.yaml`.

## 1. Technical summary

Two independent, low-coupling changes:

- **AC** touches only `scheduling/seeding.py` (two new functions),
  `scheduling/bootstrap_seed.py` (new tiny entry point), one
  `list_conversations()` call site, one `system_settings` column, and the
  backend container start command. It adds **no** code to any resolver,
  any anonymous endpoint, or `generate_draft()` — the `specs/004`
  clarification-6 invariant ("no slot generation as a side effect of a
  customer/operator query") is preserved and re-proven by a negative
  test.
- **OB** adds one authenticated endpoint + one `ai/router.py` function
  (`generate_booking_offer_draft()`), one `ai_generations.trigger` CHECK
  widening, and one frontend button. It reuses `resolve_appointment_availability()`,
  `retrieve()`, `persist_presented_offers()`, and `generation_dict()`
  verbatim — no new resolution logic, no LLM call, no autonomous-send
  path.

Neither change modifies `booking_script/`, the N3/N4/N5 mechanisms, the
veto window, or any Constitution-amendment surface.

## 2. AC-1 — Bootstrap fill

### 2.1 Entry point

New module `app/customer_care/scheduling/bootstrap_seed.py`:

```python
def run_bootstrap_seed(session: Session) -> None:
    """Idempotent. Fills the wide horizon for every specialty, then
    guarantees the AA-9 generalist D+1/D+7 minimum. Safe to run on every
    container start — ON CONFLICT DO NOTHING makes a re-run a fast no-op."""
    wide = ensure_wide_availability(session)          # existing, unchanged
    floor = ensure_seed_availability(session)         # existing AA-9, unchanged
    record_event(session, "scheduling.availability_bootstrap_seeded", "SYSTEM",
                 payload={"wide_slots_created": wide.slots_created,
                          "specialty_count": wide.specialty_count,
                          "business_day_count": wide.business_day_count,
                          "generalist_d1_created": floor.created_d1,
                          "generalist_d7_created": floor.created_d7})
    session.commit()

def main() -> None:      # `python -m customer_care.scheduling.bootstrap_seed`
    with get_session_factory()() as session:   # existing factory, infrastructure/database.py
        run_bootstrap_seed(session)
```

Two invocation routes, one idempotent body:

1. **Documented explicit step** — a `python -m
   customer_care.scheduling.bootstrap_seed` line added to `README.md`
   right after the existing `alembic upgrade head` /
   `python -m customer_care.knowledge.ingest` sequence (this project's
   established "administrative command, not a UI" pattern — `README.md`
   L40/L45). `main()` runs unconditionally when invoked this way; the
   operator chose to run it.
2. **App-startup convenience** — a FastAPI `lifespan` startup hook in
   `app/main.py` (the file currently has none) calls `run_bootstrap_seed()`
   **only when `RUN_BOOTSTRAP_SEED` is truthy**, so `docker compose up`
   with that env set (added to `docker-compose.yml`'s `backend.environment`,
   default off) gives a demo stack a populated agenda with no manual step.
   This is app startup, not a request/query side effect — `specs/004`
   clarification 6 is about the resolver/query path, which is untouched.

- **Resolves spec.md §10 Q3**: the startup hook is gated on
  `RUN_BOOTSTRAP_SEED` (dedicated flag, default off, set only in
  `docker-compose.yml` / deploy env — never in `pyproject.toml`/`pytest`
  config, so the test process never seeds; tests build their own
  fixtures). The `python -m` route has no flag — running it is itself the
  explicit opt-in. Not a reuse of `AI_PROVIDER`: the two concerns are
  orthogonal (a deterministic-provider dev run may still want a seeded
  agenda).
- **Resolves spec.md §10 Q2**: AC-1 runs *both* `ensure_wide_availability()`
  (breadth) *and* `ensure_seed_availability()` (the exact AA-9
  `count_d1>=1 && count_d7>=3` generalist guarantee the query-path
  fallback leans on). AC-2's floor keeps it topped up thereafter.

### 2.2 Idempotency / safety

Both reused functions are already `ON CONFLICT DO NOTHING` and already
hold their own advisory locks. A second `run_bootstrap_seed()` on an
already-seeded DB creates 0 rows and returns fast (the wide seeder's inner
loop still iterates business days, but every insert is a no-op — measured
acceptable for a once-per-container-start call; if profiling shows it is
not, add a cheap "already has N future slots" short-circuit, decided
during implementation, not now).

## 3. AC-2 — Low-water-mark top-up

### 3.1 New function, `scheduling/seeding.py`

```python
AC_FLOOR_MIN = 2       # spec.md §10 Q1 — "sempre que sobrar 2 ou 1"
AC_FLOOR_TARGET = 8     # headroom so it isn't re-triggered every poll
AC_FLOOR_CHECK_INTERVAL_SECONDS = 60
_FLOOR_LOCK_KEY = 725017003   # distinct from _SEED_LOCK_KEY / _WIDE_SEED_LOCK_KEY

def ensure_generalist_floor(session: Session) -> None:
    """Lazily called from list_conversations(). Never raises into the
    caller. Query-independent: reachable only from the operator queue
    poll, never from a resolver / draft / anonymous endpoint."""
    settings = get_system_settings(session)
    now = datetime.now(UTC)
    last = settings.availability_floor_checked_at
    if last is not None and (now - last).total_seconds() < AC_FLOOR_CHECK_INTERVAL_SECONDS:
        return                                   # cheap time gate, no slot query
    try:
        session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _FLOOR_LOCK_KEY})
        specialty_id = _generalist_specialty_id(session)
        today = _today_sao_paulo()
        d1 = next_business_day_sql(session, today + timedelta(days=1))
        d7 = next_business_day_sql(session, today + timedelta(days=7))
        created = 0
        before = {}
        for day in (d1, d7):
            have = _count_available_future_on(session, day, specialty_id, now)
            before[day.isoformat()] = have
            if have <= AC_FLOOR_MIN:
                created += create_slots_on(session, day, AC_FLOOR_TARGET - have, specialty_id)
        settings.availability_floor_checked_at = now
        if created:
            record_event(session, "scheduling.availability_floor_topped_up", "SYSTEM",
                         payload={"before": before, "created": created,
                                  "target": AC_FLOOR_TARGET, "min": AC_FLOOR_MIN})
        session.commit()
    except Exception:
        session.rollback()
```

- `_count_available_future_on()` is a small helper next to the existing
  `count_available_on()` — identical except it also enforces `starts_at >=
  now` (the existing one counts the whole calendar day). Added rather than
  changing `count_available_on()`, whose AA-9 callers want the
  whole-day semantics.
- Reuses `create_slots_on()` unchanged — its round-robin-within-business-
  hours insertion already tolerates being asked for more than a day can
  hold (it just stops).
- The `pg_advisory_xact_lock` + `availability_floor_checked_at` timestamp
  together mean two operators polling within the same 60 s window run the
  counting query at most once total (spec.md acceptance #3).

### 3.2 Call site — `operator_workspace/router.py::list_conversations()`

One line, once per poll (not per row), immediately after the existing
`for row in rows: ... evaluate_unclaimed_autonomous_trigger(...)` loop and
before `resolve_elapsed_autonomous_sends(session)`:

```python
    ensure_generalist_floor(session)
```

Rationale for this exact spot: it is the same lazy, no-scheduler
evaluation point feature 010 already established (`list_conversations()` is
polled by every logged-in operator's queue view), and it is demonstrably
**not** a customer/operator content query — it creates nothing in
response to a question, only in response to inventory having decayed.
`analysis.md` carries the `specs/004` AA-9 supersession note for this.

## 4. OB — Operator Booking-Offer action

### 4.1 New function, `ai/router.py`

```python
def generate_booking_offer_draft(session, operator_id, conversation, manual_search_text) -> tuple[AIGeneration, list[dict]]:
```

Mirrors `select_evidence()`'s structure (deterministic resolve → persist
`AIGeneration` → persist offered rows → events), but forces the
`appointment_availability` resolver instead of routing a pre-selected
hit:

1. Guard: `conversation.status == "ACTIVE" and conversation.effective_mode
   == "N2"` else `409 MODE_NOT_ALLOWED` (same message text as
   `generate_draft`).
2. Build `query_text`: the trailing customer-message run (reuse the same
   walk `_uncovered_customer_run()` does, extracted to a shared helper
   `_trailing_customer_messages(session, conversation)` so both call sites
   share one implementation), joined with `manual_search_text` when given.
   **Resolves spec.md §10 Q4**: trailing run, not just the latest message
   — parity with the automatic trigger; the resolver is keyword-based so
   extra text is low-risk, and an operator who wants to narrow it passes
   `manual_search_text`.
3. `run, evidence = retrieve(session, operator_id=operator_id,
   query=query_text, purpose="N2_DRAFT", top_k=8, conversation_id=...,
   triggering_message_id=<last trailing customer msg id>)` — a real
   retrieval run for Article V, and the source of the
   `appointment_availability` QA hit to attribute.
4. `try: resolution, offered_rows = resolve_appointment_availability(session, query_text)`
   - success → `AIGeneration(status="ANSWER",
     draft_text=resolution.pattern_text, provider="dynamic-pattern-resolver",
     model="not-applicable", trigger="MANUAL_BOOKING_OFFER",
     dynamic_pattern_used=True, retrieval_run_id=run.id,
     operator_id=operator_id)`; `persist_presented_offers(session,
     configured_embedding_provider(), generation.id, offered_rows)`;
     attribute `AIGenerationSource(use_order=1)` to the evidence item
     whose `matched_qa_id` resolves to a `dynamic_resolver ==
     "appointment_availability"` QA if present in `evidence`, else no
     source row (the resolution is still valid; attribution is
     best-effort, same as a dynamic resolution today when the QA is not
     rank-1).
   - `except DynamicResolutionError as exc:` → `AIGeneration(status="ABSTAIN",
     abstention_reason="DYNAMIC_DATA_UNAVAILABLE", draft_text="",
     provider="dynamic-pattern-resolver", model="not-applicable",
     trigger="MANUAL_BOOKING_OFFER", retrieval_run_id=run.id,
     operator_id=operator_id)`.
5. `generation.category_slug = derive_category_slug(session, generation)`
   after the source flush (same ordering `generate_draft` uses).
6. Events: `ai.draft_generated` / `ai.draft_abstained` (payload
   `trigger="MANUAL_BOOKING_OFFER"`), plus `ai.dynamic_pattern_resolved`
   with `{specialty_slug, slot_count}` on success or
   `ai.dynamic_pattern_fallback` with `{cause}` on abstain — the exact
   events `generate_draft`'s dynamic branch emits, so metrics/timeline
   stay uniform.
7. On any unexpected `Exception`: persist a `status="FAILED"` generation
   (same shape as `generate_draft`'s `except`) and raise
   `503 AI_PROVIDER_UNAVAILABLE`.

### 4.2 New endpoint, `ai/router.py`

```python
class BookingOfferDraftIn(BaseModel):
    manual_search_text: str = ""

@router.post("/operator/conversations/{conversation_id}/booking-offer-draft", status_code=201)
def booking_offer_draft(conversation_id, payload, operator, session) -> dict:
    conversation = session.get(Conversation, conversation_id)
    if not conversation or assigned_operator_id(session, conversation_id) != operator.id:
        raise api_error(403, "FORBIDDEN", "Conversation is not assigned to this operator")
    generation, evidence = generate_booking_offer_draft(session, operator.id, conversation, payload.manual_search_text.strip())
    return generation_dict(session, generation, evidence)
```

Returns the same `generation_dict` shape `draft()` / `select_evidence()`
return, so the frontend draft panel renders it with no new component.

### 4.3 Autonomy safety (OB-3)

`maybe_open_autonomous_window()` early-returns unless `generation.trigger
== "AUTOMATIC"` or `generation.trigger in _N5_ELIGIBLE_GB_TRIGGERS`.
`"MANUAL_BOOKING_OFFER"` is neither, so no `PendingAutonomousSend` row is
ever opened for an OB generation — no code change to that function is
needed. A negative test (`spec.md` acceptance #9) pins this: OB call with
both kill switches on and `autonomy_window_seconds=0` produces zero
`pending_autonomous_sends` rows and zero customer-visible messages.

### 4.4 Frontend (OB-4)

`frontend/src/main.tsx`, the **operator** conversation panel only (the
`selected.status === "ACTIVE"` block, ~L813-821 — *not* the customer
widget's own Enviar/Encerrar pair ~L412-426; `spec.md` OB-4's "both
occurrences" is corrected here to the single operator panel):

```tsx
    </form>
    <button type="button" className="btn-secondary"
      disabled={!aiEligible}
      onClick={() => void generateBookingOffer().catch((c) => setError(errorMessage(c)))}>
      Gerar oferta de agendamento
    </button>
    {confirmingClose ? <CloseConfirmPrompt .../> : <button ...>Encerrar conversa</button>}
```

- `generateBookingOffer()` = a new async fn next to `generate()`: `POST`
  to the new endpoint with `{ manual_search_text: searchQuery.trim() }`
  (reuses the existing manual-search input's value if present, else
  empty), then `setDraft(data)` + `refreshSelected()` exactly as
  `generate()` does. No new state.
- `aiEligible` is the existing gate (`selected?.status === "ACTIVE" &&
  selected?.effective_mode === "N2"` and claimed) — identical enablement
  to "Gerar rascunho".
- **Resolves spec.md §10 Q5**: the button is *disabled* (not hidden) when
  there is no customer message yet — consistent with how "Gerar rascunho"
  behaves; a distinct hidden/shown rule for this one button would be
  surprising.
- The resulting draft (ANSWER offer block, or ABSTAIN "sem agenda")
  renders in the existing `.draft-panel` in the `<aside>`; the operator
  sends it with the ordinary "Usar sugestão" → "Enviar", or "Aprovar"
  (quick-approve) — all existing, unchanged.

## 5. Data model changes

See `data-model.md`. Summary: one `system_settings` column
(`availability_floor_checked_at timestamptz NULL`), one
`ai_generations.trigger` CHECK widening for `'MANUAL_BOOKING_OFFER'`, two
new audit event types. No new tables.

## 6. Test plan

### Backend unit / integration (`app/tests/`)

- `test_availability_continuity.py` (new):
  - bootstrap: empty → seeded (wide + generalist D1/D7 present); re-run
    creates 0 rows, no second "created" event.
  - `ensure_generalist_floor`: D1 reduced to `<= AC_FLOOR_MIN` → one call
    restores to `AC_FLOOR_TARGET`, one `scheduling.availability_floor_topped_up`
    event; above floor → no rows, no event.
  - debounce: two calls within `AC_FLOOR_CHECK_INTERVAL_SECONDS` →
    counting query runs at most once (`availability_floor_checked_at`
    moves once; assert via a spy or a monkeypatched counter).
  - concurrency: two `ensure_generalist_floor` calls (separate sessions)
    never exceed `AC_FLOOR_TARGET` (advisory-lock test, mirrors
    `test_appointment_seeding.py`'s own).
  - query-independence: a customer booking message against an empty
    agenda still `ABSTAIN`s and (with N5 on) still produces a
    `generate_ungoverned_reply()` — and **no** slot row is created by
    that path (the negative test for `specs/004` clarification 6).
- `test_booking_offer_draft.py` (new):
  - happy path: `MANUAL_BOOKING_OFFER` `AIGeneration` `status=ANSWER` +
    `appointment_offer_presentations` rows; a subsequent `"opção 2"`
    customer reply resolves through `interpret_slot_choice()` unchanged.
  - `manual_search_text="mastologia amanhã de manhã"` narrows the offer
    set to that specialty/day/period.
  - empty agenda → `status=ABSTAIN` / `DYNAMIC_DATA_UNAVAILABLE`, no
    customer message.
  - **never autonomous**: both kill switches on, `window_seconds=0` → no
    `pending_autonomous_sends` row, no `messages` row with
    `author_type='OPERATOR'` (Article X negative test).
  - auth: unauthenticated → 401/403; authenticated-but-not-assigned →
    `403 FORBIDDEN`; `CLOSED` conversation → `409`.
- `test_012_containment.py` (new, AST-based, same technique as
  `test_010_governed_autonomy_containment.py`): the string
  `"MANUAL_BOOKING_OFFER"` is constructed in exactly one place
  (`generate_booking_offer_draft`); `maybe_open_autonomous_window`'s
  eligibility set is unchanged; `ensure_generalist_floor` /
  `run_bootstrap_seed` are never imported by `ai/router.py`,
  `anonymous_access/router.py`, or `scheduling/availability.py` (the
  query/resolver modules).

### API (`app/tests/` OpenAPI)

- `contracts/openapi.yaml`'s new path present, matches the endpoint's
  actual request/response schema, 201/403/409/503 documented.

### Frontend (`frontend/src/main.test.tsx`)

- the "Gerar oferta de agendamento" button renders between the operator
  reply form and "Encerrar conversa"; disabled on CLOSED/unclaimed/non-N2;
  on click calls the endpoint and populates the draft panel; sends
  nothing on its own.

### E2E (`frontend/e2e/v12.spec.ts`, new)

- operator opens a claimed conversation whose customer asked to book,
  clicks "Gerar oferta de agendamento", sees the offer block in the draft
  panel, sends it, customer replies "opção 1", booking flow proceeds.

### Regression

- Full backend `pytest`, full smoke suite, full Playwright suite re-run
  (not assumed) — `test_appointment_seeding.py`,
  `test_booking_script_containment.py`,
  `test_010_governed_autonomy_containment.py`,
  `test_ungoverned_n5.py` unchanged and green. Note the known
  `test_appointment_seeding.py` / shared-dev-DB `n5_kill_switch_enabled`
  isolation traps from `CLAUDE.md` — clear/restore around those files.

## 7. Rollout / ordering

1. Migrations (T1-T2) + ORM (T3).
2. AC: `seeding.py` functions (T4-T5), `bootstrap_seed.py` (T6),
   `list_conversations` hook (T7), compose command (T8).
3. OB: `generate_booking_offer_draft` + endpoint (T9-T10), trigger CHECK
   already widened in T1.
4. Frontend button (T11).
5. Tests (T12-T17).
6. `EVENT_CATALOG.md`, `specs/004` forward pointer, `analysis.md`
   convergence review, `acceptance.md`, `DECISIONS.md` D-044 status,
   `ROADMAP.md`, `CLAUDE.md`, `PROJECT_STATE.md` (T18-T20).

## 8. Risks

- **Bootstrap wide seed cost at every container start.** The wide seeder
  iterates every business day to `WIDE_SEED_END_DATE` × every specialty,
  even when all inserts are no-ops. Acceptable for a demo container that
  starts rarely; if it measurably slows startup, add the short-circuit
  noted in §2.2. Not a correctness risk (idempotent).
- **`ensure_generalist_floor` on a hot poll path.** Mitigated by the
  60 s timestamp gate (a plain column read) before any slot COUNT, and by
  the swallow-all `except`. Worst case on failure: the agenda is not
  topped up this minute and the resolver may `ABSTAIN` for one customer
  (→ N5 covers it, exactly as today) until the next successful poll.
- **`specs/004` AA-9 supersession.** Narrow and one-directional (more
  write entry points, all still non-query). Documented in `analysis.md`
  and a `specs/004/spec.md` forward pointer; `DECISIONS.md` D-044 is the
  authority. If a future reviewer reads AA-9 in isolation they must see
  the pointer — hence the forward link is mandatory, not optional.
- **OB query text pulling a stray specialty keyword** from a long
  trailing customer message. Low impact (wrong specialty's real slots,
  still a valid simulated offer the operator reviews before sending) and
  the operator can override with `manual_search_text`. Not worth
  constraining further in v1.
