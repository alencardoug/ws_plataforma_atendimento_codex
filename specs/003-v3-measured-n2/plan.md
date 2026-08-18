# Implementation Plan: V3 Measured N2

## 1. Technical summary

V3 adds three new tables (`content.categories`, `content.evaluation_cases`,
`customer_service.conversation_satisfaction_responses`) and six new nullable
columns on `ai_generations` (`instruction_text`, `category_slug`,
`marked_incorrect_at`, `marked_incorrect_by_operator_id`, `escalated_at`,
`escalated_by_operator_id`). No new services, no new background worker, no
new distributed infrastructure (Constitution Article VIII) — every new
signal is computed inline in an existing request/response cycle or exposed
as documented, versioned read-only SQL (V3-4), the same no-scheduler
posture V2-7's automatic trigger already established.

A key finding from re-reading the current implementation
(`app/customer_care/operator_workspace/router.py`,
`send_operator_message`): V3-1's **approve** and **edit** tags are not new
work. `send_operator_message` already computes
`edited = bool(generation and generation.draft_text != payload.body)` and
records it as `ai.draft_accepted` / `ai.draft_edited` on every operator
send. V3 does not add a mechanism for this — it names and aggregates an
audit fact that has existed since V1/V2. Consequently **V3-2
(quick-approve) requires no backend change at all**: it is a frontend
button that calls the existing `POST /operator/conversations/{id}/messages`
with `body` set to the current draft's `draft_text` unmodified and
`source_generation_id` set to that draft's id — the existing
`edited = draft_text != payload.body` check does the rest, and Article
III's "one explicit authenticated-operator action" guarantee is the
existing endpoint's guarantee, not a new one.

## 2. Module boundaries

- `customer_care.ai.router` — `generate_draft`/`DraftIn` gain
  `instruction_text` (V3-6); `generation_dict`/`latest_generation_dict` gain
  `category_slug` and the new flags (V3-1); `operator_conversation_detail`'s
  countdown fields (V3-9) are computed here, next to
  `evaluate_automatic_trigger`, and consumed by `operator_workspace.router`.
- `customer_care.operator_workspace.router` — two new assignment-gated
  actions, mark-incorrect and escalate (V3-1). No new quick-approve
  endpoint (see §1).
- `customer_care.knowledge.router` / `dynamic_binding.py` — category
  registry CRUD, dynamic-table listing, and the new column-introspection
  endpoint (V3-8), all in the module that already owns `qa_entries` CRUD
  and `ALLOWLISTED_TABLES`.
- `customer_care.anonymous_access.router` — one new public endpoint,
  satisfaction submission (V3-12), using the existing
  `token_bound_conversation` dependency.
- `customer_care.audit.service` — reused as-is; no new module, only new
  `event_type` values (§19).
- `customer_care.evaluation` (**new package**, the only new module V3
  introduces) — a thin model/CRUD surface for `content.evaluation_cases`
  (V3-5). Kept separate from `knowledge` (cases are not retrievable
  knowledge) and from `operator_workspace` (not conversation-scoped). No
  execution engine — storage only, per spec.md §7. This does not add a
  service or a deployment unit; it is a Python subpackage inside the same
  FastAPI app, consistent with Constitution Article VIII.
- Frontend: everything continues to live in `frontend/src/main.tsx`
  (`CustomerPage`, `OperatorPage`, `KnowledgeAdminPage`) — no new files
  required by V3 alone, though `tasks.md` may choose to split the file
  given its growth across V1/V2/V3; that split is a refactor, not new
  product behavior, and is out of scope for this plan.

## 3. Persistence strategy and migrations

### 3.1 Category registry (V3-8, cross-cutting: V3-1/V3-3/V3-4/V3-5/V3-12)

New table `content.categories`:

| Field | Notes |
|---|---|
| slug text PK | stable identifier; existing free-text values become slugs verbatim on migration |
| label text | display label, independently editable from the slug |
| is_active bool default true | soft-delete, matching `content.documents`/`content.chunks`/`content.qa_entries`'s existing convention |
| created_at timestamptz | |

Migration: create the table; backfill from **both** existing taxonomies
that already repeat across the content model —
`content.qa_entries.category` (administrative topics: `agenda`, `preco`,
`instituicao`, ...) and `content.documents.cancer_type` (clinical site:
today `mama`, `colorretal` — see `scripts/generate_documents.py`'s
`BREAST`/`COLORECTAL` fixtures) — at the same granularity level, resolved
2026-08-18 after the human pointed out the clinical side already has a
real, repeated site taxonomy that V3 should not ignore:

```sql
INSERT INTO content.categories (slug, label)
SELECT DISTINCT category, category FROM content.qa_entries WHERE category IS NOT NULL
UNION
SELECT DISTINCT cancer_type, cancer_type FROM content.documents WHERE cancer_type IS NOT NULL
ON CONFLICT DO NOTHING;

ALTER TABLE content.qa_entries ADD CONSTRAINT qa_entries_category_fkey
  FOREIGN KEY (category) REFERENCES content.categories(slug);
ALTER TABLE content.documents ADD CONSTRAINT documents_cancer_type_fkey
  FOREIGN KEY (cancer_type) REFERENCES content.categories(slug);
```

Both `qa_entries.category` and `documents.cancer_type` keep their existing
name, type, and nullability — each only gains a governing FK into the same
registry. `content.documents.care_phase` (the ~16-value treatment-phase
taxonomy — `cirurgia`, `quimioterapia`, `radioterapia`, `pos_operatorio`,
...) is a **separate, finer-grained axis and stays out of `category` for
V3** (resolved 2026-08-18: `cancer_type`, not `care_phase`, matches
administrative categories' level of granularity) — nothing prevents a
future V from adding it as a second breakdown facet. New categories are
created through V3-8's "create new category" path (for administrative
entries) or directly by whoever authors a new `cancer_type` fixture (for
clinical entries, unchanged process, now FK-governed).

**Category scope, stated explicitly:** every "by category" breakdown in
V3-3/V3-4/V3-12 attributes a category to any `ANSWER` generation grounded
in either an administrative Q&A entry or a clinical parent document. An
`ABSTAIN` or a plain-greeting generation with no evidence still produces
`category_slug = NULL` — that case did not change. Every V3-4 query must
show that as an explicit "sem categoria" row, never a silently dropped or
misattributed one.

`ai_generations.category_slug` (nullable, FK → `content.categories.slug`)
is set once, at generation-completion time, inside `generate_draft` and
`select_evidence` (`app/customer_care/ai/router.py`): if `status ==
"ANSWER"` and the `use_order = 1` `AIGenerationSource` resolves to a
`RetrievalHit` where `matched_qa_id` is set, copy that `QAEntry.category`;
else if that hit's `expanded_parent_document_id` is set, copy that
`KnowledgeDocument.cancer_type` (this covers both the LLM-composed Q&A
path and the deterministic `full_parent_draft` clinical-parent path,
`ai/router.py`, since both go through the same `AIGenerationSource`
bookkeeping); otherwise leave `NULL`. This derivation rule is a plan-level
design decision (the same class of call V2's plan.md made for
`message_selections` ordering): it makes every category-tagged metric a
plain `GROUP BY ai_generations.category_slug` instead of re-deriving the
evidence join per query, while remaining fully reconstructable from
`ai_generation_sources` → `retrieval_hits` → `qa_entries`/`documents` alone
if the column were ever dropped — satisfying spec.md §4's "no metric may
be computed from data that isn't itself durably recorded."

### 3.2 `ai_generations` new columns (V3-1, V3-6)

| Field | Notes |
|---|---|
| instruction_text text nullable | V3-6's free-text steering instruction; set only on a regenerate-with-instruction call, combined with (not replacing) `manual_search_text`/`selected_message_ids` for that same call |
| category_slug text FK → content.categories.slug, nullable | §3.1 |
| marked_incorrect_at timestamptz nullable | V3-1, retroactive, any generation in history |
| marked_incorrect_by_operator_id FK → operator_users.id, nullable | |
| escalated_at timestamptz nullable | V3-1, redefined per spec.md — content-gap signal, not routing |
| escalated_by_operator_id FK → operator_users.id, nullable | |

No new column for **approve**/**edit** (already `ai.draft_accepted` /
`ai.draft_edited`, §1) or for **search**/**take-over**/**regenerate**
(already fully derivable, spec.md V3-1):

- search: `generation.trigger == "MANUAL_EVIDENCE"`.
- take-over: `conversation.taken_over_at IS NOT NULL` for the generation's
  conversation.
- regenerate: `generation.prior_generation_id IS NOT NULL`.
- regenerate-with-instruction: same, plus `instruction_text IS NOT NULL`.

The eight-tag classification (acceptance outcome 1) is implemented once as
`classify_generation(session, generation) -> set[str]`, a new function in
`customer_care/ai/router.py`, reused verbatim by the V3-4 documented
queries' equivalent SQL `CASE` expressions (§7) and by any future UI badge
— a single source of truth, per spec.md §4's "no second, parallel record."

### 3.3 Evaluation cases (V3-5): new table `content.evaluation_cases`

| Field | Notes |
|---|---|
| id UUID PK | |
| category_slug text FK → content.categories.slug, nullable | nullable only for genuinely uncategorized probes (e.g. off-topic-abstention checks) |
| question text | the customer-style probe question |
| expected_status text (`ANSWER`\|`ABSTAIN`) | |
| expected_evidence_ids jsonb nullable | qa_id/chunk_id list expected to ground an `ANSWER`; null for expected-`ABSTAIN` cases |
| actual_status text nullable | filled in only when a reviewer manually re-checks the case against the live system — no automated re-run in V3 (spec.md §7) |
| actual_notes text nullable | free-form reviewer note |
| last_reviewed_at timestamptz nullable | |
| created_by_operator_id FK → operator_users.id | |
| created_at / updated_at timestamptz | |

Isolation from production metrics (acceptance outcome 5) is structural, not
a flag: `evaluation_cases` has no `conversation_id` and cannot spawn a
`Conversation` row, so it is mechanically impossible for V3-3/V3-4's
`ai_generations`/`conversations`-rooted queries to include it, and
mechanically impossible for a case to produce a customer-visible `Message`
(nothing here ever calls `generate_draft` against a real conversation).
Seeded from `teste_humano.md`'s findings via a minimal operator-authenticated
`POST/GET /operator/evaluation/cases` (new `customer_care.evaluation`
package, §2). No dedicated frontend screen is required by V3-5's acceptance
criteria — `tasks.md` decides whether a thin admin form is worth building.

### 3.4 Satisfaction survey (V3-12): new table
`customer_service.conversation_satisfaction_responses`

| Field | Notes |
|---|---|
| id UUID PK | |
| conversation_id FK → conversations.id, UNIQUE | one response per conversation; a missing row means "skipped," never backfilled to a default score |
| score smallint | 1–5, `CHECK (score BETWEEN 1 AND 5)` |
| resolved bool | "Sua necessidade foi resolvida?" |
| category_slug text FK → content.categories.slug, nullable | denormalized at submission time using §3.1's derivation, applied to the conversation's most recent `ANSWER` generation with a non-null `category_slug`; `NULL` if none exists |
| submitted_at timestamptz | |

No `operator_id` — customer-only per spec.md V3-12. Writable only through
the new public endpoint (§15), gated to `conversation.status == "CLOSED"`
server-side.

## 4. V3-1 — Operator feedback taxonomy

Approve/edit: already implemented (§1, §3.2) — no code change beyond
reading `ai.draft_accepted`/`ai.draft_edited` in the V3-4 queries. Search/
take-over/regenerate: already derivable (§3.2) — no code change.

Two new assignment-gated endpoints in `operator_workspace.router`, matching
the existing `claim`/`release`/`take-over` shape exactly:

- `POST /operator/conversations/{conversation_id}/generations/{generation_id}/mark-incorrect`
  — sets `marked_incorrect_at`/`marked_incorrect_by_operator_id`; idempotent
  (re-marking updates the timestamp); `record_event(..., "generation.marked_incorrect", ...)`.
- `POST /operator/conversations/{conversation_id}/generations/{generation_id}/escalate`
  — same shape; `record_event(..., "generation.escalated", ...)`.

Both validate `generation.conversation_id == conversation_id` (422
otherwise, matching `send_operator_message`'s existing
`INVALID_GENERATION` pattern) and are reachable from **any** generation in
the conversation's history the frontend renders, not only the latest one
(spec.md V3-1 resolution).

## 5. V3-2 — Quick-approve action

No backend change (§1). Frontend: `OperatorPage` gains an "Aprovar" button
next to the existing reply box, visible whenever a `latest_generation` with
`status == "ANSWER"` exists; it calls the existing
`POST /operator/conversations/{id}/messages` with
`{body: draft.draft_text, source_generation_id: draft.id, citation_retrieval_hit_ids: []}`.
One addition needed for the 409 staleness guard spec.md V3-2 implies
("acts on one generation at a time"): `send_operator_message` gains a
check — if `payload.source_generation_id` is set and does not equal the
conversation's current `latest_generation_dict(...).id`, return `409
STALE_GENERATION`. This protects every send-from-a-generation path (quick-
approve and an edited send from the reply box alike), not just quick-approve.

## 6. V3-3 — Human Correction Rate

No dedicated endpoint — implemented purely as documented SQL (§7), per
spec.md's resolution. Formula (spec.md V3-3, now literal SQL):

```sql
-- share of sent generations that were edited, overall or by category
SELECT
  category_slug,
  COUNT(*) FILTER (WHERE audit.event_type = 'ai.draft_edited')::numeric
    / NULLIF(COUNT(*) FILTER (WHERE audit.event_type IN ('ai.draft_edited', 'ai.draft_accepted')), 0)
    AS human_correction_rate
FROM ai_generations g
JOIN audit_events audit
  ON audit.payload_json->>'ai_generation_id' = g.id::text
 AND audit.event_type IN ('ai.draft_edited', 'ai.draft_accepted')
GROUP BY category_slug;
```

## 7. V3-4 — First read-only management metrics

Documented, versioned SQL only — no new endpoint, no new frontend route
(spec.md resolution; dashboard UI deferred to V4's supervisor interface).
Lives at `docs/metrics/v3_queries.sql`, extending `teste_humano.md`'s
existing manual work, each query parameterizable by date range and
optionally `category_slug`:

1. abstention rate overall/by category (`ai_generations.status = 'ABSTAIN'`
   share, `category_slug` grouped, including the `NULL`/"sem categoria" row);
2. Human Correction Rate overall/by category (§6);
3. generation volume by `trigger`/`category_slug`;
4. V3-12 average score and resolved-rate overall/by category, from
   `conversation_satisfaction_responses`.

"Read-only enforced server-side, not just omitted from the UI" (acceptance
outcome 4) holds by construction: there is no write endpoint anywhere in
this surface to disable — the queries are read-only SQL files, not an API.

## 8. V3-5 — Evaluation datasets/suites tied to category

Covered in §3.3. `GET /operator/evaluation/cases` (list, filterable by
`category_slug`), `POST /operator/evaluation/cases` (create). No automated
re-run mechanism (spec.md §7) — `actual_status`/`actual_notes`/
`last_reviewed_at` are set by a `PATCH /operator/evaluation/cases/{id}`
call a reviewer makes after manually checking the case, mirroring how
`teste_humano.md`'s manual review already worked.

## 9. V3-6 — Regenerate-with-instruction

`DraftIn` (`ai/router.py`) gains `instruction_text: str = ""`.
`generate_draft(...)` gains an `instruction_text: str = ""` parameter,
stored on the new column (§3.2), and — when non-empty — appended to
`history` as one additional entry with `role: "operator_instruction"`
(never `role: "customer"`) immediately before calling
`provider.generate(history, qa_evidence, prompt.content)`. This is additive
only: `GenerationProvider.generate`'s existing
`history: list[dict[str, str]]` signature (`ai/providers.py`) is unchanged,
so `DeterministicTestGenerationProvider` and `OpenAIGenerationProvider` both
just see one more history row — no provider-interface break.
`prompts/rag_answer.md` gains one short paragraph telling the model an
`operator_instruction`-role entry is operator steering, not customer
speech, and should be followed without ever being echoed into `draft_text`.

Audited exactly like `manual_search_text` already is: the existing
`ai.draft_generated`/`ai.draft_abstained` event payload
(`generate_draft`'s `record_event` call) gains `"instruction_text"`
alongside the fields it already logs — no new event type.

Frontend: `OperatorPage`'s draft panel gains a free-text "Instrução para
regenerar" box next to the existing manual-search box, sent as
`instruction_text` on the next `/drafts` call together with whatever
message-selection/manual-search-text state is already set (combined, not
replacing, per spec.md's resolution).

## 10. V3-7 — Clear/reset control for draft and evidence search

Pure frontend. `OperatorPage` gains a "Limpar" button that resets the local
draft state and evidence-search-results state to empty, independent of the
existing message-selection state (`desmarcar conversas`, V2-4, untouched).
No new endpoint, no new audit event (spec.md's resolution: pure client-side
reset, no server-side "dismissed" record).

## 11. V3-8 — Guided knowledge-CRUD inputs (`/operator/knowledge`)

- **Category**: `GET /operator/knowledge/categories` (list `{slug, label}`,
  active only) and `POST /operator/knowledge/categories` (create; same
  `/operator/knowledge/*` auth as the rest of this module) in
  `knowledge/router.py`, backed by §3.1's registry. `KnowledgeAdminPage`'s
  free-text `category` `<input>` becomes a `<select>` populated from the
  list endpoint, plus an inline "criar nova categoria" affordance calling
  the create endpoint.
- **Table dropdown**: `GET /operator/knowledge/dynamic-tables` returns
  `list(ALLOWLISTED_TABLES.keys())` (`knowledge/dynamic_binding.py`) — the
  dropdown reads the allowlist directly, so it can never diverge from it.
- **Column introspection**: `GET /operator/knowledge/dynamic-tables/{table}/columns`.
  Resolved 2026-08-18 to **live** introspection: for the allowlisted model
  (`ALLOWLISTED_TABLES[table][0]`), use `sqlalchemy.inspect(model).columns`
  (equivalently `model.__table__.columns`) to list column names/types at
  request time. This satisfies the spec's "live `information_schema`"
  decision — it can never drift from the actual mapped schema — while
  staying strictly scoped to the allowlist dict, never a raw
  `information_schema.columns` query against an arbitrary table name; that
  is a **stronger** safety property than literal `information_schema` SQL
  would give for the same allowlist guarantee, and is the reason this plan
  implements the decision this way rather than with raw SQL. 404 if `table`
  is not in `ALLOWLISTED_TABLES`. `Filtro`/`Colunas de saída` become
  multi-select/key-value builders populated from this response instead of
  hand-typed JSON. `knowledge/router.py`'s existing `validate_binding` is
  unchanged and remains the authoritative server-side check (carried over
  from V2's data-model note) — the guided UI reduces how often it fires, it
  does not replace it.
- **"Transformar em Q&A"** (ties V3-1's `edit` tag to this outcome): a new
  button on any generation classified `edit` opens `KnowledgeAdminPage`'s
  existing create-entry form pre-filled — `question` = the customer message
  the generation answered (`AIGeneration.triggering_message_id` →
  `Message.body`; for `MANUAL_EVIDENCE`/no-triggering-message generations,
  the latest customer message in the conversation, the same fallback
  `select_evidence` already uses), `answer_markdown` = the sent
  `Message.body`, `category` = the generation's `category_slug` if set. No
  new endpoint — a frontend-only pre-fill; the actual create still goes
  through the existing `POST /operator/knowledge/qa`, so the operator's
  explicit-confirm requirement (acceptance outcome 9a) is enforced by the
  existing create flow, not a new one.

## 12. V3-9 — Automatic-draft countdown indicator

`operator_conversation_detail`, `claim`, and `take_over`'s response dicts
(`operator_workspace/router.py`) gain two fields, computed from the same
clock `evaluate_automatic_trigger` (`ai/router.py`) already reads:

- `automatic_draft_eligible: bool` — true iff there is customer activity not
  yet covered by a generation, i.e. `conversation.last_customer_activity_at`
  is set and the newest `CUSTOMER` message is newer than
  `auto_draft_covers_through_message_id`'s message — mirroring
  `evaluate_automatic_trigger`'s own guard exactly (resolved 2026-08-18:
  shown only when eligible, not continuously);
- `automatic_draft_seconds_remaining: int`, present only when eligible —
  `max(0, AUTOMATIC_TRIGGER_IDLE_SECONDS - elapsed_seconds)`.

`AUTOMATIC_TRIGGER_IDLE_SECONDS` is already exposed via
`GET /operator/runtime-config` — not duplicated.

Frontend: `OperatorPage` ticks a local `setInterval` countdown between the
existing 2-second polls, resynced from `automatic_draft_seconds_remaining`
on every poll response — the same resync pattern already used for
`is_customer_typing`. At 0, the UI shows a "gerando…" state (not "0") until
the next poll's `latest_generation`/`automatic_draft_eligible: false`
confirms the generation landed, per spec.md's "known imprecision" note.

## 13. V3-10 — Scroll to top on evidence selection

Pure frontend. The `onSelect` handler already passed into the evidence-list
`<article>` component (`main.tsx`, the "Selecionar" button) additionally
calls `window.scrollTo({ top: 0, behavior: "smooth" })`, invoked only
inside that click handler — never inside a `useEffect` keyed on
poll-refreshed state — so the 2-second poll's unrelated re-renders can
never re-trigger it (acceptance outcome 11).

## 14. V3-11 — Confirm before closing a conversation

Pure frontend on both pages. `CustomerPage.close` and
`OperatorPage.closeConversation` each gain a `confirmingClose` local-state
step rendering spec.md's resolved copy ("Deseja encerrar a conversa?" /
"Encerrar conversa" / "Retornar e continuar conversa") before their
existing `close()`/`closeConversation()` calls fire. No backend/API change
— `POST /public/conversations/{id}` and
`POST /operator/conversations/{id}/close` are called exactly as today, one
click later. Choosing "Retornar e continuar conversa" only resets the local
`confirmingClose` flag — no request is sent, so no partial side effect is
possible by construction (acceptance outcome 12).

## 15. V3-12 — Post-conversation satisfaction survey

New endpoint `POST /public/conversations/{conversation_id}/satisfaction` in
`anonymous_access/router.py`, using the existing `token_bound_conversation`
dependency (no new customer-auth mechanism). Body: `{score: int (1-5),
resolved: bool}`.

- 409 `NOT_CLOSED` if `conversation.status != "CLOSED"`.
- 409 `ALREADY_SUBMITTED` if a response row already exists (the table's
  `UNIQUE(conversation_id)` is the actual guarantee; the check gives a
  clean error instead of a raw constraint violation).
- Computes `category_slug` per §3.1's denormalization.
- `record_event(session, "conversation.satisfaction_submitted", "CUSTOMER", conversation_id=..., payload={"score": ..., "resolved": ..., "category_slug": ...})`
  — matching the existing pattern every other customer-facing write already
  follows (`conversation.created`, `conversation.closed`,
  `message.customer_received`); V3-12 does not introduce an exception to
  it.

Frontend: `CustomerPage`, after `close()` succeeds (post V3-11's
confirmation), renders the optional survey — 1-to-5 buttons with
green-to-red emoji, and "Sua necessidade foi resolvida?" Sim 🙂 / Não 🙁 —
with a visible dismiss/skip action that renders nothing further and sends
no request.

## 16. Frontend summary

All changes land in `frontend/src/main.tsx`:

- `CustomerPage`: close-confirmation step (V3-11), satisfaction survey
  (V3-12).
- `OperatorPage`: quick-approve button (V3-2), mark-incorrect/escalate
  buttons on history (V3-1), regenerate-with-instruction box (V3-6),
  clear/limpar button (V3-7), transformar-em-Q&A button (V3-1×V3-8),
  countdown indicator (V3-9), scroll-to-top on evidence selection (V3-10),
  close-confirmation step (V3-11).
- `KnowledgeAdminPage`: category `<select>` + create-new (V3-8), table
  dropdown (V3-8), filter/output-column guided builders (V3-8).

## 17. API contract summary

New:

- `POST /operator/conversations/{id}/generations/{generation_id}/mark-incorrect`
- `POST /operator/conversations/{id}/generations/{generation_id}/escalate`
- `GET /operator/knowledge/categories`, `POST /operator/knowledge/categories`
- `GET /operator/knowledge/dynamic-tables`
- `GET /operator/knowledge/dynamic-tables/{table}/columns`
- `GET /operator/evaluation/cases`, `POST /operator/evaluation/cases`,
  `PATCH /operator/evaluation/cases/{id}`
- `POST /public/conversations/{id}/satisfaction`

Changed:

- `DraftIn` (`POST /operator/conversations/{id}/drafts`): + `instruction_text`.
- `POST /operator/conversations/{id}/messages`: new `409 STALE_GENERATION`
  case when `source_generation_id` no longer matches the conversation's
  `latest_generation`.
- `operator_conversation_detail` / `claim` / `take_over` response dicts: +
  `automatic_draft_eligible`, `automatic_draft_seconds_remaining`.
- Generation dict (`generation_dict` in `ai/router.py`): + `category_slug`,
  `marked_incorrect_at`, `escalated_at`, `instruction_text`.

Removed: none.

## 18. Security

- Every new operator endpoint reuses `CurrentOperator` plus the same
  assignment-gating (`require_assignment`) every existing conversation
  action already uses — no new auth mechanism.
- The new public endpoint reuses `token_bound_conversation` — no new
  customer-auth mechanism; the raw token is still never persisted or
  logged (unchanged from V1/V2).
- Column introspection (V3-8) never accepts a client-supplied table name
  outside `ALLOWLISTED_TABLES` — same allowlist-first pattern
  `resolve_dynamic_pattern`/`validate_binding` already enforce; §11
  explains why this is stronger than literal `information_schema` SQL.
- Quick-approve cannot fire without `CurrentOperator` + assignment-gating +
  the `STALE_GENERATION` freshness check (§5) — there is no code path that
  reaches `send_operator_message` other than an explicit authenticated
  request, closing acceptance outcome 2's negative-test requirement.
- `instruction_text` gets the same non-customer-facing treatment
  `manual_search_text` already gets: present in operator/audit responses,
  never in any public/customer-facing response schema.
- `content.evaluation_cases` and
  `conversation_satisfaction_responses` do not expose or accept
  `dynamic_data_required`/allowlist-adjacent fields — no new attack surface
  on the dynamic-evidence mechanism.

## 19. Audit and traceability

New `audit_events.event_type` values: `generation.marked_incorrect`,
`generation.escalated`, `conversation.satisfaction_submitted`. No new event
type for quick-approve (already `ai.draft_accepted`) or
regenerate-with-instruction (already `ai.draft_generated`/
`ai.draft_abstained`, payload extended with `instruction_text`).

`classify_generation()` (§3.2) is the single function every V3-1
observability point — the two new endpoints, the V3-4 queries, and any
future UI badge — must call or mirror exactly; `tasks.md` must include a
test asserting the SQL `CASE` expressions in `docs/metrics/v3_queries.sql`
agree with `classify_generation()`'s Python logic for the same fixture
data, so the two representations cannot silently drift.

## 20. Testing implementation

- Migration tests: `content.categories` backfill preserves every distinct
  existing `qa_entries.category` **and** `documents.cancer_type` value with
  no data loss; the new FK rejects an unregistered category on
  `qa_entries`, `documents`, and `ai_generations`.
- `category_slug` derivation test: a clinical-parent-grounded `ANSWER`
  generation (`full_parent_draft` path) gets `category_slug` from the
  document's `cancer_type`, not left `NULL`.
- `classify_generation()` unit tests: one fixture per tag, asserting
  exactly the expected tag set — including a generation that is both
  `edit` and later `marked_incorrect` (independent, non-exclusive facts).
- Quick-approve: integration test proving `STALE_GENERATION` fires when a
  newer generation exists, and that `ai.draft_accepted` (not `_edited`) is
  recorded for an unmodified send.
- Regenerate-with-instruction: `DeterministicTestGenerationProvider` test
  asserting the `operator_instruction`-role history entry is passed through
  and never echoed into `draft_text`.
- Column-introspection endpoint: test asserting a non-allowlisted table
  name 404s and never reaches raw SQL.
- Satisfaction endpoint: `NOT_CLOSED`/`ALREADY_SUBMITTED` negative tests;
  positive test asserting `category_slug` denormalization matches the
  conversation's actual most-recent categorized generation.
- Frontend: scroll-to-top does not fire on an unrelated poll re-render
  (acceptance outcome 11); close-confirmation leaves conversation state
  untouched on cancel (acceptance outcome 12); countdown never goes
  negative after a backgrounded tab resumes (acceptance outcome 10).
- V1/V2 regression spot-check (acceptance outcome 7): rerun the existing
  send/close/take-over/draft-generation smoke paths unmodified.

## 21. Performance

No new hot path: mark-incorrect/escalate/satisfaction are low-frequency,
single-row writes; countdown fields are computed from data already loaded
for `evaluate_automatic_trigger`'s existing guard, adding no new query;
column introspection is a small, allowlist-bounded read with no pagination
concerns (at most a handful of allowlisted tables). V3-4's queries run
outside the request path entirely (ad hoc/reporting use), so they carry no
production latency budget.

## 22. Deliverables

- Migration(s) for §3.1–3.4.
- Backend changes per §4–15, §17.
- `docs/metrics/v3_queries.sql` (§7).
- Frontend changes per §16.
- `tasks.md` breaking all of the above into dependency-ordered, gated
  phases (categories/migration before anything that reads them; V3-1's
  derivation before V3-3/V3-4's queries; V3-8's endpoints before the
  transformar-em-Q&A frontend work that depends on them).
- `data-model.md` / `contracts/openapi.yaml` deltas over V2's (per this
  plan's §3/§17).
- `acceptance.md` covering spec.md §5's 13 outcomes as executable
  scenarios.
- `checklists/{requirements,security,traceability}.md`.
- `analysis.md` (cross-artifact convergence) before any V3 production code
  is written.

## 23. Prohibited shortcuts

- No parallel "approve"/"edit" record — `ai.draft_accepted`/
  `ai.draft_edited` remain the only source of truth (§1, §3.2).
- No raw `information_schema` SQL against an unscoped table name anywhere
  (§11, §18).
- No client-supplied category free text bypassing `content.categories` on
  either `qa_entries` or `ai_generations` (§3.1).
- No satisfaction submission accepted before a conversation is `CLOSED`
  (§15).
- No new background worker/scheduler for the countdown (§12) — it stays a
  client-side tick resynced from the existing poll, exactly like
  `is_customer_typing`.
- No V3 change weakens Article III: quick-approve, regenerate-with-
  instruction, and every other new action still terminate in the existing,
  single `send_operator_message`/`close`/`satisfaction` endpoints, each
  requiring one explicit authenticated actor per call.
