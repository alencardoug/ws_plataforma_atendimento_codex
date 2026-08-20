# Feature Specification: Two-Phase Clinical Evidence Selection

**Feature ID:** `009-two-phase-clinical-evidence`
**Status:** Draft — authorized for specification 2026-08-20
**Authorized for specification:** 2026-08-20 (human, this conversation),
registered 2026-08-19 in `ROADMAP.md` ("Registered for a future SDD round —
two-phase clinical evidence: child chunk first, parent on demand")
**Scope:** the operator's "IA e evidências" sidebar shows a clinical child
chunk's matched excerpt only, never its full parent document, until the
operator explicitly clicks a new "Trazer documento" action on that chunk —
for both manual-search evidence and automatic-draft evidence, which this
cycle also unifies onto one shared rendering. See §6 for what stays
untouched: the automatic LLM-generation/reranking pipeline itself, and the
backend response shape.

## 1. Purpose

Today, direct inspection of `frontend/src/main.tsx` confirms every clinical
hit's full parent document is shown **up front, by default**, with no
gating step:

- `ManualEvidence` (`main.tsx:128-130`) renders `evidence.content` (the
  full parent document's entire text for a `CLINICAL` hit —
  `rag/service.py:75`'s `Evidence(..., parent.content_markdown or
  matched.content_markdown, matched.content_markdown, ...)` already sets
  `content` to the full parent and `matched_child_excerpt` to the child's
  own text, in the same object, for every `CLINICAL` evidence item) via
  `<MessageBody body={evidence.content} />`, then *additionally* shows
  `matched_child_excerpt` right below it under a "Trecho encontrado"
  label — both fields, simultaneously, with one "Selecionar" button.
- Manual-search evidence (`searchEvidence`, populated by `search()` calling
  `POST /operator/knowledge/search`) is the only evidence with any
  selection mechanism at all — each item renders via `ManualEvidence` with
  `onSelect` wired to `selectEvidence(item.retrieval_hit_id)` →
  `POST /operator/knowledge/evidence/{retrieval_hit_id}/select`
  (`ai/router.py`'s `select_evidence()`).
- Automatic-draft evidence (`draft.evidence`, populated whenever a draft is
  generated — idle-triggered or via "Gerar rascunho") has **no** selection
  mechanism: `main.tsx:694` renders each item as an inert
  `<small className="message-citation">{item.title}</small>` label next to
  the already-composed `draft_text`. The only action available for the
  whole draft is the single "Usar sugestão"/"Usar documento completo"
  button (`useDraftLabel`, `main.tsx:622`) that copies `draft.draft_text`
  into the reply textarea.

`select_evidence()` (`ai/router.py:387-440`) already handles both cases
generically by `retrieval_hit_id` alone — it calls `load_evidence()`
(`rag/service.py:94`), which reconstructs the exact same `Evidence` object
regardless of whether that hit originally came from a manual search or an
automatic draft's own retrieval run, then dispatches through
`full_parent_draft()`/`dynamic_pattern_result()`/the LLM path exactly as
today. **No backend change is required for selection itself** — confirmed
by this inspection, matching `ROADMAP.md`'s own resolved note that hiding
the parent is a frontend-only concern.

## 2. Definitions

- **Two-phase clinical card** — this cycle's new rendering for a `CLINICAL`
  evidence item: phase one shows only `title`/`section`/
  `matched_child_excerpt` and a **"Trazer documento"** button; phase two
  (after that click) additionally shows the full `content` in an expanded
  card with its own selection action.
- **Candidate card** — the unified rendering this cycle introduces for one
  evidence item, replacing both `ManualEvidence` (search-only) and the
  inert `<small>` citation label (draft-only) with one shared component
  used by both `searchEvidence` and `draft.evidence`. An `ADMIN_QA` item is
  always a single-phase candidate card (unchanged from `ManualEvidence`'s
  existing behavior — shows `content` immediately, one "Selecionar"
  button). A `CLINICAL` item is always a two-phase clinical card.
- Existing terms (`Evidence`, `knowledge_type`, `matched_child_excerpt`,
  `select_evidence`, `RetrievalHit`, N1/N2) are unchanged from V1/V2/V3 and
  `.specify/memory/constitution.md`.

## 3. Functional requirements (EV)

### EV-1 — Clinical evidence renders child-excerpt-only by default, everywhere

For every `CLINICAL`-typed evidence item, in both `searchEvidence` and
`draft.evidence`, the candidate card shows `title`, `section` (if present),
and `matched_child_excerpt` — **never** `content` — until "Trazer
documento" is clicked for that specific card. This is a hard constraint:
no code path renders a clinical parent's full text before that explicit
click, for any evidence source. `ADMIN_QA` items are unaffected — they keep
rendering `content` immediately, matching `ManualEvidence`'s existing
behavior exactly (a Q&A entry has no parent/child distinction to gate).

### EV-2 — "Trazer documento" reveals the full parent, unmodified

Clicking "Trazer documento" on a clinical card expands that same card (or
renders an adjacent expanded card) showing the full `content` field already
present in the payload — no new API call, no new endpoint, no
re-fetch — the value was already fetched by `search()`/the draft-generation
call and simply not rendered until now. This card gets its own selection
button, reusing the exact same `selectEvidence(retrieval_hit_id)` call and
`select_evidence()` backend endpoint the pre-existing "Selecionar" action
already uses — no new selection semantics, matching the existing
select-then-draft-substitution behavior byte-for-byte.

### EV-3 — Automatic-draft evidence becomes selectable, using the same candidate card

`draft.evidence` (currently rendered as inert `<small>` labels,
`main.tsx:694`) is rendered with the same candidate-card component as
`searchEvidence` (`main.tsx:697`) — an `ADMIN_QA` item gets an immediate
"Selecionar" button; a `CLINICAL` item gets EV-1/EV-2's two-phase
treatment. Selecting any of these items calls the same
`selectEvidence(retrieval_hit_id)` already used for manual-search
selection — `select_evidence()`'s existing generic-by-`retrieval_hit_id`
design (§1) requires no change to support this.

### EV-4 — The automatic LLM-suggestion action is unchanged and not gated

The existing "Usar sugestão"/"Usar documento completo" button
(`useDraftLabel`, copying `draft.draft_text` into the reply textarea) and
the draft-generation/reranking pipeline that produces `draft.draft_text`
(D-034's clinical-deflection reranker included) are **unchanged** by this
cycle. EV-3 adds per-evidence-item candidate cards *alongside* this
existing whole-draft action — it does not replace, hide, or require an
extra click before the operator can still use the LLM's own composed
suggestion exactly as today.

### EV-5 — Scroll behavior: "Selecionar" now scrolls to the send button; "Trazer documento" scrolls to the top

This is a deliberate change to V3-10's existing behavior. Today,
`selectEvidence()`'s success handler (`main.tsx:588-593`) always calls
`window.scrollTo({ top: 0, behavior: "smooth" })` after any selection. This
cycle **moves** that top-of-page scroll onto the new "Trazer documento"
click handler instead (so revealing a long parent document starts the
operator back at the page top to read it), and changes every
"Selecionar" click (whichever kind of candidate card) to instead scroll to
the reply-send button/textarea (`main.tsx:666`'s `#operator-reply`), since
selecting now more often happens after the operator has already scrolled
down to read a revealed parent or a draft panel, and the next action is
always sending. Both remain client-side-only, fired inside their own click
handler (matching V3-10's own "not inside a poll-refreshed `useEffect`"
discipline, `main.tsx:589-591`), never a new bespoke `useEffect`.

### EV-6 — `ADMIN_QA` evidence unaffected beyond unification

`ADMIN_QA` items in both `searchEvidence` and `draft.evidence` keep their
existing immediate-content, single-"Selecionar" rendering exactly as
`ManualEvidence` already provides — EV-3 only changes which list (search
vs. draft) uses that rendering, not the rendering itself for this
knowledge type.

## 4. Data model impact

None. `Evidence`/`RetrievalHit`/`select_evidence()`/`load_evidence()` are
all unchanged (§1 confirms both `content` and `matched_child_excerpt` are
already computed and already present in every existing response payload —
this is a rendering-gate change only). No new column, table, migration, or
endpoint. No new response field on `GET .../drafts`, `POST
/operator/knowledge/search`, or `POST .../evidence/{id}/select`.

## 5. Acceptance outcomes to develop into executable tests

1. A manual search returning a `CLINICAL` hit shows only
   `matched_child_excerpt` (plus title/section) initially — the full parent
   `content` never appears in the rendered DOM until "Trazer documento" is
   clicked (verified by DOM inspection, not just visual absence — the
   value must not be present at all pre-click, matching EV-1's "never
   renders" wording, distinct from "hidden via CSS").
2. Clicking "Trazer documento" on that same hit reveals the exact,
   unmodified `content` value already present in the fetched response — no
   new network request fires.
3. An automatic draft whose top evidence is `CLINICAL` shows that item as a
   two-phase candidate card (not an inert `<small>` label) with a working
   "Trazer documento" → "Selecionar" flow, while the draft panel's own
   "Usar documento completo"/"Usar sugestão" button and `draft_text` are
   unchanged.
4. An automatic draft whose evidence includes an `ADMIN_QA` item shows a
   directly selectable candidate card for it (not an inert label);
   selecting it calls the existing `select_evidence()` endpoint and
   produces the same generation-substitution behavior manual-search
   selection already produces today.
5. Clicking any "Selecionar" button (search-originated, draft-originated,
   `ADMIN_QA`, or a revealed clinical parent) scrolls the reply textarea
   into view; clicking "Trazer documento" scrolls to the top of the page —
   verified by asserting the correct target receives focus/scroll, not
   just that some scroll occurred.
6. The full pre-existing `smoke_*` suite and `v1/v2/v3/v4/v5` Playwright
   suite continue passing unmodified — in particular, D-013/D-014's
   clinical parent-context-expansion guarantee (the parent remains
   reachable and unmodified when selected) still holds, now reached via one
   additional explicit click for clinical content instead of by default.
7. No backend endpoint, response schema, or database migration changes —
   verified by an empty `alembic` migration diff and unmodified
   `contracts/openapi.yaml` for this feature.

## 6. What this cycle does **not** authorize

- Any change to `rag/service.py`'s retrieval/ranking, `providers.py`'s
  `rerank_clinical` (D-034), or `prompts/rag_answer.md` — this is a
  frontend rendering-gate and unification change only.
- Any change to `select_evidence()`, `load_evidence()`, `full_parent_draft()`,
  or `dynamic_pattern_result()` — all confirmed unchanged by §1's
  inspection; every code path this feature adds is a *new frontend caller*
  of the existing endpoint, never a new endpoint or altered backend
  branch.
- Any new endpoint, response field, migration, or table.
- Any change to how `draft_text` itself is composed, or to the
  D-034 clinical-deflection reranking step that competes against it —
  EV-4 is explicit that this stays untouched.
- Extending this two-phase gating to non-clinical evidence, or to any
  citation shown on an already-sent customer message (`message.body`'s own
  rendering, `main.tsx:656`) — this cycle is scoped to the operator's
  pre-send "IA e evidências" sidebar only.

## 7. Decisions resolved during specification (2026-08-20)

1. **One shared candidate-card component for both `searchEvidence` and
   `draft.evidence`**, resolving the open question left by `ROADMAP.md` —
   chosen because `select_evidence()` already treats both sources
   identically by `retrieval_hit_id` (§1), so no backend distinction exists
   to preserve; keeping two separate frontend renderings would be pure
   duplication for behavior that is already unified server-side.
2. **Card-type rule keyed on `evidence.knowledge_type` alone** (`ADMIN_QA`
   → single-phase, `CLINICAL` → two-phase) — resolves the open "exact
   rendering rule" question from `ROADMAP.md`; no new marker or backend
   field is needed because every `CLINICAL` evidence item already carries
   both `content` and `matched_child_excerpt` simultaneously (`rag/
   service.py:75`), and every `ADMIN_QA` item never has a parent to gate.
3. **"Selecionar" now scrolls to the send button; "Trazer documento" takes
   over the top-of-page scroll** — a deliberate, in-spec repurposing of
   V3-10's existing scroll-on-select behavior (§5/EV-5), not an oversight;
   matches the human's own explicit request order (`ROADMAP.md`: "clicking
   any 'Selecionar' button... scrolls to the send button; clicking 'Trazer
   documento' scrolls to the top of the page").
4. **No regression to D-013/D-014** — confirmed structurally: EV-2 reveals
   the exact same `content` field the backend already returns, unmodified,
   so the parent-context-expansion guarantee is preserved by construction,
   not by a new test alone.
