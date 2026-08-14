# Implementation Plan: V2 Commercial Product Experience

## 1. Technical summary

Evolve the V1 modular monolith in place — no new services, no message broker,
no WebSocket/scheduler infrastructure. V2 adds:

- a professional redesign of the existing React/TypeScript/Vite SPA (V2-1);
- a short, always-visible, record-keeping-only conversation token (V2-2);
- two independent operator-triggered evidence/generation actions, "Buscar
  evidências" and "Gerar rascunho" (V2-3, V2-7), alongside the existing
  automatic draft path, now debounced by customer typing activity;
- operator-selected conversation-message context with a documented default
  and clear-all control (V2-4);
- unchanged customer-ready drafting rules (V2-5), extended with the dynamic-
  evidence safety correction (V2-6);
- an authenticated knowledge-base CRUD screen (V2-8).

Same stack as V1: FastAPI + SQLAlchemy/Alembic + PostgreSQL 17/pgvector,
React/TypeScript/Vite, OpenAI adapters behind interfaces. All new behavior is
additive to V1's modules; no V1 module is replaced.

## 2. Module boundaries

Extends V1's module list; no renames.

```text
app/
  auth/
  anonymous_access/        # + short-token format, rate limiting
  conversations/           # + typing heartbeat, activity/debounce tracking
  autonomy/
  operator_workspace/      # + "Buscar evidências" as a distinct endpoint family
  knowledge/                # + CRUD service, dynamic-pattern binding + resolver
  rag/
  ai/                      # + typing-debounced automatic trigger, generation-trigger metadata
  audit/
  shared/
  infrastructure/
```

No new top-level module is introduced. The dynamic-pattern resolver (V2-6)
lives in `knowledge/` next to ingestion, since it queries structured tables
the same way ingestion reads source files — both are "bring external data
into a generation-safe form" concerns. Knowledge CRUD (V2-8) lives in
`knowledge/` for the same reason and reuses its existing re-embed-on-change
logic.

## 3. Persistence strategy and migrations

Forward-only Alembic migrations on top of V1's schema, same conventions
(explicit `customer_service` schema for new tables; `content.*` evolved in
place, never duplicated).

### 3.1 Token format (V2-2)

- `anonymous_access.security` generates an 8-character code from the alphabet
  `23456789ABCDEFGHJKMNPQRSTUVWXYZ` (digits and uppercase letters, excluding
  `0/O`, `1/I`, `L`; 31 symbols) — kept in one named constant so `plan.md`'s
  format decision has one source of truth. ~4.9×10^11 combinations.
- Persistence is unchanged in shape: only `anonymous_token_digest` (HMAC-
  SHA256, server pepper) is stored, per V1's existing column. No raw-token
  column is added — V2-2 is explicit that the token is not a recovery
  mechanism, so there is no requirement to look conversations up by token
  after issuance except through the existing digest-compare validation path.
- New: `conversations.token_validation_attempts` is **not** a persisted
  column — rate limiting is IP/source-keyed, not conversation-keyed (a
  conversation-keyed counter would let an attacker reset it by creating a new
  conversation). See §7.1 (Security) for the limiter design.

### 3.2 Conversation activity and generation triggers (V2-4, V2-7)

New columns on `conversations`:

| Field | Notes |
|---|---|
| `last_customer_activity_at` timestamptz nullable | updated on customer message send and on typing heartbeat |
| `last_customer_typing_at` timestamptz nullable | updated only by the typing heartbeat; used to compute the live "is typing" signal, separately from the debounce clock |
| `auto_draft_covers_through_message_id` FK nullable → `messages.id` | the newest customer message already covered by an automatic-trigger generation, so the same activity run is not re-triggered on every poll |

New table `customer_service.message_selections` (replaces no V1 table; V1 had
no persisted context-selection concept):

| Field | Notes |
|---|---|
| `id` UUID PK | |
| `ai_generation_id` FK → `ai_generations.id` | |
| `message_id` FK → `messages.id` | |
| `created_at` | |

Unique `(ai_generation_id, message_id)`. Populated for both trigger paths —
for the automatic path, from the resolved "latest consecutive customer-
message run since the last operator reply"; for "Gerar rascunho", from
whatever the operator had checked. This is what §4 of `spec.md` calls "a
generation's selected conversation-message IDs, stable ordering" — ordering
is derivable from each `messages.created_at`, so no separate ordinal column
is needed.

### 3.3 Generation trigger provenance

`ai_generations` gains:

| Field | Notes |
|---|---|
| `trigger` enum `AUTOMATIC` \| `MANUAL_DRAFT` \| `MANUAL_EVIDENCE` | which of V2-7/V2-3's paths produced it |
| `manual_search_text` text nullable | the manual-search box content used as input, if any (both `MANUAL_DRAFT` and `MANUAL_EVIDENCE` may set this) |

`MANUAL_EVIDENCE` generations (from "Buscar evidências") still populate the
existing `retrieval_run_id`/`ai_generation_sources` relations, scoped to the
single selected hit — no schema change needed there beyond what V1 already
has (a retrieval run may already yield a single-hit "generation" today when a
clinical parent is used as-is).

V1's `triggering_message_id` (previously `NOT NULL`) becomes **nullable**:
`MANUAL_EVIDENCE` generations have no single triggering customer message, so
it is null there. For `AUTOMATIC`/`MANUAL_DRAFT`, it continues to hold the
most recent selected customer message for quick display, while
`message_selections` (§3.2) is the authoritative full set for both.

### 3.4 Dynamic-evidence pattern (V2-6)

New table `content.qa_dynamic_bindings`:

| Field | Notes |
|---|---|
| `qa_id` FK → `content.qa_entries.qa_id`, unique | one binding per Q&A entry |
| `source_table` text | must match a key in the server-side table allowlist (§9.2) — never a raw identifier interpolated into SQL |
| `filter` jsonb | static `{column: value}` equality filter authored with the binding (e.g. `{"specialty": "Cardiologia", "availability": "positive"}`) |
| `output_columns` jsonb | ordered list of `{column, variable_name}` pairs mapping table columns to pattern placeholders |
| `row_limit` int default 4 | matches the existing "up to four offers" pattern already used in the V1 demo Q&A content |
| `created_at`/`updated_at` | |

`content.qa_entries.answer_markdown` continues to hold the pattern text with
`{{variable_name}}` placeholders for entries that have a binding; entries
without a binding are unaffected (plain markdown, as today).

`ai_generations` gains `dynamic_pattern_used` bool default false, so audit
and traceability can distinguish "the response is a resolved dynamic pattern"
from an LLM-composed answer without inspecting `draft_text` heuristically.

### 3.5 Knowledge CRUD (V2-8)

No new tables beyond §3.4's binding table — V2-8 is a UI/API surface over
the existing `content.documents`, `content.chunks`, `content.qa_entries`
(create/update/deactivate), not a new data model. "Delete" is implemented as
`is_active = false` (already an existing column on all three tables),
consistent with V1's existing soft-delete pattern and required to preserve
FK integrity for historical `ai_generation_sources`/`message_citations`
referencing already-used content.

## 4. Customer-visible token (V2-2)

- `POST /public/conversations` response includes the raw short token (as
  today) and a `token_display_format` hint if the frontend needs it — no
  contract change beyond the token's own shape (still an opaque string in
  the schema).
- The customer SPA renders the token continuously in the conversation header
  (no reveal/hide toggle) with a copy-to-clipboard action. No new
  authenticated read path — this is the same `access_token` value already
  returned once at creation and held in `sessionStorage`; V2 only changes
  what the UI does with a value it already has.
- No endpoint is added to "look up" or "resume" a conversation by token from
  a different tab/session — V2-2 is explicit that this is out of scope. The
  existing `Authorization: Bearer <token>` validation on `/public/*` routes
  is unchanged in mechanism, only in the token's length/alphabet.

## 5. "Buscar evidências" (V2-3)

New endpoint, additive to V1's existing (unchanged) `POST
/operator/knowledge/search`:

- `POST /operator/knowledge/evidence/{retrieval_hit_id}/select` — given a
  `retrieval_hit_id` from a prior `/operator/knowledge/search` call, performs
  the V1-equivalent decision deterministically:
  - `matched_kind == CLINICAL_CHILD` → returns the complete parent document
    (`clinical-parent-document` provenance, no LLM call), exactly like V1's
    existing full-parent shortcut in `ai/router.py`'s `full_parent_draft`,
    reused as a plain function call here (not re-implemented);
  - `matched_kind == ADMIN_QA` → if the entry has a §3.4 dynamic binding,
    resolves it per §9.2 (no LLM call); otherwise passes the Q&A content to
    the LLM for a concise adapted answer, reusing V1's existing
    `provider.generate` path with `qa_evidence` limited to this one hit.
  - Both branches persist an `ai_generations` row with `trigger =
    MANUAL_EVIDENCE`, and single-hit `ai_generation_sources`.
- Only one `retrieval_hit_id` may be selected per call — the endpoint takes a
  single ID, not a list, which structurally enforces V2-3's single-selection
  rule instead of relying on frontend discipline.
- This path never reads `message_selections` (§3.2) — it is independent of
  checked conversation messages, per V2-3/V2-4's explicit independence.

## 6. Operator-selected conversation context (V2-4)

- Every message in `OperatorConversationDetail.messages` gains no new
  required field for selection state — selection is a frontend-local
  checkbox state, submitted only at the moment of "Gerar rascunho" (as a list
  of message IDs), not persisted before then. This avoids a chatty
  selection-sync endpoint and matches V1's "avoid frontend-only enforcement"
  rule only where it matters (server always re-validates the submitted IDs
  belong to this conversation before using them — see §9.2).
- Default selection is computed **client-side** from data the frontend
  already has (the message list plus each message's `author_type`): the
  contiguous run of trailing `CUSTOMER` messages after the last `OPERATOR`
  message. "Desmarcar conversas" is a pure frontend action (clears local
  checkbox state); no endpoint needed.
- `GenerateDraftRequest` (manual path) changes from V1's single
  `triggering_message_id` to `selected_message_ids: UUID[]` (min 0) plus
  `manual_search_text: string` (may be empty). Server validates every ID
  belongs to the conversation and rejects (`422`) if both inputs are empty,
  per V2-4's explicit block-when-both-empty rule.

## 7. Draft generation triggers (V2-7)

### 7.1 Manual ("Gerar rascunho")

`POST /operator/conversations/{id}/drafts` (existing route, changed request
shape per §6) always runs the full RAG+LLM path with automatic chunk
selection — unchanged from V1's `generate_draft`, except the query text is
now built from `selected_message_ids` (joined message bodies, ordered by
`created_at`) concatenated with `manual_search_text` when both are present,
instead of a single triggering message. Persists `trigger = MANUAL_DRAFT` and
the `message_selections` rows.

There is no `/regenerate` endpoint in V2 for this path (V1's
`/operator/drafts/{id}/regenerate` is removed from the contract) — the
clarified decision is that re-invoking `/drafts` against the current
selection already regenerates; keeping a second route with identical
semantics would be redundant surface area.

### 7.2 Automatic/instant, 8-second debounce

No scheduler, no WebSocket — reuses V1's polling precedent (§12 of V1's
plan.md: "simple HTTP polling/refetch is sufficient... do not introduce
WebSocket/SSE solely for V1"; V2 keeps that principle and stretches it to
cover this feature instead of adding new infrastructure):

- `POST /public/conversations/{id}/typing` — a cheap heartbeat the customer
  client calls (debounced client-side to roughly every 2–3s) while the
  message box has focus and non-empty content. Updates
  `last_customer_typing_at` and `last_customer_activity_at`. Shares the same
  per-source token-validation limiter as other `/public/*` routes (§13.1);
  no separate higher-allowance limiter is needed since that limiter only
  penalizes failed validations — frequent heartbeats from a correct token
  never count against it.
- Every customer message send also updates `last_customer_activity_at`
  (already effectively "now" at insert time — no extra write).
- **The trigger check is lazy**, evaluated as a side effect of the existing
  operator conversation-detail poll (`GET
  /operator/conversations/{id}`, already polled roughly every 2s per V1) and
  of the typing heartbeat itself: if `now - last_customer_activity_at >= 8s`
  AND there exists a customer message newer than
  `auto_draft_covers_through_message_id` AND the conversation is active
  effective-N2, synchronously run the same generation path as §7.1 with
  `selected_message_ids` set to the consecutive customer-message run (§6's
  default), `trigger = AUTOMATIC`, and advance
  `auto_draft_covers_through_message_id` to the newest included message.
  This keeps the trigger's latency bounded by the operator's own poll
  interval, which is already well under 8s in practice, without a background
  worker.
- `is_customer_typing` (derived: `now - last_customer_typing_at <` a short
  grace window, e.g. 5s, to smooth over the ~2–3s heartbeat gaps) is added to
  `OperatorConversationDetail` so the operator UI can show a live indicator
  without a separate endpoint.
- No token-by-token streaming of `draft_text` — the draft is returned whole,
  same as V1.

## 8. Customer-ready generated drafts (V2-5)

Unchanged from V1's `ai/router.py` generation-strategy rules (highest-ranked
clinical → full parent; Q&A → concise LLM answer; no evidence → brief general
response or abstain) — V2-5 simply confirms these persist into V2. The only
addition is §3.4/§9.4's dynamic-pattern branch, which takes priority over the
plain-Q&A-to-LLM path when a selected/matched Q&A entry has a binding.

## 9. Dynamic-evidence safety correction (V2-6)

### 9.1 Authoring

A Q&A entry's `answer_markdown` may contain `{{variable_name}}` placeholders
when it has a `qa_dynamic_bindings` row (§3.4). Authored through V2-8's CRUD
screen — see §10 — never through the offline ingestion files alone (a
binding wired only in `documents/qa/qa-catalog.jsonl` with no
operator-facing edit path would defeat V2-8's purpose).

### 9.2 Resolution

In `knowledge/dynamic_binding.py` (new): given a `qa_id`, look up its
binding, resolve `source_table` against a **server-side allowlist mapping
table name → SQLAlchemy model** (not a raw string used to build SQL) —
e.g. `{"scheduling_availability": SchedulingAvailability}`. Build a
parameterized query: `SELECT <output columns> FROM <allowlisted model> WHERE
<filter equality columns> ORDER BY <a stable column, e.g. date/time> LIMIT
<row_limit>`. Never accept a table name, column name, or filter key from
anything other than the stored `qa_dynamic_bindings` row itself (which is
only writable through authenticated V2-8 CRUD, itself audited).

For each returned row, substitute `{{variable_name}}` per the
`output_columns` mapping into the pattern text; if `row_limit > 1`, the
plan's default rendering repeats the pattern once per row (the V1 demo
content's "up to four offers" phrasing already anticipates a multi-row
answer) and joins with a plan-defined separator. **Pinned during
implementation (tasks.md T073):** each row renders the full pattern
independently, joined with a blank line (`"\n\n"`).

**Implementation note:** the allowlist and resolver are proven against one
clearly-labeled, non-scheduling-flavored fixture table
(`content.knowledge_dynamic_fixture`) — no production Q&A entry is bound to
it. Every existing `dynamic_data_required=true` demo entry remains
unconfigured, which is the correct closure per §9.4: an unconfigured entry
and a configured-but-failing one fall back identically. See tasks.md Phase 7
for the full scope rationale.

### 9.3 Failure and fallback

Any of: no binding configured, allowlist miss, table/column mismatch, query
error, or zero matching rows — all fall back identically:

- the generation is persisted with `status = ABSTAIN`,
  `abstention_reason = DYNAMIC_DATA_UNAVAILABLE`, `dynamic_pattern_used =
  false`;
- an audit-only detail string (e.g. `"column nome_do_medico not found in
  table scheduling_availability"`, or `"no row matched filter"`) is recorded
  in the audit event payload — **never** in `draft_text` or any
  customer-visible field;
- the customer-facing behavior is V1's existing safe abstention: a short
  generic message inviting manual/operator follow-up, with no internal
  identifiers.

This closes both the original V1 finding and the "unconfigured entry" case
explicitly named during clarification — they are the same code path, not
two.

### 9.4 Scope

Only entries with `dynamic_data_required = true` **and** a `qa_dynamic_bindings`
row are affected. An entry with the flag but no binding behaves exactly like
§9.3's fallback (abstain, not literal passthrough) — this is what finally
retires the V1 finding: the flag alone no longer causes literal passthrough
under any configuration state.

## 10. Knowledge-base CRUD (V2-8)

New endpoints under `/operator/knowledge/qa` and
`/operator/knowledge/clinical-documents` (plus `/clinical-documents/{id}/chunks`
for children), all `operatorBearer`-secured, no new role:

- `POST`/`GET`/`GET {id}`/`PATCH {id}`/`DELETE {id}` (delete = `is_active =
  false`) for Q&A entries, including nested create/update of a
  `qa_dynamic_bindings` row;
- the same CRUD shape for clinical parent documents and their child chunks.

`PATCH`/`POST` on content that affects `answer_markdown`, `content_markdown`,
or a binding's `filter`/`output_columns` triggers the same re-embed-on-change
logic `customer_care.knowledge.ingest` already implements via content hash
comparison — this plan reuses that function rather than duplicating
embedding logic in the CRUD handlers. Every CRUD mutation emits an audit
event (`knowledge.qa_created`, `knowledge.qa_updated`,
`knowledge.qa_deactivated`, and the clinical-document equivalents), per the
constitution's traceability article.

## 11. Frontend

### 11.1 Customer

Builds on V1's customer SPA (§12 "Customer" subsection of V1's plan) with:

- professional visual redesign (V2-1) — design system, responsive/empty/
  loading/error states are `tasks.md`-level detail, not re-specified here.
  `accamargo.org.br` is a UX-pattern reference point per `spec.md` V2-1
  (tone/hierarchy/professionalism, not branding/content) — see `tasks.md`
  T100;
- always-visible token header with copy action (V2-2);
- a typing heartbeat call wired to the message input's change events,
  debounced client-side (§7.2).

### 11.2 Operator

Extends V1's three-pane layout. New elements:

- a checkbox on every message (V2-4), a "desmarcar conversas" control, and a
  manual-search text box shared by two distinct action buttons: **"Gerar
  rascunho"** (§7.1) and **"Buscar evidências"** (§5) — both disabled/inert
  when their required inputs are empty per V2-3/V2-4's rules;
- **"Usar sugestão"** to accept/send the current automatic-trigger draft
  (§7.2); no "Regenerar" control (§7.1);
- a live "cliente está digitando…" indicator driven by `is_customer_typing`
  (§7.2);
- a new authenticated screen (reachable from operator navigation, same
  session) for V2-8's knowledge CRUD, separate from the conversation
  workspace.

Real-time strategy stays polling-based (§7.2); no WebSocket/SSE is
introduced for V2, consistent with V1's precedent.

## 12. API contract changes (summary; `contracts/openapi.yaml` is canonical)

- `GenerateDraftRequest`: `triggering_message_id` → `selected_message_ids[]`
  + `manual_search_text`.
- New: `POST /public/conversations/{id}/typing`.
- New: `POST /operator/knowledge/evidence/{retrieval_hit_id}/select`.
- New: `POST/GET/PATCH/DELETE /operator/knowledge/qa[/{id}]`,
  `/operator/knowledge/clinical-documents[/{id}]`,
  `/operator/knowledge/clinical-documents/{id}/chunks[/{chunk_id}]`.
- Removed: `POST /operator/drafts/{generation_id}/regenerate` (§7.1).
- `OperatorConversationDetail`: adds `is_customer_typing`; `latest_generation`
  (already present in the schema, inherited from V1) is now actually
  populated — V1 declared but never implemented it, which V2 cannot leave
  as-is once an `AUTOMATIC` generation needs a way to reach the operator's
  browser with no direct API response of its own.
- `AIGeneration`: adds `trigger` and `dynamic_pattern_used`.
- Token schema note: `access_token` documented as the new short format;
  no field renamed.

## 13. Security

### 13.1 Token brute-force mitigation (V2-2)

Rate limit on the `/public/*` token-authenticated routes and on
`/public/conversations/{id}` lookups specifically: a sliding-window counter
keyed by source IP (and, where available, a secondary key such as a
per-client fingerprint header) rejecting with `429` beyond a configured
threshold (plan default: 30 failed token validations per IP per minute, then
exponential backoff up to a capped lockout window — exact numbers belong in
`tasks.md`/`data-model.md` as configuration, not hardcoded). Raised from an
initial 5 (human decision, 2026-08-14): with an 8-character/31-symbol token
(~4.9×10^11 combinations, `plan.md` §3.1), 30 failed attempts changes an
attacker's success odds negligibly, while 5 proved too easy to hit from
normal use (a customer mistyping/retrying a few times, or routine manual
testing) — the token's own entropy is the primary defense; this limiter is a
backstop against sustained automated guessing, not the first line of
defense. Successful validations do not count against the limiter. This is
required acceptance evidence (spec.md §5 item 8), with a negative test
proving lockout engages.

### 13.2 Server-side enforcement carried over from V1

- message-selection IDs, single-evidence-selection, and dynamic-binding
  resolution are all re-validated/executed server-side regardless of what
  the frontend sends (§6, §5, §9.2);
- the dynamic-binding table allowlist (§9.2) is the only way a binding can
  reach the database — never a free-form identifier from config or request
  body;
- V2-8 CRUD requires the same `operatorBearer` authentication as the rest of
  the operator surface; no anonymous or customer-token path can reach it.

## 14. Audit and traceability

New event types (added to `docs/architecture/EVENT_CATALOG.md` before
implementation): `conversation.typing_heartbeat` is **not** audited (too
frequent, no product-facing decision); `ai.draft_generated` gains `trigger`
in its payload; `ai.dynamic_pattern_resolved` and
`ai.dynamic_pattern_fallback` (carries the audit-only cause string, §9.3);
`knowledge.qa_created`/`updated`/`deactivated`,
`knowledge.clinical_document_created`/`updated`/`deactivated`,
`knowledge.clinical_chunk_created`/`updated`/`deactivated`;
`anonymous_access.token_validation_rate_limited`.

`message_selections` (§3.2) rows are themselves the durable record of
exactly which message IDs a generation used — the traceability model in
`spec.md` §4 is satisfied by this table plus existing
`ai_generation_sources`, without needing to duplicate selection into the
audit payload.

## 15. Testing implementation

Same approach as V1 (§14 of V1's plan): real PostgreSQL/pgvector for
integration tests, deterministic fake AI/embedding adapters for logic tests,
a separately marked real-provider smoke test. New areas needing explicit
coverage:

- negative tests for the token rate limiter (lockout engages, resets
  correctly, does not block legitimate customers);
- `qa_dynamic_bindings` resolution: success (single row, multi-row), each
  §9.3 failure mode individually, and a negative test proving the audit-only
  cause string never appears in `draft_text` or any customer-facing
  response;
- the lazy 8-second trigger: fires once per activity run (not per poll),
  covers the correct accumulated message set across multiple bursts, and
  does not fire while `last_customer_typing_at` is recent;
- "Buscar evidências" single-selection enforcement and its independence from
  `message_selections`;
- V2-8 CRUD: authorization (existing operator only), re-embed-on-change,
  soft-delete (`is_active`) instead of hard delete, and audit coverage.

## 16. Performance

No premature optimization, per V1's precedent. The 8-second lazy trigger
adds negligible cost to the existing operator poll (one extra timestamp
comparison); the typing heartbeat is a single indexed-row upsert. Dynamic-
pattern resolution is a single indexed, filtered, `LIMIT`-bounded query —
expected well under the existing ~10s demo-condition draft-generation
target.

## 17. Deliverables

- migrations for §3.1–§3.5;
- updated `contracts/openapi.yaml` per §12;
- updated seed/ingestion tooling if V2-8 CRUD needs a companion CLI path for
  bulk authoring (bulk import is not itself a V2 requirement; the CRUD
  screen is the primary path);
- updated `.env.example` for any new rate-limit configuration variables;
- updated quickstart covering the knowledge CRUD screen and token format
  change;
- acceptance evidence per `spec.md` §5's expanded list.

## 18. Prohibited shortcuts

Everything in V1's plan §17 still applies. V2 adds:

- resolving a dynamic-pattern binding's table/column via anything other than
  the server-side allowlist (no dynamic SQL built from stored or request
  strings);
- exposing the §9.3 audit-only failure cause to the customer in any form;
- persisting a raw token anywhere, regardless of the shorter format;
- a background scheduler/worker or WebSocket/SSE channel to implement the
  8-second trigger or the typing indicator — both must work through the
  lazy, poll-driven mechanism in §7.2;
- treating `message_selections` as authorization — server must still verify
  every selected message belongs to the conversation and the requesting
  operator is assigned to it;
- allowing V2-8 CRUD to bypass the existing content-hash/re-embed idempotency
  rules ingestion already enforces.
