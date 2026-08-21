# Implementation Plan: Governed Autonomous Response (N3/N4)

## 1. Technical summary

Layer a new eligibility gate and a new pending-send lifecycle on top of
the existing automatic-draft-trigger mechanism, without modifying that
mechanism's own behavior for any conversation whose category policy is
off. One genuinely new code path is required for GA-6 (unclaimed
conversations) — see §2.

## 2. A necessary elaboration spec.md leaves to this plan: unclaimed-conversation generation

Direct inspection of `app/customer_care/ai/router.py` found two guards
that block GA-6 as written, neither mentioned in `spec.md` because the
spec was written against the roadmap's intent, not the code:

- `evaluate_automatic_trigger()` (line ~496) returns immediately unless
  `conversation.status == "ACTIVE"`, and again (line ~505-507) unless an
  operator is currently assigned (`assigned_operator_id()` non-`None`).
  Both are true by design for the existing N2 automatic-draft feature —
  neither is true for a `WAITING` conversation, which by definition has
  no assigned operator.
- `generate_draft()` (line ~269) itself independently raises
  `MODE_NOT_ALLOWED` unless `conversation.status == "ACTIVE"` — reusing
  it unmodified for `WAITING` conversations is not possible.
- `AIGeneration.operator_id` (`infrastructure/models.py` line ~214) is a
  non-nullable FK — there is no operator to attribute an
  unclaimed-conversation generation to.

Resolution (matching this project's own pattern of additive,
zero-regression-risk changes — e.g. 007's `guided_booking_selected_offer_id`):

1. **New function**, not a modified one: `evaluate_unclaimed_autonomous_trigger(session, conversation)`
   in `ai/router.py`, next to `evaluate_automatic_trigger()`. Mirrors its
   idle-timeout and uncovered-message logic exactly (same
   `AUTOMATIC_TRIGGER_IDLE_SECONDS`, same
   `auto_draft_covers_through_message_id` idempotency marker — commit
   before attempting generation, so concurrent evaluation from multiple
   operators' simultaneous queue polls stays safe by the same mechanism
   `evaluate_automatic_trigger()` already relies on), but requires
   `conversation.status == "WAITING"` instead of `"ACTIVE"`, and skips
   the assigned-operator check entirely. `evaluate_automatic_trigger()`
   itself is not touched — zero behavior change for any already-claimed
   conversation.
2. `generate_draft()` gains one new keyword-only parameter,
   `allow_unclaimed: bool = False`. When `True`, its guard becomes
   `conversation.status not in ("ACTIVE", "WAITING")` instead of
   `!= "ACTIVE"` (still rejects `CLOSED`); every existing call site keeps
   its default, so every existing caller's behavior is unchanged.
   `operator_id`'s type widens to `UUID | None`; only the new unclaimed
   path ever passes `None`.
3. **Migration**: `ai_generations.operator_id` becomes nullable. No CHECK
   constraint is added tying it to a specific trigger value — the
   invariant ("only the unclaimed-autonomous path ever produces
   `operator_id IS NULL`") is enforced by there being exactly one call
   site that passes `None`, documented inline at that call site, matching
   this project's existing preference for code-level invariants over
   defensive CHECK constraints where a single call site is the only
   producer (see `booking_script/service.py`'s own containment
   discipline).
4. `evaluate_unclaimed_autonomous_trigger()` is invoked once per
   `WAITING` conversation from `list_conversations()`
   (`operator_workspace/router.py` line ~90-104), the endpoint every
   logged-in operator's queue already polls every 2s — the same
   "lazily evaluated as a side effect of an existing poll" pattern
   `evaluate_automatic_trigger()` itself already uses at the
   conversation-detail level (V2-7/V3-9's own documented rationale: no
   scheduler, no background worker, Constitution Article VIII). Placed
   after the existing `waiting`/`active` query, before `summary()`
   construction, so a conversation that just became eligible is reflected
   in the very same response.

## 3. Category eligibility check (GA-2, GA-3)

New shared helper, `maybe_open_autonomous_window(session, generation, conversation)`
in `ai/router.py`, called from both `evaluate_automatic_trigger()` (added
as one line, right after its own successful `generate_draft()` call) and
`evaluate_unclaimed_autonomous_trigger()`:

```python
def maybe_open_autonomous_window(session, generation, conversation) -> None:
    if generation.status != "ANSWER":
        return
    top_evidence_category = ...  # rank-1 evidence's category slug, via existing evidence/retrieval_hits join
    settings = get_autonomy_settings(session)  # new table, §data-model.md
    if not settings.kill_switch_enabled:
        return
    if not category_autonomy_enabled(session, top_evidence_category):
        return
    session.add(PendingAutonomousSend(
        generation_id=generation.id, conversation_id=conversation.id,
        category=top_evidence_category, window_seconds=settings.window_seconds,
        opens_at=func.now(), status="PENDING",
    ))
    session.commit()
```

This is the single point where GA-1/GA-2/GA-5's checks compose — neither
trigger-evaluation function duplicates the category/kill-switch logic.

## 4. Resolving a pending row (GA-4)

- **Autonomous send** (window elapsed, no operator action): lazily
  evaluated the same way — a new
  `resolve_elapsed_autonomous_sends(session)` call, invoked once per
  `list_conversations()` poll (same call site as §2.4) and once per
  `operator_conversation_detail()` poll (existing per-conversation poll),
  covering both the queue-level and detail-level cases. Selects every
  `PENDING` row with `resolves_at <= now()`, sends via the existing
  `send message as operator` path but with `author_type="OPERATOR"`,
  `autonomous_source="governed_autonomy"`, `operator_id=None` (mirrors
  §2's `operator_id` nullability — no human operator is the source of an
  autonomous send even on an already-claimed conversation), sets the row
  `status="SENT"`, `resolved_at=now()`.
- **PAUSE**: `POST /operator/conversations/{id}/pending-autonomous-send/{pending_id}/pause`.
  Sets `status="PAUSED"`, `resolved_at`, `resolved_by_operator_id`. Does
  not touch `category.autonomy_enabled`.
- **EDIT**: no new endpoint. The existing manual-send endpoint
  (`POST /operator/conversations/{id}/messages`), on success, checks for
  a `PENDING` row on that conversation and resolves it to `status="EDITED"`
  as a side effect — mirrors how `guided_booking`'s own state already
  gets inferred from what was actually sent, not a separate intermediate
  step.
- **TAKE OVER**: the existing `POST /operator/conversations/{id}/take-over`
  endpoint, on success, resolves any `PENDING` row on that conversation
  to `status="TAKEN_OVER"` as a side effect. No new endpoint.

## 5. Frontend (delegated to implementation judgment per the human's own "faça o que achar melhor")

- **Queue item**: a `WAITING` or `ACTIVE` conversation with a `PENDING`
  row shows a countdown badge (mirrors the existing
  `automatic_draft_seconds_remaining` countdown pattern, V2-7/V3-9's own
  `Respondendo em Ns…`/`Gerando resposta…` text) — reusing that existing
  visual language rather than inventing a new one keeps this consistent
  with the operator's existing mental model.
- **Conversation view**: when a `PENDING` row exists for the open
  conversation, show the pending draft text (read-only preview, not the
  editable reply textarea — editing happens via the existing textarea
  itself per §4's EDIT semantics) plus three buttons: "Pausar",
  "Editar" (focuses the existing reply textarea, pre-filled with the
  pending draft text — reuses the existing "Usar sugestão" copy-into-textarea
  pattern), "Assumir controle" (the existing button, unchanged). At
  `window_seconds=0`, the row typically resolves to `SENT` before the
  operator's own poll ever observes it as `PENDING` — the three buttons
  simply have nothing to act on in that case, no special-casing needed in
  the component itself.
- **Autonomy settings panel**: a new section (queue sidebar, alongside
  the existing "Garantir disponibilidade"/"Preencher agenda ampla"
  buttons) with: a category list, each with an ON/OFF toggle
  (`GET`/`POST /operator/knowledge/categories/{slug}/autonomy`); a
  window-duration number input in seconds, including 0
  (`GET`/`POST /operator/autonomy-settings`); the kill switch as one
  prominent toggle, visually distinct (e.g. styled like the existing
  `alert`/error treatment) given its system-wide, immediate effect.
- **Badge**: generalize the existing `message.autonomous_source ===
  "booking_script"` check (`frontend/src/main.tsx`, queue-item and
  transcript rendering) to `message.autonomous_source != null`, with
  the title text reusing the existing wording pattern
  ("Enviada automaticamente...") but naming the actual source
  (`booking_script` → agendamento simulado; `governed_autonomy` →
  resposta autônoma governada) — one shared component, not two badges.

## 6. Test plan

- Backend: new `test_governed_autonomy.py` (real-DB integration style,
  matching `test_guided_booking.py`/`test_appointment_wide_seeding.py`'s
  own established pattern) covering every acceptance outcome in
  `spec.md` §6 directly against `maybe_open_autonomous_window()`,
  `resolve_elapsed_autonomous_sends()`, and the three resolution paths.
  Negative tests per Constitution Article X: kill-switch-off,
  category-off, ABSTAIN, and manual-trigger cases must all produce zero
  `pending_autonomous_sends` rows — each gets its own explicit test, not
  bundled into one large scenario.
- `smoke_v10_governed_autonomy.py`: real-provider HTTP smoke, covering
  the full lifecycle end-to-end including an unclaimed-conversation
  autonomous send (GA-6) and a window-elapses-and-sends case with a real
  (short, e.g. 2s) window against a real clock — not mocked.
- Frontend: `v10.spec.ts`, covering PAUSE/EDIT/TAKE OVER and the
  window=0 immediate-send case, following the deadlock-retry `psql()`
  pattern already established in `v7`/`v8`/`v9.spec.ts` (§ this
  session's own closure findings).

## 7. Risks

- **Capacity/queue-model change (GA-6)** is the largest behavioral
  change this cycle makes to existing V1 architecture — a `WAITING`
  conversation can now already contain a customer-visible answer before
  any operator ever sees it. Mitigated by: kill switch defaults off,
  every category defaults off, and GA-6 itself only ever fires through
  the same `ANSWER`-only gate as every other path.
- **`operator_id` nullability** touches a widely-read column (audit
  trails, "who generated this" attribution elsewhere). Mitigated by
  scoping the nullable case to exactly one new call site and leaving
  every existing caller's non-null guarantee intact by not changing
  their own code paths at all.
- **Two independent evaluation points for elapsed-window resolution**
  (queue poll and detail poll) could double-send if not idempotent — the
  `PENDING → SENT` status transition itself is the guard (an
  `UPDATE ... WHERE status='PENDING'` pattern, matching this project's
  existing `auto_draft_covers_through_message_id`-style idempotency
  discipline), not a separate lock.
