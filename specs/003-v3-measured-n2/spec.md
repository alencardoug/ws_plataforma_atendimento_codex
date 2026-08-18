# Feature Specification: V3 Measured N2

**Feature ID:** `003-v3-measured-n2`
**Status:** Clarification complete (2026-08-18) — planning, tasks, analysis,
and acceptance coverage required before implementation
**Authorized for specification:** 2026-08-17
**Scope:** V3 ("Measured N2") only

## 1. Purpose

V2 made N2 professional and commercially usable. V3 makes it **measured**:
give the operator a richer, trackable vocabulary for how they act on an AI
draft, and give the organization its first honest signal — Human Correction
Rate, category-level metrics, and a growing evaluation dataset — of how well
the AI is actually doing, before any conversation about autonomy (N3/N4) is
credible. V3 changes **what is measured and how the operator acts**, not
**who is allowed to send a message to a customer**.

This draft records the V3 outcomes already approved by the human — the
`ROADMAP.md` "V3 — Measured N2" bullets, plus seven additions agreed during
discovery and review on 2026-08-17 (V3-2 quick-approve; V3-7 clear/reset;
V3-8 guided knowledge-CRUD inputs; V3-9 automatic-draft countdown; V3-10
scroll-to-top on evidence selection; V3-11 confirm-before-close; V3-12
post-conversation satisfaction survey) — and nothing more. All material
behavior choices these outcomes raised were resolved with the human on
2026-08-17 and are recorded inline in §2; §7 summarizes that resolution.

## 2. Confirmed V3 outcomes

### V3-1 — Operator feedback taxonomy

Every operator action taken on (or instead of) an AI generation is
classified into a fixed, trackable taxonomy, matching `ROADMAP.md`'s V3
list: **approve, edit, regenerate, regenerate-with-instruction, search,
take-over, escalate, mark-incorrect**. This taxonomy is the raw material for
V3-3 (Human Correction Rate) and V3-5 (evaluation datasets) — every metric
V3 produces is a rollup of these tagged events, not a separately-invented
number.

Some of these already exist as distinct trackable events from V1/V2 and need
no new UI, only classification at the data layer (see `data-model.md` when
written):

- **search** — "Buscar evidências" (V2-3), already fully distinct and
  audited.
- **take-over** — already exists (V1/V2), already audited
  (`conversation.taken_over`).
- **regenerate** — V2 deliberately has no dedicated "Regenerar" control
  (`prior_generation_id` already links a new generation to what it
  replaced); a second "Gerar rascunho" call against the same conversation
  *is* a regenerate event and is already fully derivable from existing data.

Others are genuinely new for V3. Resolved 2026-08-17 (see §7):

- **edit** — binary and always inferred: `sent_text != draft_text` is
  classified `edit`, with no edit-distance magnitude and no operator-chosen
  classification. Simpler and avoids subjective operator judgment calls.
  Resolved 2026-08-17: an `edit` event must retain what it needs to support
  turning a correction into new knowledge — at minimum the customer's
  triggering message, `draft_text`, and `sent_text` — so that, from the
  conversation view, the operator can trigger a manual "transformar em Q&A"
  action that opens V3-8's guided knowledge-CRUD form pre-filled (question =
  customer's message, answer = `sent_text`, category = the conversation's
  category as a suggested default). The operator reviews and explicitly
  confirms before any `content.qa_entries` row is created — no automatic or
  queued creation. See V3-8 and acceptance outcome 9a.
- **regenerate-with-instruction** — a new capability (V3-6), not just a tag;
  see V3-6 for its UX.
- **escalate** — redefined from the roadmap's original framing. This is
  **not** a signal to route the conversation to a human specialist (that
  remains V5's "call-center specialist escalation" workflow, untouched).
  It marks that the operator could not answer using what is already
  standardized/known to the knowledge base — a content-gap signal, not a
  handoff request. It feeds V3-5 (evaluation datasets) and V3-8 (knowledge
  CRUD) as a prompt to review/extend standardized content, not a queue.
  Tag only for V3 either way — no routing or queue view.
- **mark-incorrect** — new UI affordance, available on every message in the
  conversation history (not restricted to the most recent generation, and
  not confined to the metrics surface), so an operator can flag a past
  generation retroactively while reviewing a conversation.

### V3-2 — Quick-approve action

A single explicit operator action that sends the current AI draft
**unmodified** — addresses the operator-friction concern raised in this
conversation (many drafts need zero editing; today sending one still means
opening/using the reply box) **without weakening V1 Article III**: it is
still one explicit authenticated-operator action per message, still visibly
distinguishable from an edited send, and it is the canonical way an
`approve` (V3-1) event is recorded. This does **not** run automatically and
is not a toggle — an operator acts on one generation at a time, same as
every existing send path.

### V3-3 — Human Correction Rate and related evidence

A first real, computed metric (not a placeholder) measuring how often/how
much an operator changes an AI draft before sending, aggregated overall and
per-category. Formula: share of generations classified `edit` (V3-1, binary,
`sent_text != draft_text`) out of all sent generations (`edit` + `approve`,
including V3-2 quick-approve), overall and broken down by category.

### V3-4 — First read-only management metrics

Resolved 2026-08-17: documented, versioned SQL queries (extending
`teste_humano.md`'s existing manual work), not a new dashboard screen — a
dashboard UI is deferred to V4's supervisor interface, which needs one
regardless. V3-4 covers at least: abstention rate overall and by category,
Human Correction Rate (V3-3) overall and by category, generation volume by
trigger/category, and V3-12's satisfaction results (average score and
resolved-rate) overall and by category. Read only — V3 introduces no policy
or configuration surface.

### V3-5 — Evaluation datasets/suites tied to category

A durable, category-tagged record of evaluation cases (question, expected
behavior/evidence, and — once run — actual outcome), so quality can be
tracked over time and regressions caught, instead of relying on ad hoc
manual review. `teste_humano.md`'s manual RAG-evaluation work (2026-08-17)
is the intended seed content for this — its registry table (§5 of that
document) maps directly to what this data model needs to durably store.
Resolved 2026-08-17: V3 delivers only the durable data model/storage for
these cases (seeded manually); an automated mechanism to re-run stored
cases against the live system and record pass/fail is out of scope for V3
and deferred to a future V.

### V3-6 — Regenerate-with-instruction

A new way for the operator to steer a regeneration with a short free-text
instruction (e.g. "seja mais formal", "inclua o horário de atendimento"),
distinct from V2-4's message-selection and V2-3's manual-search-text inputs.
Still produces an internal draft only; still requires an explicit operator
send. Resolved 2026-08-17: free-text box (not fixed presets), combining with
the existing message-selection/manual-search-text inputs for that
generation rather than replacing them. The instruction text gets the same
non-customer-facing, audited handling `manual_search_text` already gets
(§4); exact logging mechanism is a `plan.md`-level detail.

### V3-7 — Clear/reset control for draft and evidence search

A single control that resets the operator's in-progress draft panel and
manual-search-evidence results back to empty, independent of message
selection (V2-4's existing "desmarcar conversas" already handles that).
Addresses a concrete operator-workflow gap raised during discovery
(2026-08-17): today there is no way to discard a generated draft or a stale
search result set without navigating away and back. Does not touch or
delete anything already sent or already durably stored (`ai_generations`
rows, audit events) — purely resets transient client-side UI state. Resolved
2026-08-17: no server-side "dismissed" event — HCR/V3-1 metrics do not
distinguish "generated and discarded" from "never generated" for V3.

### V3-8 — Guided knowledge-CRUD inputs (`/operator/knowledge`)

Raised during discovery (2026-08-17): today `KnowledgeAdminPage`'s
`category` field is free text (no visibility into existing categories,
easy to fragment the taxonomy V3-3/V3-4/V3-5 all key off), and the
dynamic-binding `Tabela`/`Filtro`/`Colunas de saída` fields are raw
text/JSON with no guidance from what's actually valid (today, only
`knowledge_dynamic_fixture` is allowlisted; Phase 11's `validate_binding`
already rejects an invalid table/column with `422`, but only after the
operator submits, not before). V3 replaces free text with guided input:

- `category`: resolved 2026-08-17 — the free-text `category` column is
  formalized into a real registry (a proper category table), not just
  "distinct existing values." The combo box lists that registry (fetched
  from the API, so it stays live as the taxonomy grows) plus an explicit
  "create new category" path, with server-side enforcement against
  typos/near-duplicates. V3-1/V3-3/V3-4/V3-5/V3-12's category breakdowns all
  key off this registry.
- Dynamic-binding `Tabela`: a dropdown of exactly the server-side
  allowlisted tables (today just one; grows if a future feature adds more)
  instead of free text that can typo past the 422 check.
- `Filtro`/`Colunas de saída`: guided by the *selected* table's actual
  columns rather than hand-typed JSON. Resolved 2026-08-17: the new
  read-only endpoint uses **live `information_schema` introspection**
  (still strictly scoped to allowlisted table names only, never arbitrary
  schema access) rather than a static hardcoded column map, so it never
  drifts out of sync if an allowlisted table's columns change.
- the manual "transformar em Q&A" action (V3-1) opens this same guided form,
  pre-filled, as one more entry point alongside the existing
  create-new-entry flow.

This is real backend+frontend scope (a new endpoint, not just a frontend
dropdown), which is why it is deferred to V3's SDD cycle rather than done
as an ad hoc patch.

### V3-9 — Automatic-draft countdown indicator

Raised during discovery (2026-08-17): alongside the existing "cliente está
digitando…" indicator (V2-7), show a live countdown to when the automatic
draft will fire (the 8-second idle threshold, `AUTOMATIC_TRIGGER_IDLE_SECONDS`).
Feasible without new infrastructure: the backend already computes
idle-since-last-activity server-side for V2-7's own trigger logic
(`evaluate_automatic_trigger`); exposing `last_customer_activity_at` (or a
derived "seconds remaining") on `OperatorConversationDetail` lets the
frontend tick a countdown locally between polls, resynced from the server
timestamp on every 2-second poll so client-clock drift never compounds.
`AUTOMATIC_TRIGGER_IDLE_SECONDS` itself should come from
`/operator/runtime-config` (already exists) rather than being duplicated as
a hardcoded frontend constant. Resolved 2026-08-17: the countdown is shown
only when there is customer activity not yet covered by any generation —
i.e. exactly when `evaluate_automatic_trigger` would actually act — not
shown continuously whenever the conversation is merely eligible/active with
nothing pending.

**Known imprecision, not a defect to design around:** V2-7's trigger is
lazily evaluated (piggybacked on the operator's poll and the customer's
typing-heartbeat, `plan.md` §7.2 — no real scheduler, per Constitution
Article VIII). The countdown reaching zero is an estimate of *when the
threshold is crossed*, not a guarantee the generation has fired that
instant — the actual `AIGeneration` still only appears on the next poll
or heartbeat tick after that (worst case, a couple of seconds later). The
UI should show a distinct "gerando…" state once the countdown hits zero,
not sit at "0" implying nothing is happening.

### V3-10 — Scroll to top on evidence selection

Raised during discovery (2026-08-17): when the operator clicks "Selecionar"
on a manual-search evidence result, the page should scroll to the top so
the resulting draft panel (which renders in the "IA / Evidências" column,
potentially below the fold after scrolling through search results) is
immediately visible without a manual scroll. Small, purely client-side UX
fix — no backend change. Resolved 2026-08-17: scoped to evidence selection
("Selecionar") only — "Gerar rascunho" and V3-6's regenerate-with-instruction
do not trigger this scroll.

### V3-11 — Confirm before closing a conversation

Raised during discovery (2026-08-17): "Encerrar conversa" closes a
conversation with no confirmation step today, on both the customer and
operator surfaces, and a closed conversation cannot be reopened (V1/V2
behavior, unchanged). Add a confirm/cancel prompt before the close action
actually fires — purely a client-side guard in front of the existing close
endpoint; no backend/API change. Resolved 2026-08-17: both surfaces get the
confirmation step, with simple, identical-in-spirit copy: "Deseja encerrar
a conversa?" with two actions, "Encerrar conversa" and "Retornar e continuar
conversa". Choosing to continue leaves status and all state unchanged (no
partial side effect).

### V3-12 — Post-conversation satisfaction survey

Raised during review (2026-08-17): after a conversation closes (V3-11), the
customer is offered a short, optional satisfaction survey — a 1-to-5 score
(shown with green-to-red emoji, matching the ROADMAP's request) and a
separate yes/no question, "Sua necessidade foi resolvida?" (Sim 🙂 / Não
🙁). Customer-facing only — the operator surface gets no equivalent
self-assessment prompt. Answering is optional and does not block or delay
the conversation's closure, which already completed via V3-11; the survey
is a follow-on step the customer may dismiss without answering. Results are
durable, tied to the closed conversation and its category, and roll into
V3-4's read-only metrics (average score and resolved-rate, overall and by
category) alongside HCR and abstention rate. No policy or automated action
is triggered by a low score in V3 — that is a future V's concern if ever
authorized.

## 3. V1/V2 baseline that V3 must preserve unless explicitly superseded

- **Constitution Article III is unchanged: an AI generation remains an
  internal artifact; only an explicit authenticated-operator action creates
  a customer-visible message.** V3-2's "quick-approve" is one more *path* to
  that same explicit action, not an exception to it. No toggle, setting, or
  automatic condition may cause a generation to reach a customer without a
  human clicking send for that specific message. (This was explicitly
  requested as an N4-style auto-send toggle during discovery on
  2026-08-17 and explicitly declined for V3 — see `DECISIONS.md`.)
- anonymous customer access remains scoped server-side to one conversation;
  the raw customer token is never persisted and never placed in URLs/logs;
- operator authentication/authorization remains server-side; UI state is
  never trusted as authorization;
- administrative source metadata remains non-exposable to customers;
  clinical citation projection remains server-side controlled;
- messages, generations, retrieval/provenance, `message_selections`, and
  audit events remain distinct traceable facts; no chain-of-thought is
  persisted anywhere new V3 adds;
- AI/RAG failure does not block manual service;
- data remains synthetic/demo (Constitution Article VI) — V3 is entirely
  about *measuring* the existing synthetic-data system better, not about
  handling real data.

## 4. Required V3 traceability model

The V3 data model and API work must represent, at minimum:

- for every generation, which V3-1 taxonomy tag(s) applied to what happened
  to it (approved unmodified / edited-then-sent / regenerated / regenerated
  with instruction / discarded in favor of search / discarded via take-over
  / marked incorrect / marked for escalation), without inventing a second,
  parallel record of what V2 already tracks (`trigger`, `prior_generation_id`,
  `message_selections`, `manual_search_text`);
- whatever V3-6's instruction text is, with the same non-customer-facing,
  audited handling `manual_search_text` already gets;
- evaluation cases (V3-5) as durable rows, category-tagged, distinguishable
  from production conversations (must never be counted in V3-3/V3-4's
  production metrics, and must never reach a real customer);
- a formal category registry (V3-8) that `content.qa_entries.category` and
  every other category-tagged fact in this document (V3-1/V3-3/V3-4/V3-5/
  V3-12) key off, replacing today's ungoverned free-text column;
- an `edit` event's link back to its customer message and `draft_text`/
  `sent_text` pair, sufficient to drive V3-1's "transformar em Q&A" action
  without re-deriving anything already stored;
- V3-12 survey responses as durable rows tied to the closed conversation and
  its category, distinguishable from conversation/message data proper;
- enough to compute V3-3/V3-4 from stored facts alone — no metric may be
  computed from data that isn't itself durably recorded and auditable.

## 5. Acceptance outcomes to develop into executable tests

1. Every one of V3-1's eight taxonomy tags is observable in stored data
   after the corresponding operator action, without ambiguity about which
   tag applies; `edit` is derived solely from `sent_text != draft_text`
   (no magnitude, no operator-chosen classification) and `escalate` is
   verifiably tag-only (no queue, no routing side effect).
2. Quick-approve (V3-2) sends the draft byte-for-byte unmodified, is tagged
   `approve`, and — like every other send path — cannot fire without an
   explicit authenticated-operator action for that specific message; a
   negative test proves no code path can trigger it automatically.
3. Human Correction Rate (V3-3) is computed only from durably stored
   approve/edit facts, is reproducible from raw data by an independent
   query, and is available both overall and broken down by category.
4. The read-only metrics surface (V3-4) never exposes a control that
   changes system behavior — read-only is enforced server-side, not just
   omitted from the UI.
5. An evaluation case (V3-5) run against the live system never creates a
   customer-visible message, is excluded from V3-3/V3-4's production
   metrics, and is traceable back to the category it was seeded for.
6. Regenerate-with-instruction (V3-6) produces an internal draft only
   (same as every other trigger); the instruction text is retrievable in
   operator/audit views and never appears in a customer-visible field
   unless an operator explicitly sends text containing it.
7. All V1/V2 acceptance outcomes this spec's §3 lists as preserved still
   pass unmodified (spot-check, not a full rerun of V1/V2's suites).
8. Clear/reset (V3-7) empties the draft panel and evidence-search results
   without affecting message selection, without deleting any durably stored
   generation/audit row, and without requiring navigation away from the
   conversation.
9. Guided knowledge-CRUD inputs (V3-8): the category selector always
   reflects the current live registry of categories (no client-side
   staleness after another operator adds one); the table dropdown never
   lists a non-allowlisted table; filter/output-column suggestions for a
   selected table only ever come from that table's real columns via the new
   read-only `information_schema` endpoint, scoped strictly to allowlisted
   tables, never arbitrary schema introspection.
9a. The "transformar em Q&A" action (V3-1) on an `edit` event opens V3-8's
    guided form pre-filled with the customer's message, `sent_text`, and a
    suggested category; no `content.qa_entries` row is created without the
    operator explicitly confirming the pre-filled form.
10. The countdown indicator (V3-9) resets correctly when new customer
    activity extends the idle window (matching V2-7's existing reset
    behavior exactly, not a separate/divergent clock), never shows a
    negative or stale value after the tab has been idle/backgrounded and
    resumed, and does not itself cause a generation to fire — it only
    reflects server-computed state, matching acceptance outcome D of V2's
    `acceptance.md` (typing-debounce) which this must not regress.
11. Selecting evidence (V3-10) scrolls the page to the top; it does not
    fight or fire redundantly against the browser's own scroll restoration
    on unrelated re-renders (e.g. the 2-second poll updating unrelated
    state must not repeatedly yank the scroll position back to top).
12. "Encerrar conversa" (V3-11) never closes a conversation without an
    explicit confirm step, on both customer and operator surfaces; choosing
    "Retornar e continuar conversa" leaves the conversation's status and all
    state completely unchanged (no partial side effect from the cancelled
    attempt).
13. The satisfaction survey (V3-12) never blocks or delays the conversation
    close that V3-11 already performed; skipping it leaves no partial or
    inconsistent record; a submitted response is durably tied to the
    correct conversation and category and is reflected in V3-4's metrics.

## 6. Explicitly out of scope unless newly approved

- autonomous AI-to-customer send in any form, including a toggle, setting,
  policy default, or scheduled/conditional trigger — this is N4 (Era C),
  requires its own future authorization, and was explicitly declined for V3
  during discovery on 2026-08-17;
- N3 governed autonomy, supervisor interface, category-level ON/OFF/REVIEW/
  ESCALATE *policy enforcement* (V4) — V3-1's `escalate` tag records intent
  only, it does not implement policy;
- the actual specialist-escalation *workflow* (routing, queue, handoff
  package) — that is V5;
- dynamic appointment availability, scheduling, payment, customer profile/
  CPF/password recovery — unchanged from V2's exclusions;
- real patient data — unchanged from V2's exclusions (Constitution Article
  VI);
- a separate vector database, microservices, or background-job platform
  without an analyzed requirement (Constitution Article VIII).

## 7. Decisions that must be clarified before planning/code

All material behavior choices identified during discovery and review are
resolved as of 2026-08-18 and captured above:

- `edit` classification, binary/always-inferred, and its retained link to
  the triggering message for the "transformar em Q&A" action — V3-1;
- `escalate` redefined as a content-gap signal (tag only, no queue/routing,
  distinct from V5's specialist-escalation workflow) — V3-1;
- `mark-incorrect` available on every message in conversation history —
  V3-1;
- Human Correction Rate's exact formula — V3-3;
- V3-4's metrics surface as documented/versioned SQL, not a new dashboard
  screen, and its inclusion of V3-12's satisfaction results — V3-4;
- V3-5 scoped to durable storage only, no re-run mechanism — V3-5;
- regenerate-with-instruction (V3-6) as a free-text box combined with (not
  replacing) existing message-selection/manual-search-text inputs — V3-6;
- V3-7's clear/reset as pure client-side state, no server-side "dismissed"
  event — V3-7;
- the category taxonomy formalized into a real registry, and V3-8's column
  introspection as live `information_schema` lookups scoped to the
  allowlist — V3-8;
- V3-9's countdown shown only when there is customer activity not yet
  covered by a generation — V3-9;
- V3-10's scroll-to-top scoped to evidence selection only — V3-10;
- V3-11's confirm step on both customer and operator surfaces, with the
  exact copy — V3-11;
- V3-12 (satisfaction survey) added to scope during review: customer-only,
  optional/non-blocking, feeding V3-4's metrics — V3-12.

If a new material behavior choice surfaces during `plan.md`/`tasks.md`
authoring, record it here (or in a dedicated `clarifications` note) and
resolve it with the human before proceeding, per the same rule V1/V2 used.

## 8. Required next artifacts

After the questions above are resolved, create/update:

- `plan.md` with architecture, data-model, API, UI, accessibility, security,
  audit, and testing decisions for every confirmed V3-1..V3-12 outcome;
- `tasks.md` broken into dependency-ordered phases, each with its own gate;
- `data-model.md` / `contracts/openapi.yaml` deltas over V2's;
- `acceptance.md` covering §5 above as executable scenarios;
- `checklists/{requirements,security,traceability}.md`;
- `analysis.md` (Spec Kit `analyze`-equivalent cross-artifact convergence)
  before any V3 production code is written.
