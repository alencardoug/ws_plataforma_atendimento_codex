# Feature Specification: V2 Commercial Product Experience

**Feature ID:** `002-v2-commercial-product-experience`
**Status:** Clarification complete (2026-08-14) — planning, tasks, analysis,
and acceptance coverage required before implementation
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
own active conversation continuously (no reveal/hide action) and offer an
explicit copy action. The token shall not be put into a URL, ordinary logs,
audit payloads, analytics, or another conversation's UI. The backend continues
to persist only its secure digest.

The token format changes from V1's long random string to a **short 8-character
code, uppercase letters and digits, excluding visually ambiguous
characters** (`0`/`O`, `1`/`I`/`L`; `plan.md` §3.1 pins the exact 31-symbol
alphabet). It exists purely for the customer's own record-keeping (e.g.
reading it back to a support contact) — copying or displaying it does not
create a customer account, a cross-session recovery workflow, or any way to
resume/reopen a conversation. This is an explicit, deliberate scope boundary,
not an oversight.

Because a short code has meaningfully less entropy than V1's token, `plan.md`
**must** define brute-force mitigation for the anonymous-conversation-access
endpoint that validates it (rate limiting and/or lockout per token attempt,
by source and/or by conversation), and the negative tests proving it. This is
a required part of the V2-2 acceptance evidence, not an optional hardening
item.

### V2-3 — Operator-selected manual evidence ("Buscar evidências")

A distinct **"Buscar evidências"** action searches the knowledge chunks using
the operator's manual-search query and returns inspectable administrative
Q&A records and clinical child chunks. Exactly one returned item is
selectable at a time — no multi-select of chunks.

Selecting an item triggers the outcome automatically, with no separate
confirmation step:

- selecting a clinical child makes its complete parent document available for
  the normal explicit operator-send workflow. This is the *only* outcome for
  clinical evidence in this action — there is no alternate LLM-composed short
  reply grounded in a clinical document, here or anywhere else in V2;
- selecting administrative Q&A supplies its approved Q&A content to the LLM,
  which produces a concise answer focused on the customer's request rather than
  reproducing chunks, source labels, instructions, or retrieval metadata;
- the system records the selected evidence ID, its source type, clinical
  parent expansion when used, generation provenance, and any final explicit
  operator send in durable, append-only traceability.

"Buscar evidências" is fully independent of "Gerar rascunho" (V2-7): it does
not combine with selected conversation-message context (V2-4) and does not
use automatic chunk selection. The two actions happen to read the same
manual-search text box as a convenience; they do not share a pipeline.

### V2-4 — Operator-selected conversation context

Every customer and operator message displayed in the operator conversation
view shall have a checkbox. By default, only the latest consecutive run of
customer messages since the last operator reply comes pre-selected; the
operator can check/uncheck any message, and a **"desmarcar conversas"**
control clears every conversation-message selection at once. The generation
trace shall durably record exactly the selected message IDs and their
ordering/reference, without persisting model chain-of-thought.

If no conversation message is selected, only the manual-search text box
content is used as input to generation. If neither any conversation message
is selected nor the manual-search box has content, "Gerar rascunho" (V2-7)
and "Buscar evidências" (V2-3) must not generate anything — both actions stay
inert/blocked in that state.

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

### V2-6 — Dynamic-evidence safety correction (D-028)

When selected or retrieved evidence has `dynamic_data_required=true`, the
final response shall follow a developed chunk pattern whose variables are
substituted from live database content; the LLM shall not compose or rewrite
the response in this case — the resolved, substituted pattern is the final
message. This closes the V1 finding that such evidence (e.g. entries whose
`answer_markdown` names internal identifiers like `scheduling.available_offers`)
could reach the LLM with only a prompt-level, not code-level, safeguard.

This outcome is scoped to the correction mechanism only. It does not authorize
appointment holds/reservations/confirmations, CPF/identity/payment handling,
or autonomous scheduling — those remain excluded per §6 and `ROADMAP.md`'s
separate "Dynamic appointment availability" future feature.

**Mechanics:**

- The chunk pattern and its variables are authored **manually** by whoever
  maintains the knowledge base, through the V2-8 knowledge-management screen.
  A variable's name corresponds to a column name in a structured PostgreSQL
  table (e.g. a scheduling-availability table with columns for medical
  specialty, date, time, doctor, and availability status). Resolving a
  pattern means querying that table filtered by the relevant columns (e.g.
  specialty + positive availability) and substituting the returned column
  values into the pattern's variables.
- Wiring a specific Q&A entry to its source table/filter/columns is an
  explicit, per-entry configuration — it is not inferred or generic. A Q&A
  entry can be flagged `dynamic_data_required=true` without yet having this
  wiring configured.
- **An entry flagged `dynamic_data_required=true` that has no wiring
  configured yet, or whose configured lookup fails (connection error, missing
  table/column, no matching row, stale/unavailable data), always falls back
  to manual service — it never returns a literal or partially-substituted
  pattern to the customer.** The specific cause (e.g. "column
  `nome_do_medico` not found in table X", "no row matched the filter") is
  recorded for the **operator/audit trail only**, with the same detail as the
  example above. Consistent with V1's citation-exposure boundary, this
  diagnostic detail — table names, column names, query specifics — must never
  reach the customer; the customer-facing fallback stays a safe, generic
  manual-service message.
- This mechanism applies only to Q&A entries explicitly flagged
  `dynamic_data_required=true` with this configuration; it is not a general
  templating feature for other Q&A content.

### V2-7 — Draft generation triggers: automatic and manual ("Gerar rascunho")

Two triggers reach the same smart RAG+LLM generation, with *automatic* chunk
selection by the system (unlike V2-3's manually selected single chunk). There
is no token-by-token streaming of generated text anywhere in V2 — the draft
appears complete once generated, same as V1.

- **Automatic/instant, debounced by an 8-second inactivity window:** the
  customer client sends a live "is typing" signal while the message box has
  focus/content — not just on message send. The automatic trigger fires only
  after 8 seconds pass with no typing activity and no new message. Sending a
  message does not by itself fire generation if the customer keeps typing
  within the window; several consecutive customer messages sent within
  successive windows accumulate into one batched trigger over all of them
  (e.g. 4 messages sent within a typing burst, then 8s idle → one generation
  over those 4; 2 more messages then 8s idle again → one generation over the
  latest 6, per V2-4's "consecutive run since the last operator reply"
  default). This intentionally reduces the number of automatic generation
  calls compared to firing on every message. The "is typing" state is also
  shown to the operator as a live indicator in the conversation view. The
  operator reviews the eventual result via **"Usar sugestão"** to accept/send
  it.
- **Manual ("Gerar rascunho")**: the operator explicitly triggers generation
  using whatever is currently selected — checked conversation messages (V2-4)
  plus the manual-search text box content (which may be empty).

"Gerar rascunho" always regenerates against the current selection state.
There is no separate "Regenerar" action: changing the selection and
re-invoking "Gerar rascunho" already produces a fresh draft, so a dedicated
regenerate control would be redundant.

Both triggers produce the same kind of internal `AIGeneration` draft, subject
to the same explicit-operator-send boundary as V1 (§3). "Gerar rascunho" is
unrelated to "Buscar evidências" (V2-3) — independent actions that happen to
share the manual-search text box, not a combined pipeline.

### V2-8 — Knowledge-base CRUD ("registros" screen)

V2 needs an authenticated screen for full CRUD (create, read, update, delete)
on both administrative Q&A entries and clinical parent/child documents,
including authoring/editing the V2-6 dynamic-pattern wiring on a Q&A entry.
It reuses the existing operator credentials/authentication — no new role is
introduced. `plan.md` must define how this interacts with the existing
offline ingestion path (`customer_care.knowledge.ingest`), including
re-embedding on create/update and audit coverage for these CRUD operations,
consistent with the constitution's traceability requirements.

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
8. Repeated invalid token attempts against the anonymous-access endpoint are
   rate-limited/locked out; the token character set excludes visually
   ambiguous characters.
9. An automatic draft is not generated while the customer is actively typing
   or sending consecutive messages; it fires only after 8 seconds of
   inactivity, over the accumulated messages since the last operator reply,
   and the operator sees a live "customer is typing" indicator.
10. A `dynamic_data_required=true` entry with no configured table/column
    wiring, or whose lookup fails, always falls back to manual service with a
    generic customer-facing message; the specific cause is visible only in
    operator/audit views, never to the customer.
11. An authenticated operator can create, read, update, and deactivate/delete
    both Q&A entries (including their V2-6 dynamic-pattern wiring) and
    clinical parent/child documents, with durable audit coverage.

## 6. Explicitly out of scope unless newly approved

- dynamic appointment availability, appointment holds/reservations, payment,
  scheduling, customer profile/CPF/password recovery — with the single narrow
  exception of V2-6's dynamic-evidence safety correction, which is in scope;
- autonomous AI-to-customer send or an AI ability to change policy;
- real patient data;
- a separate vector database, microservices, or a background-job platform
  without an analyzed requirement;
- V3 feedback taxonomy, N3/N4, supervisor, management, and AI Ops features.

## 7. Decisions that must be clarified before planning/code

All material behavior choices identified during discovery are resolved as of
2026-08-14 and captured above:

- evidence defaults/precedence, multiple/mixed selections, clinical send
  versus generation, message-context default/eligibility, and regeneration
  behavior — V2-3, V2-4, V2-7 (no separate "Regenerar" action; re-invoking
  "Gerar rascunho" against the current selection serves that purpose);
- token UX/lifecycle and format — V2-2 (always visible, short code, no
  recovery semantics, required brute-force mitigation);
- streaming — V2-7 (none; the 8-second typing-debounced automatic trigger is
  the relevant mechanism instead);
- dynamic-evidence pattern mechanics — V2-6 (manually authored, column-named
  variables against a structured table; unconfigured/failed lookups fall back
  to manual with an operator/audit-only detailed cause);
- a new scope item surfaced during clarification — V2-8, knowledge-base CRUD.

If a new material behavior choice surfaces during `plan.md`/`tasks.md`
authoring, record it here (or in a dedicated `clarifications` note) and
resolve it with the human before proceeding, per the same rule.

## 8. Required next artifacts

After the questions above are resolved, create/update:

- `plan.md` with architecture, data migration, API, UI, accessibility, security,
  audit, error/fallback, and rollout decisions;
- `tasks.md` in dependency order, including migrations before dependent code;
- `data-model.md` and `contracts/openapi.yaml` (or a clear V2 contract);
- `acceptance.md`, requirements/security/traceability checklists, and tests;
- `analysis.md` documenting a cross-artifact and V1-to-V2 convergence review.

No V2 production code should be added before those artifacts agree.
