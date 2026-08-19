# Feature Specification: Dynamic Pricing and Guided Booking Selection

**Feature ID:** `005-dynamic-pricing-and-guided-booking`
**Status:** Draft — authorized for specification 2026-08-19
**Authorized for specification:** 2026-08-19 (human, this conversation)
**Scope:** a real `price_lookup` resolver reusing feature 004's existing
pricing data; a content correction for the `preco`/`pagamento` Q&A
categories to stop describing behavior the system doesn't have; and a new
embedding-assisted guided-selection layer (slot choice, booking
confirmation) that stays entirely inside the existing N2 draft/explicit-send
model — see §6 for the exact constitutional boundary this cycle does
**not** cross.

## 1. Purpose

`teste_humano.md` §6.2 (2026-08-19) documented that three Q&A categories —
`preco`, `pagamento`, `convenio` — are marked `dynamic_data_required=true`
but have no resolver, so they always abstain: the same problem `agenda` had
before feature 004. Reading the actual seeded content
(`content.qa_entries`, QA-025..037) shows this is not one uniform problem:

- **`preco` (QA-025/026/027)** ask for a specific specialty's price
  ("Quanto custa uma consulta de mastologia?"). This is genuinely
  per-query dynamic — and feature 004 already built the exact data source
  needed: `scheduling.professional_specialties.fixed_price_cents`, a fixed
  price per specialty (confirmed identical across all professionals within
  one specialty in the seeded data). `booking_script/service.py`'s
  `lookup_recent_specialty_price()` already reads this same column for
  AA-10's price line — this feature adds the missing *retrieval-triggered*
  path, it does not invent a new price source.
- **`preco` (QA-028/029/030)** and all of **`pagamento`
  (QA-031/032/033/034)** ask general policy questions ("O preço muda
  conforme o horário?", "Receberei comprovante?") that do not need a
  per-query lookup at all — they were over-flagged with
  `dynamic_data_required=true` the same way several `agenda` entries were
  before AA-3a corrected the pattern. Worse, the four `pagamento` answers
  describe a payment mechanism that was never built (a fake
  `www.pagamento_fictico...` link with a 3-second auto-confirmation timer)
  and directly contradicts the payment step AA-10 actually shipped (a
  sim/não question inside the booking script). This is a real content
  defect, not just a coverage gap: if these ever resolved, they would tell
  the customer something false about how the system behaves.
- **`convenio` (QA-035/036/037)** is explicitly out of scope for this
  cycle (human decision, 2026-08-19) — stays exactly as it is today
  (abstaining), deferred to future work alongside real insurance data.

Separately, the human raised a genuinely new capability during this
cycle's authorization conversation: today, `resolve_appointment_availability`
(004, AA-2) returns up to 4 candidate slots as one rendered text block, and
AA-10's booking script only starts from a customer message matching a fixed
keyword list (`detect_booking_intent`) — there is no step where the
customer picks *which* of the 4 offered slots they want, and no step where
the system explicitly asks the customer to confirm before anything
proceeds. The human wants both of those steps added, with the
interpretation of the customer's free-text reply (which slot, and
sim/não) assisted by embeddings — but **explicitly decided (2026-08-19,
this conversation) that this assistance must stay inside N2**: it produces
an internal draft an operator still must explicitly send, exactly like
every other AI-assisted draft in the system. It does not extend Constitution
Amendment 1.1.0's autonomous-send exception, which remains scoped only to
AA-10's original fixed CPF/payment script, unchanged. See §6.

## 2. Definitions

- **Guided booking selection (GB)** — this cycle's new capability: after
  the customer sees up to 4 candidate slots, help them pick one and confirm
  intent to proceed, via embedding-assisted interpretation of their free
  text, always producing an operator-reviewable draft.
- **Presented offer** — one of the (at most 4) `schedule_slots` rows
  rendered and shown to the customer by a resolved `appointment_availability`
  generation, now durably recorded (§7) so a later customer reply can be
  matched against it.
- Existing terms (`dynamic_resolver`, `NAMED_RESOLVERS`, `AA-*`,
  `dynamic_data_required`, N1/N2, `AIGeneration`, explicit operator send)
  are unchanged from V1-004 and `.specify/memory/constitution.md`.

## 3. Functional requirements — pricing (PL)

### PL-1 — `price_lookup` as a second named resolver

`app/customer_care/ai/router.py`'s `NAMED_RESOLVERS` allowlist (AA-1's
pattern) gains a second entry: `"price_lookup": resolve_price_lookup`.
Every other still-unimplemented `dynamic_resolver` value
(`payment_simulator`, `insurance_lookup`) remains absent from the allowlist
and therefore keeps abstaining exactly as today — this cycle does not
authorize them (`payment_simulator` is superseded by §4's content
correction; `insurance_lookup`/`convenio` stays deferred, §6).

### PL-2 — Deterministic specialty-only extraction, reusing AA-3

`resolve_price_lookup(session, query_text)` reuses
`scheduling.availability.extract_parameters()` for its specialty match only
(the same deterministic keyword table, including the AA-3a generalist
default — asking "quanto custa uma consulta?" with no specialty named
prices the generalist consultation, not an error). Date/period extraction
is irrelevant here and ignored.

### PL-3 — Read-only, single-row lookup, never LLM-composed

The resolver issues one `SELECT` against
`scheduling.professional_specialties` joined to `scheduling.specialties`
on the extracted specialty slug, `LIMIT 1` (price is identical across
professionals within a specialty in the seeded data — confirmed via direct
query 2026-08-19; the resolver does not assume this will always hold and
takes the first row deterministically by a stable order, not an arbitrary
one). Writes nothing, ever — same invariant as AA-2. Output is a fixed
Python-rendered template (specialty name, formatted price via the existing
`format_price_brl()`, approximate duration from
`appointment_duration_minutes`) — never an LLM paraphrase, matching AA-5's
precedent.

### PL-4 — Manual fallback on no pricing row

If the extracted specialty has no `professional_specialties` row (should
not happen against the seeded data, since all 4 specialties are priced),
the resolver raises `DynamicResolutionError` and the existing
`ABSTAIN`/`DYNAMIC_DATA_UNAVAILABLE` path handles it — same as every other
resolver failure (AA-8's precedent). No new fallback mechanism.

## 4. Content correction — `preco` and `pagamento` (PM)

### PM-1 — Only the 3 genuinely dynamic `preco` entries stay dynamic

QA-025/026/027 keep `dynamic_data_required=true` and
`dynamic_resolver='price_lookup'` (already set in seed data). Their
`question`/`answer_markdown` text is reviewed for retrieval quality (the
embedding indexes `question + "\n" + answer`, per
`knowledge/ingest.py::qa_content_hash`'s pairing — so wording changes here
affect retrieval, not just display) but the *customer-facing* text always
comes from PL-3's Python template, never from `answer_markdown` — matching
how `agenda`'s AA-1..AA-9 entries already work today (their `answer_markdown`
is descriptive/internal, never rendered verbatim to a customer either).

### PM-2 — The other 3 `preco` entries become static

QA-028/029/030 ("O preço muda conforme o horário?", "O valor inclui
exames?", "Posso pagar depois da consulta?") get
`dynamic_data_required=false` and a rewritten `answer_markdown` that is
directly, unconditionally true regardless of which specialty/slot is being
discussed (no `{{variable}}`, no resolver, no per-query lookup) — the same
"always-true static rewrite" pattern `teste_humano.md` §6.2 already
documented as an available option. Exact wording is an implementation-time
editorial task (`tasks.md`), constrained only by: no specific price
figures (that's PL-3's job), no reference to a mechanism that doesn't
exist.

### PM-3 — All 4 `pagamento` entries become static and accurate

QA-031/032/033/034 get `dynamic_data_required=false` and rewritten
`answer_markdown` describing what the system *actually* does: payment
confirmation happens as a sim/não question inside the booking-confirmation
conversation (AA-10's existing `AWAITING_PAYMENT` step,
`booking_script/service.py`), not a clickable link. The fictional
`www.pagamento_fictico...`/3-second-timer content is removed, not
preserved alongside a caveat — it describes a mechanism this system has
never had. `QA-033`'s security guidance ("never send real card details in
chat") is preserved verbatim in spirit — it remains correct and worth
keeping regardless of the underlying mechanism.

### PM-4 — `convenio` untouched

QA-035/036/037 are not edited by this cycle. They keep
`dynamic_data_required=true`, no resolver, and continue abstaining exactly
as today (human decision, 2026-08-19).

## 5. Functional requirements — guided booking selection (GB)

### GB-1 — Presented offers become a durable, generation-linked fact

Whenever `resolve_appointment_availability` (AA-2) successfully produces a
non-empty result, the specific `schedule_slots` rows it offered (up to 4,
already the existing `LIMIT 4`) are persisted as new rows tied to the
`AIGeneration` that carries them — specialty, professional, unit,
`starts_at`/`ends_at`, price, and their 1-based display order exactly as
shown to the customer. This is the new fact this feature adds to the data
model (§7) — everything about *which* slots were actually shown must be
reconstructable later without re-running the resolver (whose live query
could return different rows by the time the customer replies).

### GB-2 — Slot-choice interpretation, embedding-assisted, draft-only

When an operator generates a draft (manually via "Gerar rascunho" or
automatically via the existing V2-7 idle trigger) for a conversation whose
most recent customer message follows a GB-1 offer set with no confirmed
selection yet, generation takes a new branch instead of (not in addition
to) ordinary RAG composition: it embeds the customer's message with the
same `EmbeddingProvider` already used for retrieval (`rag/service.py`),
compares it by cosine similarity against each presented offer's own
description text (embedded once, at GB-1 persistence time — not
re-embedded per attempt), and treats the highest-similarity offer above a
fixed confidence threshold as the customer's selection. This is
classification against a small, closed, already-known set of candidates —
not open-ended text generation — so no LLM call is used or needed here;
"embedding" is the literal mechanism, not a stand-in for "LLM" (matching
the human's "LLM ou embedding" framing — embedding alone is sufficient and
keeps this fully deterministic given a fixed model/input, same
determinism-preference precedent as AA-5/D-028's "no LLM rewrite" rule,
extended here to interpretation as well as composition, since nothing about
that rule was meant to apply only to output text).

The resulting `AIGeneration` (status `ANSWER`, `dynamic_pattern_used=true`,
a new `trigger` value or reuse of the existing dynamic-pattern audit shape
— `plan.md` decides the exact mechanism) has fixed, Python-rendered
`draft_text` restating the selected offer's specifics and asking exactly
one question: whether the operator should send a request to confirm the
booking. **It is a draft like any other** — nothing sends automatically,
the operator reviews and explicitly sends or edits, same as every existing
draft path.

### GB-3 — Below-confidence match aborts to the existing manual/abstention path

If no presented offer's similarity clears the confidence threshold (the
customer's reply doesn't clearly match any of the 4, e.g. "nenhuma dessas
serve" or an unrelated message), generation falls back to ordinary RAG
composition instead — it does not force a wrong selection and does not
invent a 5th option. This mirrors AA-8's "never fabricate, fall back to
the existing safe path" precedent, adapted from data-lookup failure to
classification-confidence failure.

### GB-4 — Confirmation-intent interpretation, embedding-assisted, draft-only

Once GB-2 has produced a sent (operator-approved) confirmation-question
message and the customer replies, the next draft-generation call for that
conversation takes a second new branch: it classifies the customer's reply
as affirmative/negative/unclear by embedding-similarity against a small,
fixed set of canonical affirmative/negative reference phrases (not a
regex list — this is the one piece of interpretation logic in this feature
that genuinely benefits from embeddings' generalization over free
phrasing, unlike GB-2's closed 4-candidate set, which a regex could not
handle at all). An affirmative classification produces a draft whose fixed
text is a plain, human-authored acknowledgement that invites the customer
to proceed (never wording lifted from `BOOKING_INTENT_KEYWORDS` on the
operator's behalf — the customer must still say something that
independently satisfies `detect_booking_intent` for AA-10 to start; this
feature does not shortcut that check). A negative or unclear classification
produces a draft that asks the confirmation question again, plainly worded,
not a repeat of the exact same sentence verbatim (avoids sounding broken on
screen — an editorial constraint, not a data-model one).

### GB-5 — No new autonomous-send path (the constitutional boundary, restated)

GB-2's and GB-4's outputs are ordinary `AIGeneration` rows reachable only
through the existing draft-generation endpoints, sent only by the existing
explicit-operator-send action. `booking_script/service.py` — the sole
module authorized to call `send_scripted_message()` (Constitution
Amendment 1.1.0, D-031) — is not modified, not imported from, and not
imported by this feature's new code. `advance_booking_script()`'s trigger
condition (`detect_booking_intent()` on a raw customer message, checked
only while `conversation.booking_script_step is None`) is unchanged byte
-for-byte. GB-4's affirmative path increases the *likelihood* that the
customer's next real message satisfies that existing check by having
already confirmed intent in plain language — it does not alter, bypass, or
special-case the check itself.

## 6. What this cycle does **not** authorize

- Extending Constitution Amendment 1.1.0 / AA-10's autonomous-send
  exception to any new message, step, or condition — explicitly declined
  by the human, 2026-08-19 (see §5 GB-5). Any future proposal to do so
  needs its own explicit human decision recorded in `DECISIONS.md`, the
  same way D-031 was.
- A real `insurance_lookup` resolver or any `convenio`/insurance data
  model — stays deferred (§4 PM-4).
- A real `payment_simulator` resolver, a payment link, or any payment
  timer mechanism — PM-3 corrects the *description* of payment to match
  what AA-10 already does; it does not add new payment behavior.
- Real booking, holds, identity persistence, or payment processing — all
  remain deferred exactly as `specs/004-dynamic-appointment-availability/spec.md`
  §6 already states; nothing in this feature touches that boundary.
- A full scheduling CRUD screen — still deferred, unchanged from 004's own
  deferral.
- Any change to `schedule_slots.status`/booking state as a result of GB-2
  or GB-4 — both are purely read/interpret/draft; neither writes to
  `scheduling.*`.

## 7. Data model impact (elaborated in `data-model.md`)

- One new table to persist GB-1's presented offers, linked to
  `AIGeneration` (durable, append-only from that generation's perspective
  — never mutated after creation, only superseded by a later generation's
  own new offer set on a subsequent resolution).
- `content.qa_entries` rows QA-028/029/030/031/032/033/034: `UPDATE`
  (`dynamic_data_required`, `answer_markdown`), triggering normal
  content-hash-driven re-embedding (`knowledge/ingest.py`) — not a schema
  change.
- No change to `scheduling.*` tables, `booking_script_step`, or the
  `messages_check` constraint — this feature does not touch AA-10's
  containment mechanisms at all (§6).

## 8. Acceptance outcomes to develop into executable tests

1. A customer asking for a specific seeded specialty's price receives a
   real, correctly-priced `ANSWER` generation (not abstention), with the
   price sourced from `scheduling.professional_specialties` and never
   fabricated by an LLM.
2. A customer asking a price/payment policy question covered by
   PM-2/PM-3 receives a real, accurate `ANSWER` generation with no mention
   of a payment link or timer that doesn't exist.
3. `convenio` questions still abstain exactly as before this feature —
   unchanged behavior, regression-checked.
4. After a resolved `appointment_availability` generation offers up to 4
   slots, a customer reply naming/describing one of them (in at least 2
   distinct phrasings per offer) produces a draft that correctly restates
   that specific offer and asks whether to proceed — never sent
   automatically.
5. A customer reply that doesn't clearly match any offered slot produces
   an ordinary RAG-composed draft instead of a wrong/forced selection.
6. Following a sent GB-2 confirmation-question message, a customer's
   affirmative reply (in at least 3 distinct phrasings, not just "sim")
   produces a draft inviting the customer to proceed — still requiring
   explicit operator send.
7. A negative or unclear reply to the same question produces a draft that
   re-asks, worded differently from the original question.
8. `booking_script/service.py` and `booking_script/parsing.py` are
   byte-for-byte unmodified by this feature's implementation (a literal
   diff check in the acceptance protocol, mirroring how 004 verified AA-10's
   structural containment).
9. The full pre-existing `smoke_*` suite (16 scripts) and the
   `v1/v2/v3/v4` Playwright suite continue passing unmodified — no V1-004
   regression.
10. No new customer-visible message is ever created outside an
    authenticated-operator-send call chain, except the pre-existing AA-10
    path — verified the same way 004's Phase 10 convergence check verified
    it (grep-able single-purpose `send_scripted_message()`, unchanged call
    graph).

## 9. Decisions resolved with the human (2026-08-19)

1. **`convenio` is out of scope for this cycle** — stays deferred,
   abstaining, unchanged. Only `preco`/`pagamento` are in scope.
2. **The new guided-selection/confirmation interpretation stays inside
   N2** — produces an internal draft an operator must explicitly send;
   does not extend Constitution Amendment 1.1.0's AA-10 exception. Chosen
   over the alternative (extending the autonomous-send exception to cover
   these new steps too) after the tradeoff was explained: extending the
   exception would need a new constitutional-amendment-level decision
   (like D-031's own multi-round process), while keeping it in N2 needs
   none and reuses 100% of the existing explicit-send/audit/draft
   machinery.
3. **"LLM ou embedding"** — resolved as embedding-only similarity
   matching for both GB-2 (closed 4-candidate classification) and GB-4
   (open-phrasing yes/no classification against a fixed reference set),
   not a live LLM call, to stay consistent with this codebase's existing
   determinism-for-dynamic-answers precedent (AA-5/D-028) and avoid adding
   a new LLM-latency/cost path for what is fundamentally a classification
   problem over a small candidate set.
