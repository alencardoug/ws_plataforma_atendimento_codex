# Feature Specification: Governed Autonomous Response (N3/N4)

## 1. Purpose

Introduce the system's first mechanism by which an LLM-generated draft can
reach the customer without a per-message operator click, strictly within
the bounds Constitution Amendment 1.2.0 (`.specify/memory/constitution.md`
Article III) authorizes. This is the merged delivery of `ROADMAP.md`'s V4
("N3 governed autonomy / Supervisor") and V9 ("N4 HOTL") entries, built as
one unified mechanism rather than two — see §9 for why the human decided
against building them as separate maturity levels.

## 2. Definitions

- **Category autonomy policy** — a per-content-category ON/OFF flag
  (default OFF) that a human operator sets. Only evidence whose category
  is ON is eligible for governed autonomous send.
- **Veto window** — the period between an eligible draft being generated
  and it being sent to the customer. Its duration is a single system-wide
  value, operator-configurable through the frontend, from 0 seconds
  (immediate send) upward. It is never configured per category.
- **PAUSE** — an operator action during an open window that cancels this
  one autonomous send; the draft becomes an ordinary N2 draft awaiting
  manual send. The category's own policy is unaffected — the *next*
  eligible message in that category is still autonomous.
- **EDIT** — an operator action during an open window that lets the
  operator compose and manually send a reply, replacing the autonomous
  path for this one message.
- **TAKE OVER** — the existing V1 mechanism (`Assumir controle`):
  switches the conversation to N1, disabling AI (and therefore autonomy)
  for it entirely, for the rest of the conversation.
- **Kill switch** — a single global toggle, independent of any category's
  own policy. When off, the entire system behaves as pure N2: no message
  ever sends without an explicit operator click, regardless of any
  category's ON/OFF state.
- **Governed autonomous send** — the act of a draft reaching the customer
  because its window elapsed with no operator action. The category's own
  ON policy is the standing authorization for that silence or immediacy;
  there is no separate per-message approval step.

## 3. Functional requirements (GA)

### GA-1 — Category autonomy policy: data, defaults, who sets it

- `content.categories` gains an `autonomy_enabled boolean not null default
  false` column (matches this project's existing precedent of adding a
  narrow, targeted column rather than a separate polymorphic policy
  table — e.g. `conversations.guided_booking_selected_offer_id`,
  007/D-037).
- Any authenticated operator may toggle any category's policy — there is
  no `supervisor`/`manager` role (Constitution Article II/III explicitly
  do not authorize one via this amendment; human decision, §9).
- All categories are eligible for the policy from day one, including
  clinical ones. There is no restricted low-risk pilot subset (human
  decision, §9) — the policy itself, not category type, is what an
  operator uses to control risk.
- Every toggle is a new `POST /operator/knowledge/categories/{slug}/autonomy`
  (or equivalent) call, recorded as an `audit_events` row
  (`autonomy.category_policy_changed`) with operator identity, timestamp,
  category slug, and the before/after boolean.

### GA-2 — Evidence/trigger gate (non-negotiable, Constitution (a)/(b))

- A generation is eligible for governed autonomous send only if:
  - `status == 'ANSWER'` with real retrieved evidence — any `ABSTAIN`
    (`INSUFFICIENT_EVIDENCE`, `DYNAMIC_DATA_UNAVAILABLE`, or any other
    reason code) is never eligible; it falls back to the ordinary N2
    manual queue exactly as it does today;
  - `trigger == 'AUTOMATIC'` — i.e. it originated from the existing
    automatic-draft-trigger debounce (`evaluate_automatic_trigger()`,
    V2-7/V3-9). A manually requested draft ("Gerar rascunho") is never
    eligible, regardless of category policy;
  - the generation's rank-1 evidence's category has `autonomy_enabled =
    true` at the moment the generation completes;
  - the global kill switch is on.
- This evaluation happens once, at the moment `evaluate_automatic_trigger()`
  would otherwise just leave the draft sitting for an operator to see. If
  eligible, a `PendingAutonomousSend` row is created instead (GA-3); if
  not, behavior is unchanged from today (008's `preparing_response` cue,
  operator's own countdown, etc. all still apply as before this cycle).

### GA-3 — The veto window itself

- New table `customer_service.pending_autonomous_sends` (elaborated in
  `data-model.md`): one row per eligible generation, `status` in
  `PENDING` / `SENT` / `PAUSED` / `EDITED` / `TAKEN_OVER`, `opens_at`,
  `window_seconds` (captured at creation time — a later change to the
  global setting never retroactively changes an already-open window),
  `resolves_at = opens_at + window_seconds`, `resolved_at`,
  `resolved_by_operator_id` (`NULL` for an autonomous auto-send —
  nothing "resolved" it, the window's own elapse did).
- A background-evaluated resolution (same lazy-evaluation-on-poll pattern
  this project already uses for `evaluate_automatic_trigger()` itself,
  not a scheduler/cron — Constitution Article VIII, no new distributed
  infrastructure) sends the message once `now() >= resolves_at` and the
  row is still `PENDING`.
- The sent message's `autonomous_source` (existing column, currently only
  ever `'booking_script'` for AA-10) is set to `'governed_autonomy'` for
  this path — reusing the exact mechanism and the frontend's existing
  "automático" badge (`frontend/src/main.tsx`'s
  `message.autonomous_source === "booking_script" && <span
  className="badge" ...>` block generalizes to check either value), not
  inventing a new transparency mechanism.
- `window_seconds` itself is a single global, operator-configurable
  value (`customer_service.system_settings` or equivalent single-row
  table — elaborated in `data-model.md`), settable from the frontend,
  and may be set to 0. At 0, `resolves_at == opens_at`: there is no
  practical window for PAUSE/EDIT/TAKE OVER to be exercised in, so the
  frontend need not render them as live actions for that specific
  message — but the three mechanisms themselves (GA-4) remain fully
  implemented server-side at every duration, including 0, per
  Constitution (d).

### GA-4 — PAUSE / EDIT / TAKE OVER

- **PAUSE**: `POST /operator/conversations/{id}/pending-autonomous-send/{id}/pause`.
  Sets the row's `status = 'PAUSED'`, `resolved_by_operator_id`. The
  generation becomes an ordinary visible draft (exactly like any other
  `AUTOMATIC`-trigger draft today) awaiting a normal manual send. The
  category's own `autonomy_enabled` flag is untouched — the next eligible
  message in that category still opens its own window.
- **EDIT**: the operator uses the existing reply textarea/send flow.
  Sending manually while a `PENDING` row exists for that conversation
  implicitly resolves it to `status = 'EDITED'` (no separate "cancel"
  click required first — matches this project's existing pattern where
  `latest_sent_generation_trigger()`-style checks already infer state
  from what was actually sent, not from an explicit intermediate step).
- **TAKE OVER**: the existing `POST /operator/conversations/{id}/take-over`
  endpoint. If a `PENDING` row exists for the conversation at that
  moment, it resolves to `status = 'TAKEN_OVER'` and never sends. No new
  endpoint — this reuses V1's mechanism unchanged; the only new behavior
  is resolving any pending row as a side effect.
- All three actions are available to **any** authenticated operator, not
  only one who has claimed the conversation — necessary because GA-6
  allows autonomy on unclaimed (`WAITING`) conversations, which by
  definition have no assigned operator yet.

### GA-5 — Kill switch

- A single boolean, `customer_service.system_settings.autonomy_kill_switch_enabled`
  (or equivalent — same settings table as `window_seconds`), independent
  of any category's own policy.
- When off (the default — autonomy is opt-in at every level, matching
  every category's own `autonomy_enabled = false` default), GA-2's
  eligibility check always fails: the system behaves as pure N2, with
  zero code-path difference from before this cycle for any conversation.
- Settable from the frontend by any authenticated operator; every change
  is an `audit_events` row (`autonomy.kill_switch_toggled`).

### GA-6 — Eligibility on unclaimed ("Aguardando") conversations

- Human decision (§9): governed autonomy is **not** limited to
  already-claimed conversations. `evaluate_automatic_trigger()`'s own
  existing eligibility check (an uncovered customer message, no other
  precondition about assignment) already runs independent of claim
  status for the *automatic-draft* mechanism today (an unclaimed
  conversation can already accumulate an internal automatic draft no
  operator has seen); GA-2's eligibility check layers directly on top of
  that existing behavior, unchanged.
- An autonomously-sent message on an unclaimed conversation does **not**
  change `conversations.status` — it stays `WAITING`, exactly as it was
  before the send, and remains fully claimable by any operator afterward.
  Claim/take-over remain the only two actions that change `status` to
  `ACTIVE` (unchanged from V1).
- An unclaimed conversation with a pending or already-resolved autonomous
  send does **not** count toward any operator's
  `OPERATOR_MAX_ACTIVE_CONVERSATIONS` capacity — capacity is about a
  human's assigned workload, and no human is assigned yet. This is a
  resolved-by-inspection consequence of GA-6's own premise, not a
  separate ask, but is stated explicitly here since it is a genuine,
  observable change in what "waiting" can mean (a waiting conversation
  may now already have one or more customer-visible answers in it).

### GA-7 — Customer-facing behavior

- The customer sees no distinction between an autonomously-sent message
  and an operator-sent one beyond what already exists — no new UI signal
  is added to the customer's own page by this cycle. `008`'s
  `preparing_response` cue continues to apply identically (it already
  reflects `automatic_draft_status()`'s existing eligibility computation,
  which this cycle does not change).
- No new customer-facing endpoint, field, or copy. This keeps the
  customer-side safety surface (008/009's own recent closure work)
  entirely unmodified by this cycle.

## 4. What this cycle does **not** authorize

- Any `supervisor`/`manager` role or interface — human decision,
  simplified away (§9). Every "operator" action in this spec means the
  existing `operator_users` role.
- Any autonomous send that is not gated by GA-2's evidence/trigger checks
  — in particular, a manually requested draft is never autonomous, and an
  `ABSTAIN` is never autonomous, at any window duration including 0.
- Any change to real booking, payment, or identity persistence — those
  remain governed entirely by their own existing constraints, unchanged.
- Telegram, dynamic ETA, persisted customer continuity, or any other item
  Constitution Article II still forbids.
- Automatic autonomy *increase* of any kind beyond what a human operator
  explicitly sets via GA-1/GA-5's own toggles — Article XI (autonomy only
  decreases automatically) is unaffected by this cycle; V8's own future
  "automatic safety downgrade" remains separate, later work.
- V5's "call-center specialist escalation" — a separate, later roadmap
  item, not part of N3/N4.

## 5. Data model impact (elaborated in `data-model.md`)

- `content.categories`: new `autonomy_enabled boolean not null default
  false` column.
- New `customer_service.pending_autonomous_sends` table (GA-3).
- New `customer_service.system_settings` (or equivalent) single-row
  table: `window_seconds integer not null default <TBD in plan.md>`,
  `autonomy_kill_switch_enabled boolean not null default false`.
- `customer_service.messages.autonomous_source`: existing column gains a
  new allowed value, `'governed_autonomy'`, alongside the existing
  `'booking_script'`.
- New `audit_events` event types: `autonomy.category_policy_changed`,
  `autonomy.kill_switch_toggled`, `autonomy.window_duration_changed`.
- `customer_service.ai_generations.operator_id`: existing `NOT NULL` FK
  becomes nullable — GA-6's unclaimed-conversation path has no operator
  to attribute a generation to (resolved by direct inspection during
  planning; see `plan.md` §2 for the exact call-site scoping that keeps
  every other caller's non-null guarantee intact).
- No change to `ai_generations.trigger`'s existing CHECK constraint — a
  governed-autonomous generation's own `trigger` value stays `'AUTOMATIC'`,
  matching GA-2's own gate; the new lifecycle (pending/sent/paused/
  edited/taken-over) lives entirely in the new `pending_autonomous_sends`
  table, not as new trigger values, keeping this project's existing
  "per-value-means-one-thing" trigger convention intact (D-035).

## 6. Acceptance outcomes to develop into executable tests

1. A category with `autonomy_enabled=false` (the default) never opens a
   window for any generation, at any window-duration setting, with the
   kill switch on — behavior is byte-for-byte identical to pre-cycle N2.
2. An `ABSTAIN` generation (any reason code) in an `autonomy_enabled=true`
   category never opens a window.
3. A manually requested draft ("Gerar rascunho") in an
   `autonomy_enabled=true` category never opens a window, even when its
   own evidence/status would otherwise qualify.
4. An eligible `AUTOMATIC`-trigger `ANSWER` in an `autonomy_enabled=true`
   category, kill switch on, window > 0: opens a `PENDING` row; PAUSE
   converts it to an ordinary awaiting-send draft without touching the
   category's own policy; a second eligible message in the same category
   still opens its own window afterward.
5. Same setup, EDIT: operator sends manually; the row resolves to
   `EDITED`; no autonomous send occurs for that message.
6. Same setup, TAKE OVER: the row resolves to `TAKEN_OVER`; the
   conversation is now N1; no further autonomous sends occur in it.
7. Same setup, no operator action: at `resolves_at`, the message sends
   automatically; `autonomous_source='governed_autonomy'`; the existing
   "automático" badge renders on the operator's transcript.
8. Window duration = 0: the row resolves to `SENT` with no observable
   gap for an operator to act within; PAUSE/EDIT/TAKE OVER still succeed
   if attempted in the same instant (server-side check, not a UI-only
   guard) but the frontend does not need to surface them as live options
   for that message.
9. Kill switch off: no eligibility check ever passes, regardless of any
   category's own `autonomy_enabled` value.
10. An eligible message on a `WAITING` (unclaimed) conversation: sends
    autonomously without any operator having claimed it;
    `conversations.status` remains `WAITING` afterward; the conversation
    does not count toward any operator's active-conversation capacity;
    any operator can still claim it normally afterward.
11. Every category-policy toggle, kill-switch toggle, and window-duration
    change produces exactly one `audit_events` row with operator
    identity, timestamp, and the before/after value.
12. Full pre-existing suite (V1-V3, 004-009) unmodified elsewhere still
    passes — this cycle adds a new gate in front of an existing code
    path (`evaluate_automatic_trigger()`'s own output) and must not
    change that path's behavior for any conversation whose category
    policy is off or whose kill switch is off.

## 7. Decisions resolved with the human (2026-08-20, grill session)

Per `docs/sdd/GRILL_GATE.md`, conducted because `ROADMAP.md`'s V4/V9
bullets left architecture, safety mechanism, and constitutional scope
entirely undefined — the remaining uncertainty was too large to write
deterministic acceptance criteria without it. Full rationale is in D-041
(`DECISIONS.md`); summarized inline here for spec-local traceability:

- N3 and N4 are one mechanism, not two maturity levels — every autonomous
  send goes through a veto window (possibly 0-length), so there is no
  separate "N3 = immediate" path distinct from "N4 = windowed" as the
  original roadmap bullets implied.
- The window's duration is a single global, frontend-configurable value
  (never per-category), explicitly allowed to be 0 (immediate send) —
  this was a deliberate widening the human made mid-grill after initially
  ruling out any immediate-send path entirely; PAUSE/EDIT/TAKE OVER stay
  fully implemented server-side regardless of the configured duration.
- Evidence/trigger gating (GA-2) is non-negotiable: only real `ANSWER`
  evidence from the existing automatic-trigger path is ever eligible.
- No new `supervisor` role — ordinary operators manage policy.
- All categories eligible from day one — no restricted pilot.
- Autonomy applies even to unclaimed conversations — a real, deliberate
  change to what "waiting" can mean, not just "skip the send click"
  within an already-claimed conversation.
- A global kill switch is mandatory, independent of category policy.
- Frontend scope (what the actual screens look like) was explicitly left
  to implementation-time judgment ("faça o que achar melhor") rather than
  grilled further — `plan.md` resolves the concrete UI.
