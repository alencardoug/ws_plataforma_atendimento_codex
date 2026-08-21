# Feature Specification: Ungoverned Fictional-Demo Autonomy (N5)

## 1. Purpose

This project is a technical-portfolio demonstration — a RAG/AI customer-care
architecture case study, not a real clinical institution. The human's goal
for this cycle is to demonstrate full, unconstrained autonomous AI-to-
customer response to interviewers/reviewers: every eligible customer
message gets an autonomous reply, including messages the existing
evidence-gated pipeline (N3/N4, `specs/010-governed-autonomous-response/`)
would otherwise leave to the manual N2 queue or `ABSTAIN` entirely.

This is authorized by Constitution Amendment 1.3.0
(`.specify/memory/constitution.md` Article III, "Ungoverned fictional-demo
exception"). That amendment's clause (e) makes the exception void without a
visible "this is a fictional technical demonstration" disclaimer on every
customer-facing entry point — implemented as a prerequisite to this spec,
before N5 itself, in `frontend/src/main.tsx`'s `.disclaimer-banner`
(customer landing page and operator login screen).

N5 is independent of, and does not replace, N3/N4 (feature 010). Both
mechanisms continue to exist; an operator chooses which is active via two
separate kill switches.

## 2. Definitions

- **N5**: the ungoverned autonomous-reply mode this spec authorizes. When
  its own kill switch is on, every AUTOMATIC-trigger-eligible customer
  message receives an autonomous reply regardless of retrieval outcome.
- **N5 kill switch**: `system_settings.n5_kill_switch_enabled` — a second,
  independent boolean alongside N3/N4's existing
  `autonomy_kill_switch_enabled`. Neither implies the other.
- **Ungoverned reply**: an LLM completion produced without requiring
  retrieval evidence, a matched category, or an `ANSWER` (vs. `ABSTAIN`)
  classification to authorize sending it to the customer. Retrieval is
  still attempted where the existing pipeline already attempts it (so
  Article V's traceability fields stay populated), but its outcome does
  not gate the send.
- **`automatic_trigger_idle_seconds`**: the renamed, now-configurable
  form of the existing fixed constant `AUTOMATIC_TRIGGER_IDLE_SECONDS`
  (`app/customer_care/ai/router.py`, currently `8`) — the idle-debounce
  period after the customer's last message/typing heartbeat before the
  automatic-trigger evaluation (shared by N3/N4 and N5) runs at all.

## 3. Functional requirements (N5)

### N5-1 — Independent kill switch

`system_settings` gains `n5_kill_switch_enabled boolean NOT NULL DEFAULT
false`. Default off, same as every other autonomy switch in this project.
Settable only via an authenticated operator action
(`POST /operator/autonomy-settings`, extended to accept this field
alongside the existing `window_seconds`/`kill_switch_enabled`), recorded as
an audit event with operator identity and before/after value (Article IX,
matching Amendment 1.3.0 clause matching 1.2.0(f)'s established pattern).

N5 being on has no bearing on N3/N4's own `autonomy_kill_switch_enabled` or
any category's `autonomy_enabled` policy, and vice versa. Both mechanisms
may be independently on, independently off, or any combination.

### N5-2 — Applies to every AUTOMATIC-eligible message, including ABSTAIN

When N5's kill switch is on, the automatic-trigger evaluation (the same
debounce entry point N3/N4 already uses,
`_uncovered_customer_run()`/`evaluate_automatic_trigger()`/
`evaluate_unclaimed_autonomous_trigger()`) always produces a customer-facing
autonomous reply once it fires — there is no category filter and no
`ABSTAIN` fallback under N5. Concretely:

- if the existing evidence-gated generation would produce `status=ANSWER`
  with a matched category, N5 does **not** override or duplicate it — that
  generation is used as-is (N5 adds coverage, it does not degrade an
  already-good grounded answer);
- if the existing generation would produce `status=ANSWER` with no matched
  category (an evidence-free reply, e.g. a greeting), or `status=ABSTAIN`
  (any reason code), N5 additionally invokes an ungoverned completion — a
  direct LLM call, given the conversation history and the customer's
  latest message, with **no** retrieval-evidence requirement and no
  `ABSTAIN` option available to the model — and that ungoverned reply is
  what gets sent autonomously in place of the manual-queue fallback N3/N4
  alone would have left.

This is additive coverage, not a replacement of the evidence-gated path:
whenever real evidence already produced a good grounded answer, that
answer is used; N5 only fills the gap N3/N4 alone leaves open.

### N5-3 — Reuses the existing veto window unchanged

N5-eligible messages open a `pending_autonomous_sends` row exactly like an
N3/N4-eligible one, using the same system-wide `autonomy_window_seconds`
value and the same PAUSE / EDIT / TAKE OVER resolution paths
(`specs/010-governed-autonomous-response/spec.md` GA-3/GA-4, unchanged). No
separate window/duration setting is introduced for N5.

### N5-4 — Distinct provenance, same audit/traceability discipline

Every N5 send is recorded with `autonomous_source='ungoverned_n5'` —
distinct from `'governed_autonomy'` (N3/N4) and `'booking_script'`
(AA-10) — both in the `messages` row and in the operator-facing badge
(distinct tooltip text, e.g. "Enviada automaticamente, sem evidência —
modo N5"). The underlying `ai_generations` row still records prompt
version, generation model/configuration, and timestamps per Article V;
when retrieval was attempted, the `retrieval_run` is still linked even
though it did not gate the send. No hidden model reasoning is persisted
(Article V, unchanged).

### N5-5 — `automatic_trigger_idle_seconds` becomes operator-configurable

`system_settings` gains `automatic_trigger_idle_seconds integer NOT NULL
DEFAULT 8` (matching the current hardcoded value — corrects the human's
recollection of "5 seconds"). `AUTOMATIC_TRIGGER_IDLE_SECONDS`'s two call
sites in `app/customer_care/ai/router.py` read this setting instead of the
module constant. Exposed via the same `/operator/autonomy-settings`
GET/POST pair and the same settings panel (Knowledge Management page) as
`window_seconds`. This setting is shared infrastructure — it affects when
the automatic trigger evaluates at all, for both N3/N4 and N5 alike; it is
not itself part of either autonomy mechanism's own gating logic.

### N5-6 — Disclaimer is a load-bearing precondition, not decoration

Per Amendment 1.3.0 clause (e), N5 must not be reachable if the
customer-facing disclaimer is absent. This spec does not add a runtime
check for this (the amendment's authority is the constitution text itself,
matching how Amendment 1.1.0/1.2.0's own clauses are enforced by
process/review, not a runtime assertion) — but `analysis.md` for this
package must explicitly confirm, by direct inspection, that the disclaimer
implemented ahead of this spec (`frontend/src/main.tsx`'s
`.disclaimer-banner` on both the customer landing page and operator login
screen) is still present at closure time.

## 4. What this cycle does **not** authorize

- Any weakening of N3/N4 (Amendment 1.2.0) when N5's own kill switch is
  off — 1.2.0(a)'s never-autonomous-on-`ABSTAIN` rule and 1.2.0(c)'s
  per-category policy gate remain exactly as strict as before in that
  state.
- Any weakening of Amendment 1.1.0's booking-script exception — untouched,
  zero coupling, verified the same way every prior cycle has verified it
  (`test_booking_script_containment.py`).
- Real patient/customer identity persistence, real payment, or real
  booking behavior (Article VI unchanged).
- Removing or softening the customer-facing/operator-login disclaimer —
  the opposite of this cycle's own precondition.
- A `supervisor`/`manager` role, Telegram, or any other item Article II
  still forbids.
- Deploying this project against real patient data — Article VI's
  synthetic-data-only rule is unaffected by this amendment; N5's relaxed
  evidence-gating is justified specifically by the fictional nature of the
  content, not by any change to what data the system is allowed to hold.

## 5. Data model impact (elaborated in `data-model.md`)

- `system_settings` gains two columns: `n5_kill_switch_enabled boolean NOT
  NULL DEFAULT false`, `automatic_trigger_idle_seconds integer NOT NULL
  DEFAULT 8`.
- `messages.autonomous_source`'s CHECK constraint (already widened once by
  feature 010 for `'governed_autonomy'`) widens again for `'ungoverned_n5'`.
  The second, independent `messages_check` constraint (found live during
  feature 010) needs the same widening — confirm during implementation
  whether it already covers this by pattern or needs its own migration.
- No new tables. N5 reuses `pending_autonomous_sends` as-is (no schema
  change to that table).

## 6. Acceptance outcomes to develop into executable tests

1. N5 off (default), N3/N4 off (default): a greeting or an uncovered
   question never sends autonomously — pure N2, unchanged from today.
2. N5 off, N3/N4 on with a matching category: existing feature-010 behavior
   is completely unaffected (regression check).
3. N5 on, N3/N4 off entirely (its kill switch off): an uncovered question
   (that would `ABSTAIN` under N3/N4) still gets an autonomous ungoverned
   reply, `autonomous_source='ungoverned_n5'`.
4. N5 on, category-matched `ANSWER` available: the grounded evidence-backed
   answer is sent (with its citations), not a redundant ungoverned
   duplicate — `autonomous_source` stays `'governed_autonomy'` for that one
   if N3/N4's own gate also independently allows it, or falls through to
   `'ungoverned_n5'` only if N3/N4's own category/kill-switch gate would
   have blocked it.
5. N5 on: PAUSE, EDIT, and TAKE OVER all still work on an N5-pending send,
   identically to an N3/N4-pending one.
6. N5 on, unclaimed ("Aguardando") conversation: autonomous ungoverned
   reply still sends without a claim, status stays `WAITING` (same
   guarantee as GA-6).
7. `automatic_trigger_idle_seconds` changed via the settings endpoint
   measurably changes when the automatic trigger fires (a real, not
   simulated, timing test).
8. Toggling N5's kill switch is an authenticated-only action and produces
   exactly one audit event with operator identity and before/after value.
9. Structural containment: exactly one additional non-operator-authenticated
   `Message`-construction call site is added for N5 (or the existing
   `autonomy/service.py` site is extended, not duplicated) — verified by
   the same AST-based technique as `test_booking_script_containment.py`/
   `test_010_governed_autonomy_containment.py`.
10. The customer-facing and operator-login disclaimers are still present
    (`analysis.md` confirms by direct inspection at closure).

## 7. Decisions resolved with the human (2026-08-21, grill session)

See `DECISIONS.md` D-042 for the full record. Summary: (1) N5 has its own
independent kill switch; (2) N5 reuses the existing veto-window mechanism
unchanged; (3) N5 applies to every AUTOMATIC-eligible message, explicitly
including overriding the `ABSTAIN`-never-autonomous rule while N5's own
kill switch is on; (4) N5 sends carry their own distinct
`autonomous_source` and operator-UI badge; (5, folded in from a related
ask) `automatic_trigger_idle_seconds` becomes operator-configurable
alongside `autonomy_window_seconds`.
