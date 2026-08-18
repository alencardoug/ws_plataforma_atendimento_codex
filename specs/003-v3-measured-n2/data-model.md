# V3 Data Model

This is a delta over `specs/002-v2-commercial-product-experience/data-model.md`
(itself a delta over V1's), both of which remain canonical for every
table/field not listed here. Names are conceptual; implementation naming may
vary if semantics remain exact. See `plan.md` §3 for the rationale behind
each change.

## 1. `content.categories` (new table)

Formal registry replacing the previously ungoverned free-text taxonomy
shared by administrative Q&A and clinical-site classification. See `plan.md`
§3.1 for the 2026-08-18 correction that folds `content.documents.cancer_type`
into this same registry alongside `content.qa_entries.category`.

| Field | Notes |
|---|---|
| slug text PK | stable identifier; existing free-text values become slugs verbatim on migration |
| label text | display label, independently editable from the slug |
| is_active bool default true | soft-delete, matching `content.documents`/`content.chunks`/`content.qa_entries`'s existing convention |
| created_at timestamptz | |

Backfilled from `DISTINCT content.qa_entries.category UNION DISTINCT
content.documents.cancer_type` (both non-null). New rows are created either
through V3-8's "create new category" path (administrative) or by whoever
authors a new `cancer_type` fixture (clinical) — the write path for each
source is unchanged from today, both now FK-governed into this table.

`content.documents.care_phase` (the ~16-value treatment-phase taxonomy) is
**not** folded into this registry for V3 (resolved 2026-08-18 — a separate,
finer-grained axis than `category`'s intended granularity); a future V may
add it as an independent breakdown facet.

## 2. `content.qa_entries` (changed)

| Field | Notes |
|---|---|
| category text, **now FK → content.categories.slug** | name/type/NOT NULL unchanged; gains a governing FK |

## 3. `content.documents` (changed)

| Field | Notes |
|---|---|
| cancer_type text nullable, **now FK → content.categories.slug** | name/type/nullability unchanged; gains a governing FK |

## 4. `ai_generations` (new columns)

| Field | Notes |
|---|---|
| instruction_text text nullable | V3-6's free-text steering instruction; set only on a regenerate-with-instruction call |
| category_slug text FK → content.categories.slug, nullable | derived once at generation-completion time (`plan.md` §3.1); `NULL` for `ABSTAIN`/`FAILED` and for evidence-free `ANSWER`s |
| marked_incorrect_at timestamptz nullable | V3-1, retroactive, independent of approve/edit |
| marked_incorrect_by_operator_id FK → operator_users.id, nullable | |
| escalated_at timestamptz nullable | V3-1, redefined — content-gap signal, not routing (`spec.md` V3-1) |
| escalated_by_operator_id FK → operator_users.id, nullable | |

No column added for **approve**/**edit** — both remain fully derived from
the existing `ai.draft_accepted`/`ai.draft_edited` audit events
(`send_operator_message`'s existing `edited = generation.draft_text !=
payload.body` computation, unchanged since V1/V2). No column added for
**search**/**take-over**/**regenerate** — all three remain fully derivable
from `trigger`, `conversation.taken_over_at`, and `prior_generation_id`
respectively (`spec.md` V3-1, `plan.md` §3.2).

## 5. `content.evaluation_cases` (new table)

| Field | Notes |
|---|---|
| id UUID PK | |
| category_slug text FK → content.categories.slug, nullable | nullable only for genuinely uncategorized probes |
| question text | the customer-style probe question |
| expected_status text (`ANSWER`\|`ABSTAIN`) | |
| expected_evidence_ids jsonb nullable | qa_id/chunk_id list; null for expected-`ABSTAIN` cases |
| actual_status text nullable | set only by a reviewer's manual re-check — no automated re-run in V3 |
| actual_notes text nullable | |
| last_reviewed_at timestamptz nullable | |
| created_by_operator_id FK → operator_users.id | |
| created_at / updated_at timestamptz | |

No FK from this table into `conversations` or `ai_generations`, and no FK
from any `customer_service` table into this table — isolation from
production metrics (`spec.md` acceptance outcome 5) is structural, not a
flag (`plan.md` §3.3).

## 6. `customer_service.conversation_satisfaction_responses` (new table)

| Field | Notes |
|---|---|
| id UUID PK | |
| conversation_id FK → conversations.id, UNIQUE | one response per conversation; a missing row means "skipped," never backfilled |
| score smallint | 1–5, `CHECK (score BETWEEN 1 AND 5)` |
| resolved bool | "Sua necessidade foi resolvida?" |
| category_slug text FK → content.categories.slug, nullable | denormalized at submission time from the conversation's most recent `ANSWER` generation with a non-null `category_slug`; `NULL` if none |
| submitted_at timestamptz | |

No `operator_id` — customer-only (`spec.md` V3-12). Writable only through
`POST /public/conversations/{id}/satisfaction`, gated to
`conversation.status == "CLOSED"` server-side.

## 7. Fields deliberately not added

- No `is_synthetic`/`is_test` flag on `conversations` or `ai_generations`
  for V3-5's evaluation isolation — `content.evaluation_cases`'s structural
  absence of any FK path into production tables makes such a flag
  unnecessary (§5).
- No server-side "draft dismissed" event for V3-7's clear/reset — resolved
  2026-08-18 as pure client-side state (`plan.md` §10); HCR/V3-1 metrics do
  not distinguish "generated and discarded" from "never generated" for V3.
- No new operator role/permission table for the new mark-incorrect/escalate/
  evaluation-case/category-create actions — all reuse the existing
  `operator_users` authentication as-is, same as V2-8's knowledge CRUD did.
- No `care_phase` column added to `content.categories`'s registry (§1) — out
  of scope for V3 by explicit 2026-08-18 resolution.

## 8. Constraints and integrity notes

- `content.categories.slug` values must be unique across both source
  taxonomies (administrative and clinical) — the backfill's `UNION` already
  deduplicates identical strings; a genuine naming collision between an
  administrative topic and a clinical site (unlikely given their differing
  vocabularies, but not structurally prevented) resolves to a single shared
  category. `tasks.md` T011 must verify no such collision exists in current
  seed data before the migration is treated as safe to run as-is.
- `ai_generations.category_slug`'s derivation (`plan.md` §3.1) reads
  `ai_generation_sources` → `retrieval_hits` → `qa_entries`/`documents` at
  generation-completion time only; it is never recomputed retroactively if
  a `qa_entries.category` or `documents.cancer_type` value changes later —
  historical generations keep the category that was true when they were
  created, matching how every other snapshotted fact in this system already
  behaves (e.g. `message_citations.display_title`, V1 data-model.md §10).
- `conversation_satisfaction_responses.conversation_id` UNIQUE is the actual
  enforcement for "one response per conversation" — the endpoint's
  `ALREADY_SUBMITTED` check is a clean error in front of it, not a
  substitute for it.
- `content.evaluation_cases.expected_evidence_ids` values are not
  foreign-keyed to `qa_entries`/`chunks` (a jsonb list, not a relation) —
  acceptable because this table is reference/documentation data for manual
  review, not a live-integrity-checked production path; `tasks.md` T074
  covers testing its traceability instead.
