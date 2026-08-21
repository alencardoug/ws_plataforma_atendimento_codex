# Customer Care AI Constitution

Version: 1.2.0
Ratified: 2026-08-10
Amended: 2026-08-18 (Amendment 1.1.0 — narrow exception to Article III);
2026-08-20 (Amendment 1.2.0 — governed autonomous send, N3/N4)

## I. Specification precedes implementation

No new product behavior is implemented before it is represented in the active feature specification. If implementation reveals a required behavioral change, update the spec/plan/tasks before continuing.

## II. V1 scope discipline

The currently authorized V1 includes N1/N2 only. Supervisor, manager, AI Ops, Telegram, persisted customer identity, dynamic ETA, and automatic autonomy downgrade remain forbidden unless required only as low-cost extension points with no V1 behavior. **N3 and N4 are authorized as of Amendment 1.2.0 (human decision 2026-08-20), strictly bounded by Article III's governed-autonomy exception below** — no other N3/N4 behavior described in `ROADMAP.md`'s original bullets (e.g. immediate/non-veto-windowed autonomous send) is authorized by this amendment.

## III. Human authority over V1 outbound AI

AI generations are internal artifacts. In V1, only an authenticated operator action may create a customer-visible operator message from an AI draft. No provider callback, background job, frontend shortcut, or API route may bypass this rule.

**Governed-autonomy exception (Amendment 1.2.0, human decision
2026-08-20):** an LLM-generated draft may be sent to the customer without
a per-message operator click, strictly limited to:

(a) the draft's generation must have `status=ANSWER` with real retrieved
    evidence — an `ABSTAIN` (including `DYNAMIC_DATA_UNAVAILABLE`,
    `INSUFFICIENT_EVIDENCE`, or any other reason code) may never be sent
    autonomously; it always falls back to the ordinary N2 manual queue;
(b) the draft must originate from the existing automatic-draft-trigger
    debounce (V2-7/V3-9's `evaluate_automatic_trigger`) — a manually
    requested draft ("Gerar rascunho") is never eligible for autonomous
    send, regardless of category policy;
(c) the draft's evidence category must be governed by an explicit,
    per-category autonomy policy (ON/OFF) that a human operator set —
    default OFF; no category is autonomous until explicitly turned on;
(d) every eligible draft opens a veto window whose duration is a single
    system-wide value (never per-category), operator-configurable through
    the frontend, ranging from 0 seconds (immediate send, no wait) up to
    an operator-chosen duration. While the window is open (duration > 0),
    any operator may PAUSE (cancel this specific autonomous send; the
    draft becomes an ordinary N2 draft awaiting manual send; the
    category's policy is unaffected), EDIT (compose and send manually,
    replacing the autonomous path for this message), or TAKE OVER
    (existing V1 mechanism — switches the conversation to N1, disabling
    AI for it entirely) — all three remain fully implemented server-side
    at every duration setting, including 0; at 0 seconds there is no
    window for an operator to act within, so in practice the frontend
    need not surface them as live actions for that message, but the
    mechanisms themselves are never removed or bypassed in the backend.
    If the window elapses (immediately, at 0) with no operator action,
    the draft sends automatically — the category's own ON policy is the
    standing authorization for that silence or immediacy, not a separate
    per-message approval;
(e) a single global kill switch (independent of any per-category policy)
    must exist; when off, the entire system behaves as pure N2 — no
    message ever sends without an explicit operator click, regardless of
    any category's own ON/OFF state;
(f) every category policy change is an authenticated operator action,
    recorded as an immutable audit event (Article IX) with operator
    identity, timestamp, category, and the before/after policy value;
(g) this exception does not authorize any new persisted customer
    identity, real payment, or real booking behavior — those remain
    governed by their own existing constraints (Article VI, the
    dynamic-appointment-availability package's own scope limits) unchanged
    by this amendment;
(h) this exception does not extend to any other outbound message path in
    the system beyond what (a)-(g) describe, and does not by itself
    authorize a `supervisor`/`manager` role, Telegram, or any other item
    Article II still forbids.

This exception is independent of, and does not narrow or widen, Amendment
1.1.0's own narrow exception for the dynamic-appointment-availability
booking script — that script's fixed-template, non-LLM autonomous sends
remain governed entirely by their own original terms.

**Prior narrow exception (Amendment 1.1.0, human decision 2026-08-18):** the
simulated identity/payment-confirmation script belonging to the
dynamic-appointment-availability feature
(`specs/004-dynamic-appointment-availability/`) may send its messages to
the customer automatically, without a per-message operator click, strictly
limited to:

(a) messages drawn from a fixed, human-authored template set for that one
    script only — never LLM-composed, never LLM-rewritten;
(b) the CPF-format-only validation and sim/não interpretation steps of
    that one specific flow;
(c) no real booking, payment, or identity persistence — remains a
    synthetic simulation only (Article VI unchanged); the underlying
    appointment-booking feature (D-026) remains separately deferred.

This exception does not extend to any other outbound message in the
system, does not authorize LLM-generated autonomous send, and does not by
itself authorize real booking/payment/identity behavior. Every other
outbound path in the system remains governed by this article's original
rule without exception.

## IV. Manual service survives AI failure

AI and RAG are assistive in V1. Provider failure, insufficient evidence, or retrieval failure must degrade to manual operator service rather than fail the conversation lifecycle.

## V. Grounding and traceability

Every AI draft must be attributable to:

- triggering customer message;
- prompt version;
- generation model/configuration;
- retrieval run;
- retrieved knowledge evidence;
- timestamps/latency and usage metadata when available.

No hidden model reasoning is persisted.

## VI. Data minimization

V1 uses synthetic/demo data only. Anonymous customers have no persisted person/profile identity. Conversation content is treated as potentially sensitive and excluded from ordinary INFO logs.

## VII. Security at boundaries

Authentication, authorization, conversation token scope, citation exposure, and outbound-send authority are enforced server-side. UI state is never trusted as an authorization mechanism.

## VIII. Modular monolith first

Prefer explicit modules, ports, and application services inside one backend deployment. Distributed infrastructure is prohibited until a measured requirement justifies it.

## IX. Durable facts enable future governance

Persist normal transactional state relationally and record critical operational facts as immutable audit events. Do not adopt event sourcing or streaming infrastructure solely for future analytics.

## X. Test critical invariants negatively

For every safety boundary, include a test proving forbidden behavior fails. In particular, direct AI-to-customer send, citation leakage, cross-conversation anonymous access, and capacity overflow must have negative tests.

## XI. Autonomy only decreases automatically

Future versions may automatically reduce autonomy when evidence degrades. No future feature may automatically increase autonomy without explicit human governance approval.

## XII. Future-readiness without speculative implementation

Model boundaries that would be expensive to reverse (channel-neutral conversation core, AI provider port, knowledge type/source exposure, audit event identifiers) are designed now. Future product features are not implemented until their own specification is authorized.
