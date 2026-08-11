# Feature Specification: V2 Commercial Product Experience

**Feature ID:** `002-v2-commercial-product-experience`
**Status:** Discovery draft — clarification, planning, tasks, analysis, and
acceptance coverage required before implementation
**Authorized for specification:** 2026-08-11
**Scope:** V2 commercial experience only

## 1. Purpose

Evolve the completed V1 assisted-service baseline into a more professional and
usable commercial product experience without weakening the safety boundaries
that make V1 auditable: customer-token scope, operator authorization,
operator-controlled outbound send, evidence/source exposure policy, and manual
service fallback.

This draft records the V2 outcomes already approved by the human. Implement in
the normal SDD order only after the open decisions in section 7 are clarified
and the normal artifacts are complete.

## 2. Confirmed V2 outcomes

### V2-1 — Professional customer and operator UX

The customer and operator web interfaces need a professional, coherent, and
accessible visual/interaction design. The V2 plan must define the design system,
responsive behavior, empty/loading/error states, keyboard behavior, and the
acceptance evidence for the redesigned flows. This outcome does not by itself
authorize unrelated new business workflows.

### V2-2 — Customer-visible conversation token

The customer interface shall display the raw access token for that customer's
own active conversation and offer an explicit copy action. The token shall not
be put into a URL, ordinary logs, audit payloads, analytics, or another
conversation's UI. The backend continues to persist only its secure digest.

The V2 specification/plan must define safe copy feedback, reveal/masking
behavior, token lifetime/recovery semantics, and negative authorization/logging
tests. Displaying a token does not create a customer account or cross-session
recovery feature.

### V2-3 — Operator-selected manual evidence

Manual evidence search shall visibly use the query typed by the operator and
return inspectable administrative Q&A records and clinical child chunks. Each
returned item shall be selectable before draft generation.

For selected evidence:

- selecting a clinical child makes its complete parent document available for
  the normal explicit operator-send workflow;
- selecting administrative Q&A supplies its approved Q&A content to the LLM,
  which produces a concise answer focused on the customer's request rather than
  reproducing chunks, source labels, instructions, or retrieval metadata;
- the system records the selected evidence IDs, their source type, clinical
  parent expansion when used, generation provenance, and any final explicit
  operator send in durable, append-only traceability.

The V2 design must make the difference between selecting a source to send in
full and using a source as LLM grounding unambiguous to the operator.

### V2-4 — Operator-selected conversation context

Every customer and operator message displayed in the operator conversation
view shall have a checkbox. The operator can select which messages are supplied
to draft generation. The generation trace shall durably record exactly the
selected message IDs and their ordering/reference, without persisting model
chain-of-thought.

The draft must remain focused on the selected customer request and use only the
selected conversation context plus the selected/authorized evidence defined by
the final V2 rules.

### V2-5 — Customer-ready generated drafts

For Q&A-grounded drafts, the LLM shall interpret the selected Q&A content to
answer the customer request in simple, sufficient Brazilian Portuguese. Output
shall contain only the message proposed for the customer: no introduction about
the drafting process, no instructions after it, no chunk/source dump, and no
internal metadata. A simple greeting shall receive a simple natural greeting.

When no selected knowledge supports an organization-specific or clinical claim,
the model may give a short general response or request clarification, but shall
not invent the claim. Provider/RAG failure shall keep manual operator messaging
available.

## 3. V1 baseline that V2 must preserve unless explicitly superseded

- anonymous customer access is scoped server-side to one conversation;
- the raw customer token is never persisted and is never placed in URLs/logs;
- operator authentication and authorization are server-side;
- an AI generation is an internal artifact; only an explicit authenticated
  operator send may create a customer-visible operator message;
- administrative source metadata remains non-exposable to customers; clinical
  citation projection remains server-side controlled;
- messages, generations, retrieval/provenance, and audit events remain distinct
  traceable facts; no chain-of-thought is persisted;
- AI/RAG failure does not block manual service;
- data remains synthetic/demo unless a later human decision explicitly changes
  that scope.

## 4. Required V2 traceability model

The V2 data-model and API work must represent, at minimum:

- a generation's selected conversation-message IDs, stable ordering, and the
  user request/message that triggered it;
- a generation's selected evidence/retrieval-hit IDs and source type;
- a clinical child-to-parent expansion event/reference when a parent document
  is made available;
- whether final sent text used a full parent document, an AI draft, an edited
  draft, or purely manual text;
- correlation to immutable audit events without duplicating raw token values or
  chain-of-thought.

## 5. Acceptance outcomes to develop into executable tests

1. A customer can view/copy only that conversation's token; the token is not in
   route URLs, backend persistence, normal logs, or another customer view.
2. Manual search visibly returns results matching the entered query, with type
   and enough content for an operator to make an informed selection.
3. Selecting a clinical child gives the operator the complete linked parent for
   the existing explicit-send action; no automated send occurs.
4. Selecting administrative Q&A leads to a concise LLM response that addresses
   the chosen customer request and contains no chunk/source commentary.
5. Checkboxes permit the operator to select multiple customer/operator messages;
   the subsequent generation trace and audit prove exactly what was selected.
6. Unauthorized users cannot inspect or modify another conversation's token,
   message selections, evidence selections, generation inputs, or internal
   source metadata.
7. RAG/provider failure and insufficient evidence still leave manual operator
   response available.

## 6. Explicitly out of scope unless newly approved

- dynamic appointment availability, appointment holds/reservations, payment,
  scheduling, customer profile/CPF/password recovery;
- autonomous AI-to-customer send or an AI ability to change policy;
- real patient data;
- a separate vector database, microservices, or a background-job platform
  without an analyzed requirement;
- V3 feedback taxonomy, N3/N4, supervisor, management, and AI Ops features.

## 7. Decisions that must be clarified before planning/code

These are material behavior choices. Claude Code must ask the human or record
an approved resolution; it must not silently choose one.

1. **Evidence defaults and precedence:** Must draft generation use only
   operator-selected evidence, keep V1 automatic retrieval as a fallback, or
   combine both? If both are present, what is their displayed ordering and
   provenance meaning?
2. **Multiple/mixed selections:** If the operator selects more than one clinical
   child, or clinical and Q&A items together, what draft/send result is desired?
   May multiple full parent documents be inserted/sent, and in what order?
3. **Clinical send versus generation:** Is a selected clinical parent always a
   direct full-document candidate, or may the operator request an LLM-composed
   short message grounded in it as a distinct action?
4. **Message-context default and eligibility:** Are all messages initially
   selected, only the latest unanswered customer message, or none? Must every
   generation include one selected customer message? Can operator messages be
   used without a selected customer request?
5. **Regeneration behavior:** Does regeneration preserve the selected messages
   and evidence exactly, allow editing them, or create a new explicit selection
   snapshot each time?
6. **Token UX/lifecycle:** Is the token displayed continuously or behind a
   reveal action? Does copying it enable any recovery/resume workflow, or is it
   informational only within the original tab/session?
7. **Streaming:** The roadmap says streaming where beneficial. Is it in this V2
   package, and if so, which internal/operator surfaces may stream while the
   explicit human-send boundary remains intact?

## 8. Required next artifacts

After the questions above are resolved, create/update:

- `plan.md` with architecture, data migration, API, UI, accessibility, security,
  audit, error/fallback, and rollout decisions;
- `tasks.md` in dependency order, including migrations before dependent code;
- `data-model.md` and `contracts/openapi.yaml` (or a clear V2 contract);
- `acceptance.md`, requirements/security/traceability checklists, and tests;
- `analysis.md` documenting a cross-artifact and V1-to-V2 convergence review.

No V2 production code should be added before those artifacts agree.
