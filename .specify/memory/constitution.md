# Customer Care AI Constitution

Version: 1.1.0
Ratified: 2026-08-10
Amended: 2026-08-18 (Amendment 1.1.0 — narrow exception to Article III)

## I. Specification precedes implementation

No new product behavior is implemented before it is represented in the active feature specification. If implementation reveals a required behavioral change, update the spec/plan/tasks before continuing.

## II. V1 scope discipline

The currently authorized V1 includes N1/N2 only. N3, N4, supervisor, manager, AI Ops, Telegram, persisted customer identity, dynamic ETA, and automatic autonomy downgrade are forbidden unless required only as low-cost extension points with no V1 behavior.

## III. Human authority over V1 outbound AI

AI generations are internal artifacts. In V1, only an authenticated operator action may create a customer-visible operator message from an AI draft. No provider callback, background job, frontend shortcut, or API route may bypass this rule.

**Narrow exception (Amendment 1.1.0, human decision 2026-08-18):** the
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
