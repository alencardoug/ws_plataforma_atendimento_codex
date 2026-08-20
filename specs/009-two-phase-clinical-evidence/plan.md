# Implementation Plan: Two-Phase Clinical Evidence Selection

Governing spec: `spec.md`. Constitution: `.specify/memory/constitution.md`
(unchanged by this feature — see spec.md §6).

## 1. Technical summary

Frontend-only. One new shared React component replaces two existing
renderings (`ManualEvidence`, used only by `searchEvidence`; the inert
`<small>` citation label, used only by `draft.evidence`) with one
`EvidenceCandidate` component used by both lists. `ADMIN_QA` items keep
today's single-phase behavior; `CLINICAL` items gain a two-phase reveal.
Backend is untouched — confirmed by spec.md §1/§4 direct inspection:
`select_evidence()` already dispatches on `retrieval_hit_id` alone,
independent of which list (search or draft) the operator picked from.

## 2. Module boundaries

- `frontend/src/main.tsx` — the only file touched.
  - Replace `ManualEvidence` (`main.tsx:128-130`) with a new
    `EvidenceCandidate` component (same file, exported the same way
    `ManualEvidence` was, since `main.test.tsx` may import it directly —
    confirmed by checking existing imports in `main.test.tsx` before
    removing the old export name, per tasks.md T3).
  - `OperatorPage`'s render (`main.tsx:675-699`) changes two call sites:
    `searchEvidence.map(...)` (`main.tsx:697`) and the inert
    `draft.evidence.map(...)` label (`main.tsx:694`) both switch to
    `EvidenceCandidate`.
  - `selectEvidence()` (`main.tsx:582-593`) changes its post-select scroll
    target from `window.scrollTo({ top: 0, ... })` to focusing/scrolling
    `#operator-reply` into view (EV-5). A new `bringDocument(retrievalHitId:
    string)` local per-card state (not a server call) toggles a card's
    "parent revealed" flag and performs the top-of-page scroll V3-10
    originally gave to selection.
- No other file changes. No new backend module, no new endpoint, no new
  migration (spec.md §4).

## 3. Persistence

None. See spec.md §4.

## 4. `EvidenceCandidate` component design

```tsx
function EvidenceCandidate({
  evidence, onSelect, revealed, onReveal,
}: {
  evidence: Evidence;
  onSelect?: () => void;
  revealed: boolean;
  onReveal: () => void;
}) {
  const isClinical = evidence.knowledge_type === "CLINICAL";
  const showFull = !isClinical || revealed;
  return <article className="evidence-item">
    <strong>{evidence.title}</strong>
    {evidence.section && <small>Seção: {evidence.section}</small>}
    {isClinical && !showFull && evidence.matched_child_excerpt && <>
      <small>Trecho encontrado</small>
      <MessageBody body={evidence.matched_child_excerpt} />
      <button type="button" className="btn-secondary" onClick={onReveal}>Trazer documento</button>
    </>}
    {showFull && <>
      <MessageBody body={evidence.content} />
      {isClinical && evidence.matched_child_excerpt && <>
        <small>Trecho encontrado</small>
        <MessageBody body={evidence.matched_child_excerpt} />
      </>}
      {onSelect && <button type="button" onClick={onSelect}>Selecionar</button>}
    </>}
  </article>;
}
```

Design notes:

- `revealed`/`onReveal` are lifted to the parent (`OperatorPage`) as a
  `Set<string>` of revealed `retrieval_hit_id`s (`revealedEvidenceIds`),
  matching the existing `selectedMessageIds`/`markedIncorrectIds` pattern
  already used for other per-item toggle state in this same component —
  not local `useState` inside `EvidenceCandidate` itself, so the reveal
  state survives whichever list re-renders the card (e.g. a poll refresh
  replacing `draft` with an equivalent object) without collapsing back to
  hidden. Cleared by `clearDraftAndSearch()` (`main.tsx:598-604`) alongside
  `searchEvidence`/`draft`, matching that function's existing "reset
  everything AI/evidence-related" scope.
- `showFull` for a non-clinical (`ADMIN_QA`) item is always `true` —
  reproduces `ManualEvidence`'s exact current behavior for that type
  (EV-6), just renamed.
- `onSelect` stays optional exactly as `ManualEvidence`'s did (`main.tsx:697`
  passes `undefined` when `!aiEligible`) — `EvidenceCandidate` used for
  `draft.evidence` also gates `onSelect` on `aiEligible`, matching the
  existing gate already applied to `searchEvidence`.
- `onReveal` has no `aiEligible` gate — reading a document is not a
  send-adjacent action, matching spec.md's framing of "Trazer documento"
  as inspection, not selection (§1/§2).

## 5. `OperatorPage` call-site changes

```tsx
// state
const [revealedEvidenceIds, setRevealedEvidenceIds] = useState<Set<string>>(new Set());
const revealDocument = (id: string) => {
  setRevealedEvidenceIds((prev) => new Set(prev).add(id));
  window.scrollTo({ top: 0, behavior: "smooth" });
};

// draft.evidence — was: {draft.evidence.map((item) => <small ...>{item.title}</small>)}
{draft.evidence.map((item) => <EvidenceCandidate
  key={item.retrieval_hit_id}
  evidence={item}
  revealed={revealedEvidenceIds.has(item.retrieval_hit_id)}
  onReveal={() => revealDocument(item.retrieval_hit_id)}
  onSelect={aiEligible ? () => void selectEvidence(item.retrieval_hit_id).catch((caught) => setError(errorMessage(caught))) : undefined}
/>)}

// searchEvidence — was: <ManualEvidence ... />
{searchEvidence.map((item) => <EvidenceCandidate
  key={item.retrieval_hit_id}
  evidence={item}
  revealed={revealedEvidenceIds.has(item.retrieval_hit_id)}
  onReveal={() => revealDocument(item.retrieval_hit_id)}
  onSelect={aiEligible ? () => void selectEvidence(item.retrieval_hit_id).catch((caught) => setError(errorMessage(caught))) : undefined}
/>)}
```

`selectEvidence()` itself (`main.tsx:582-593`) drops its own
`window.scrollTo({ top: 0, ... })` call and instead does:

```tsx
document.getElementById("operator-reply")?.scrollIntoView({ behavior: "smooth", block: "center" });
```

(`#operator-reply` is the existing reply `<textarea>` id, `main.tsx:666` —
already present, no markup change needed there.)

## 6. Test plan

- **Frontend unit/component** (`frontend/src/main.test.tsx`, Vitest):
  - a `CLINICAL` evidence item renders `matched_child_excerpt` and a
    "Trazer documento" button, and does **not** render `content` in the
    DOM (EV-1, acceptance outcome 1);
  - clicking "Trazer documento" renders `content` and a "Selecionar"
    button, with no new `fetch` call recorded (EV-2, outcome 2);
  - an `ADMIN_QA` item renders `content` and "Selecionar" immediately,
    unchanged from today (EV-6);
  - `draft.evidence` items render as `EvidenceCandidate` (both types),
    not as inert `<small>` labels (EV-3, outcome 3/4).
- **Playwright E2E**: update the existing V3-10 test in
  `frontend/e2e/v3.spec.ts` ("selecting evidence scrolls to top...") — its
  scenario searches "horário de atendimento" (an `ADMIN_QA` hit) and
  clicks "Selecionar" directly; per EV-5 this must now assert the reply
  textarea scrolls into view, not that `window.scrollY` returns near 0.
  Rename the test to reflect the corrected behavior and note inline that
  this is a deliberate, in-spec change (linking `009-two-phase-clinical-
  evidence`), not a regression of V3-10 itself. Add a new
  `frontend/e2e/v9.spec.ts` (continuing the existing v4/v5 smoke-script
  package-number-not-product-version naming convention set by
  `smoke_v4_appointment_availability.py`/`smoke_v5_guided_booking.py` for
  packages 004/005) covering: a clinical search hit shows child-excerpt-
  only by default; "Trazer documento" reveals the parent and scrolls to
  top; selecting the revealed parent scrolls to the reply textarea; an
  automatic draft's evidence list is selectable.
- No new backend test needed (spec.md §4/§7 outcome 7 — verified instead by
  an empty `alembic`/`openapi.yaml` diff, checked at `tasks.md`'s final
  task).

## 7. Risks and mitigations

- **Risk:** `revealedEvidenceIds` state leaking across conversations if
  the operator switches conversations without it clearing. **Mitigation:**
  scope it exactly like `searchEvidence`/`draft` — cleared by
  `clearDraftAndSearch()` and also whenever a new conversation is
  `open()`-ed (matching how `setDraft(null)`/`setSearchEvidence([])`
  already reset on `open()`/`closeConversation()`, `main.tsx:548,570` —
  `tasks.md` adds `setRevealedEvidenceIds(new Set())` at the same call
  sites).
- **Risk:** changing `selectEvidence()`'s scroll target could surprise an
  operator relying on V3-10's original top-scroll muscle memory.
  **Mitigation:** explicitly decided and documented (spec.md §7 decision
  3, `DECISIONS.md` D-039) — not an oversight; acceptance outcome 5 tests
  the new behavior directly.
