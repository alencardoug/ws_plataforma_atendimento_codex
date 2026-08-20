# Feature Specification: Customer-Facing Draft Status

**Feature ID:** `008-customer-facing-draft-status`
**Status:** Draft — authorized for specification 2026-08-20
**Authorized for specification:** 2026-08-20 (human, this conversation),
registered 2026-08-19 in `ROADMAP.md`
**Scope:** a generic, no-numbers "preparing a response" cue on the
customer's own tab while the existing automatic-draft mechanism (V2-7/V3-9)
is counting down — nothing else. See §6 for the deliberate scope limit
this spec keeps: manual "Gerar rascunho" clicks are **not** covered.

## 1. Purpose

The operator already sees "Respondendo em Ns…" / "Gerando resposta…"
(`frontend/src/main.tsx`, `OperatorPage`) while
`automatic_draft_eligible`/`automatic_draft_seconds_remaining`
(`automatic_draft_status()`, `app/customer_care/ai/router.py:469-487`)
report a pending automatic draft. `automatic_draft_status()`'s only current
caller is `automatic_draft_fields()` (`operator_workspace/router.py:70-71`),
itself spread only into operator-authenticated responses — confirmed by
direct inspection, no other call site exists. The customer sees nothing:
`GET /public/conversations/{id}` (`anonymous_access/router.py:72-74`)
returns only `customer_projection()`'s shared shape
(`id`/`status`/`messages`/`created_at`/`closed_at`,
`conversations/projections.py:23-38`), which has no draft-status field at
all, and `ConversationOut` (`shared/schemas.py:37-42`) doesn't declare one.
The human wants a customer-visible cue for this specific wait, so the
customer isn't left wondering whether their message was received.

## 2. Definitions

- **`preparing_response`** — this cycle's new customer-facing boolean.
  `true` for the same window `automatic_draft_eligible` is `true`
  operator-side (the whole 8-second debounce, not only its final instant)
  — never exposes the countdown number itself.
- Existing terms (`automatic_draft_status`, `AUTOMATIC_TRIGGER_IDLE_SECONDS`,
  `customer_projection`, N1/N2) are unchanged from V2/V3.

## 3. Functional requirements (CS)

### CS-1 — New computed-only field, reusing `automatic_draft_status()` verbatim

A new small function in `anonymous_access/router.py` (matching
`automatic_draft_fields()`'s own "compose on top of `customer_projection()`,
don't edit it" pattern — `customer_projection()` stays the function shared
with the operator router, unchanged):

```python
def customer_draft_status(session: DbSession, conversation: Conversation) -> dict:
    eligible, _seconds_remaining = automatic_draft_status(session, conversation)
    return {"preparing_response": eligible}
```

Reuses `automatic_draft_status()`'s existing eligibility computation
exactly — no duplicated logic, no new query. `_seconds_remaining` is
discarded inside this function, before it ever reaches a response model —
the countdown number itself never crosses into any `/public/*` response.

### CS-2 — `GET /public/conversations/{id}` gains the field

`ConversationOut` (`shared/schemas.py`) gains one new field,
`preparing_response: bool = False`. The public router composes it exactly
like `automatic_draft_fields()` already does operator-side:
`{**customer_projection(session, conversation), **customer_draft_status(session, conversation)}`.

### CS-3 — No leak beyond "is a response being prepared right now"

Confirmed by direct inspection of `automatic_draft_status()`: `eligible`
is unconditionally `False` whenever `conversation.effective_mode != "N2"`
— a customer reading `preparing_response=False` cannot distinguish "this
is an N1 conversation" from "this is N2 with nothing pending," so no
mode information leaks. No other field from `automatic_draft_status()`
(seconds remaining, trigger internals, whether an operator is assigned) is
exposed — `CS-1`'s function signature makes this structural, not just a
frontend-rendering choice.

### CS-4 — Frontend: generic cue, no numbers, rides the existing 2-second poll

`CustomerPage`'s existing `refresh()`/poll (`main.tsx`, `useEffect` already
refetching `CustomerConversation` every 2s) needs no new endpoint or timer
— `preparing_response` rides along on the response it already fetches.
`CustomerConversation` (frontend interface) gains
`preparing_response: boolean`. Rendered as one line using the existing
`typing-indicator` CSS class (matching the operator countdown's own visual
treatment, minus the countdown), placed near the message list/send-form
area — **not** to be confused with the pre-existing customer-typing cue at
the same visual class (`{text.trim().length > 0 && ... "Digitando…"}`,
`main.tsx`), which is about the *customer's own* typing state and is
unrelated to draft preparation; the two must never render simultaneously
in a way that's ambiguous about which is which (exact copy, e.g.
`"Preparando resposta…"`, distinct from "Digitando…").

## 4. What this cycle does **not** authorize

### CS-5 — Manual "Gerar rascunho" clicks stay uncovered — a deliberate scope limit, not an omission

`automatic_draft_status()`/`automatic_draft_eligible` reflect **only** the
automatic idle-trigger path (V2-7/V3-9). A manual draft generation
(operator clicking "Gerar rascunho", `generate_draft` called synchronously
inside the POST handler, `ai/router.py`) has no persisted in-progress flag
anywhere in the codebase today — confirmed by direct inspection — so there
is no existing signal this cycle could expose for that case without adding
a wholly new in-progress-tracking mechanism, which `ROADMAP.md`'s own
wording ("while an automatic draft is being prepared") never asked for.
**This cycle does not add one.** A customer may see no cue at all while an
operator is manually drafting a reply — expected, unchanged behavior.

### CS-6 — No other new exposure

No change to citation exposure, evidence content, retrieval scores, or any
other field `customer_projection()`/`ConversationOut` don't already carry.
No change to the operator-facing countdown (`OperatorPage`'s "Respondendo
em Ns…") — it keeps showing seconds, unchanged; only the customer-facing
cue is generic.

## 5. Data model impact

None. `preparing_response` is computed fresh from existing columns
(`conversation.status`, `effective_mode`, `last_customer_activity_at`,
`auto_draft_covers_through_message_id`) on every request — no new column,
no new table, no schema migration.

## 6. Acceptance outcomes to develop into executable tests

1. While an automatic-draft debounce window is active for an N2
   conversation with an assigned operator, `GET /public/conversations/{id}`
   returns `preparing_response: true`, and the customer's tab shows
   "Preparando resposta…" within one 2-second poll cycle.
2. Once the window elapses and the automatic draft actually generates (or
   the trigger condition clears), `preparing_response` returns to `false`
   and the cue disappears.
3. `GET /public/conversations/{id}}`'s response never contains a numeric
   seconds-remaining value, an operator-assignment fact, or an
   `effective_mode` value distinguishable via `preparing_response` alone —
   verified by direct response-schema inspection, not just visual absence.
4. An N1 conversation, or an N2 conversation with no operator assigned yet,
   always returns `preparing_response: false` — never leaks a stuck
   `true`.
5. A manual "Gerar rascunho" click produces no customer-facing cue change
   — regression-checked, confirming CS-5's scope limit holds.
6. The operator's own "Respondendo em Ns…"/"Gerando resposta…" countdown
   is pixel-for-pixel unchanged.
7. The full pre-existing `smoke_*` suite and `v1/v2/v3/v4/v5` Playwright
   suite continue passing unmodified.

## 7. Decisions resolved with the human (2026-08-20)

1. **Generic indicator only, no seconds** — chosen over replicating the
   operator's own numeric countdown, to avoid exposing internal
   debounce-timing/trigger mechanics to the customer (§3/CS-1, CS-3).
2. **Automatic-trigger path only** — manual draft generation stays
   uncovered rather than building a new in-progress-tracking mechanism
   this cycle wasn't asked to add (§4/CS-5).
