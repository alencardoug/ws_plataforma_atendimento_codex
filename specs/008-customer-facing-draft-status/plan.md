# Implementation Plan: Customer-Facing Draft Status

Governing spec: `spec.md`. Constitution: `.specify/memory/constitution.md`
(unchanged — spec.md §4/§6).

## 1. Technical summary

One backend computed field, composed onto `GET /public/conversations/{id}`
exactly as CS-1/CS-2 specify; one frontend field + one rendered cue. No
migration, no new endpoint.

## 2. Module boundaries

- `app/customer_care/anonymous_access/router.py` — add
  `customer_draft_status()` (spec.md CS-1, verbatim) and compose it into
  `read_conversation()` only (`GET /public/conversations/{id}` — the
  endpoint `CustomerPage`'s poll actually calls). `create_conversation()`
  and `close_conversation()` are left returning `customer_projection()`
  alone: `ConversationOut.preparing_response`'s Pydantic default (`False`)
  is already correct for both (a just-created conversation has no
  `last_customer_activity_at` yet; a just-closed one is never N2-ACTIVE) —
  computing it explicitly there would be redundant, not a correctness
  requirement, and spec.md CS-2 scopes the composition to the one GET
  endpoint by name.
- `app/customer_care/shared/schemas.py` — `ConversationOut` gains
  `preparing_response: bool = False`.
- **No call to `evaluate_automatic_trigger()` is added.** Confirmed by
  reading `automatic_draft_status()`'s docstring and
  `evaluate_automatic_trigger()`'s own docstring
  (`ai/router.py:469-522`): the "callers must call this after
  evaluate_automatic_trigger" contract is about same-request ORM
  freshness after a mutation (the operator router calls
  `evaluate_automatic_trigger()` immediately before, in the same request,
  because that call may itself mutate `auto_draft_covers_through_message_id`).
  `read_conversation()` performs no mutation — it reads whatever the DB's
  last-committed state already is, which reflects the most recent
  operator-poll or customer-typing-heartbeat evaluation regardless. Adding
  a trigger-evaluation call here would make a plain `GET` request
  side-effecting (able to itself launch a generation), which spec.md never
  asks for and would be a new, undiscussed trigger path — out of scope
  (spec.md §4 "no new column... no schema migration" implies no new
  behavior path either).
- `frontend/src/main.tsx` — `CustomerConversation` gains
  `preparing_response: boolean`; `CustomerPage` renders the new cue.

## 3. Frontend placement (resolves spec.md CS-4's "near the message
list/send-form area" instruction concretely)

Rendered as its own line, directly after the `<section className="messages">`
block and before the `<form>` (`main.tsx:360-361`) — deliberately not
sharing the existing "Digitando…" `<span>` (`main.tsx:365`, next to the
send button) so the two can never occupy the same visual slot or be
mistaken for each other, satisfying spec.md CS-4's explicit
non-ambiguity requirement structurally (different DOM location), not just
by copy difference:

```tsx
{conversation?.preparing_response && <p aria-live="polite" className="typing-indicator">Preparando resposta…</p>}
```

## 4. Persistence

None (spec.md §5, confirmed).

## 5. Test plan

- Backend (`app/tests/test_*`): `customer_draft_status()` returns
  `{"preparing_response": True}` when `automatic_draft_status()` reports
  eligible, `False` otherwise; `GET /public/conversations/{id}`'s response
  never contains `seconds_remaining`/any other `automatic_draft_status()`
  internal (outcome 3); an N1 conversation or one with no assigned
  operator always returns `False` (outcome 4).
- Frontend (`main.test.tsx`): `CustomerPage` renders "Preparando
  resposta…" only when `preparing_response: true`, distinct from and
  non-overlapping with the "Digitando…" cue.
- Playwright (new `frontend/e2e/v8.spec.ts`, continuing the v4/v5/v9
  package-number naming convention): an idle N2 conversation with an
  assigned operator and a fresh customer message shows the cue on the
  customer's tab within one poll cycle after the 8-second debounce window
  opens, and it disappears once the automatic draft actually lands;
  a manual "Gerar rascunho" click produces no customer-facing change
  (outcome 5, regression-checking CS-5); the operator's own
  "Respondendo em Ns…"/"Gerando resposta…" countdown is pixel-for-pixel
  unchanged (outcome 6).

## 6. Risks

- **Risk:** confusing the new cue with "Digitando…" if both could render
  together for the same customer at the same time (e.g., operator drafting
  while the customer is also typing a follow-up). **Mitigation:** they are
  gated on independent conditions (`preparing_response` vs. `text.trim()`
  length) and rendered in different DOM locations (plan.md §3) — both can
  be visible simultaneously, which is honest (both things are true at
  once), and their distinct positions/copy prevent misreading one as the
  other.
