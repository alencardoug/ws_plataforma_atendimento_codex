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

### GB-2 — Slot-choice interpretation: ordinal-first, embedding-second, draft-only

**Corrected 2026-08-19 (D-033).** When an operator generates a draft
(manually via "Gerar rascunho" or automatically via the existing V2-7 idle
trigger) for a conversation whose most recent customer message follows a
GB-1 offer set with no confirmed selection yet, generation takes a new
branch instead of (not in addition to) ordinary RAG composition. Two
interpretation strategies are tried in order, neither an LLM call:

1. **Deterministic ordinal/positional parsing** — real usage found that
   embedding similarity structurally cannot match a reply like "segunda
   opção" or "3" to an offer: an ordinal reference shares no semantic
   content with an offer's own specialty/day/time text, so no confidence
   threshold fixes this. A small keyword table (`primeira`/`segunda`/
   `terceira`/`quarta`, each with a masculine/feminine form) plus a
   bounded 1-4 bare-digit fallback (there are never more than 4 offers,
   AA-2) resolves this class of reply exactly, deterministically.
2. **Embedding similarity** (original design, unchanged mechanism) — for
   a genuine paraphrase of the offer's own content (e.g. "o de quinta de
   manhã"), embeds the customer's message with the same `EmbeddingProvider`
   already used for retrieval, compares it by cosine similarity against
   each presented offer's own description text (embedded once, at GB-1
   persistence time), and treats the highest-similarity offer above a
   fixed confidence threshold as the customer's selection. Tried only when
   ordinal parsing finds nothing (or a named ordinal is out of range for
   this offer set).

Both are classification against a small, closed, already-known set of
candidates — not open-ended text generation — so no LLM call is used or
needed either way; "embedding" is the literal mechanism for strategy 2,
not a stand-in for "LLM" (matching the human's original "LLM ou embedding"
framing — embedding alone is sufficient and keeps this fully deterministic
given a fixed model/input, same determinism-preference precedent as
AA-5/D-028's "no LLM rewrite" rule, extended here to interpretation as
well as composition).

The resulting `AIGeneration` (status `ANSWER`, `dynamic_pattern_used=true`,
`trigger='GUIDED_SLOT_SELECTION'`) has fixed, Python-rendered `draft_text`
stating the selected offer's specifics **and its price** (reusing
`professional_specialties.fixed_price_cents` through the offer's `slot_id`,
same read-through-the-FK design as PL-3), followed directly by AA-10's own
fixed CPF-request line — **not** a "do you confirm?" question (removed by
D-033, see GB-4). **It is a draft like any other** — nothing sends
automatically, the operator reviews and explicitly sends or edits, same as
every existing draft path.

### GB-3 — Below-confidence match aborts to the existing manual/abstention path

If ordinal parsing finds nothing and no presented offer's embedding
similarity clears the confidence threshold either (the customer's reply
doesn't clearly match any of the 4, e.g. "nenhuma dessas serve" or an
unrelated message), generation falls back to ordinary RAG composition
instead — it does not force a wrong selection and does not invent a 5th
option. This mirrors AA-8's "never fabricate, fall back to the existing
safe path" precedent, adapted from data-lookup failure to
classification-confidence failure.

### GB-4 — Direct-to-CPF/payment flow, reusing AA-10's own parsers, draft-only

**Corrected 2026-08-19 (D-033), replacing the original standalone
"Deseja que eu confirme o agendamento?" confirmation step entirely.** Real
use found that step redundant and confusing: it asked the customer to
reconfirm something they'd already stated by picking a slot, and even a
clear "sim" reply led nowhere without the customer *separately* typing an
independent booking-intent phrase (AA-10's own trigger) — no continuous
path from "I picked a slot" to actually completing the simulated booking.
The human decided (D-033) that once a slot's details are stated (GB-2),
the flow should go directly to asking for CPF, then payment — the same
two questions AA-10's autonomous script always asked — but **continue to
stay inside N2**: one more explicit operator send per step, never an
autonomous send, preserving the earlier decision made when GB was first
authorized (spec.md §9 item 2 / D-032).

This is GB's own parallel CPF/payment conversation, textually identical to
AA-10's fixed messages but delivered as ordinary operator-approved drafts:

- After a GB-2 slot-choice draft is sent, the customer's next reply is
  interpreted by `extract_cpf()` — **reused verbatim from
  `booking_script.parsing`** (the same digit-count-only validation, never
  the real CPF check-digit algorithm, matching AA-10's "é uma simulação"
  framing) — not reimplemented, to avoid two copies of format logic
  drifting apart. Invalid → a draft re-asking for a valid CPF
  (`trigger` stays `GUIDED_SLOT_SELECTION`). Valid → a draft confirming
  the CPF and asking whether the value was paid
  (`trigger='GUIDED_CPF_CONFIRMED'`).
- After that draft is sent, the customer's next reply is interpreted by
  `extract_payment_confirmation()` — also reused verbatim from
  `booking_script.parsing`. Affirmative → a draft with AA-10's own final
  success wording (`trigger='GUIDED_BOOKING_COMPLETE'`, terminal — no
  further customer reply is specially interpreted after it). Negative or
  unclear → a draft re-asking the payment question
  (`trigger` stays `GUIDED_CPF_CONFIRMED`, unlimited retries, matching
  AA-10's own no-retry-limit behavior).

**The raw CPF/payment reply is parsed only from the request-local value**
— same non-retention principle AA-10 already applies to its own script,
extended here because GB now asks the same two sensitive questions.
Concretely: `advance_guided_booking()` runs synchronously inside
`anonymous_access/router.py`'s `send_customer_message()` (alongside, not
instead of, AA-10's own `advance_booking_script()`), using the raw
in-memory request body — the *only* place a raw CPF/payment reply is ever
read. It never persists that raw value; it stages only the
already-computed, safe *result* text (`conversations.guided_booking_pending_text`/
`guided_booking_pending_trigger` — new transient columns, data-model.md
§9) for the next draft-generation call to pick up and clear. The durable
`Message.body` for those two customer replies carries a fixed disclosure
marker instead, mirroring AA-10's own redaction exactly
(`anonymous_access/router.py` checks GB's own pending state only when
AA-10 itself didn't already redact).

### GB-5 — No new autonomous-send path (the constitutional boundary, restated)

GB-2's and GB-4's outputs are ordinary `AIGeneration` rows reachable only
through the existing draft-generation endpoints, sent only by the existing
explicit-operator-send action. `booking_script/service.py` — the sole
module authorized to call `send_scripted_message()` (Constitution
Amendment 1.1.0, D-031) — is not modified, not imported from, and not
imported by this feature's code, and `conversation.booking_script_step` is
never read or written by it either (GB-4 reuses only
`booking_script.parsing`'s pure, non-DB, non-autonomous-send functions —
disclosed precisely, not "zero coupling," per `test_005_booking_script_containment.py`'s
D-033-revised assertions). `advance_booking_script()`'s own trigger
condition (`detect_booking_intent()` on a raw customer message, checked
only while `conversation.booking_script_step is None`) is unchanged byte-
for-byte — a customer who independently types a booking-intent phrase at
any point (bypassing GB entirely) still reaches AA-10's autonomous script
exactly as before this feature existed; GB and AA-10 are two structurally
separate paths to conceptually similar outcomes, not a combined one.

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
4. **(D-033)** After a resolved `appointment_availability` generation
   offers up to 4 slots, a customer reply naming/describing one of them —
   by ordinal/position ("segunda opção", "3") or by paraphrase (in at
   least 2 distinct phrasings per offer) — produces a draft that
   correctly restates that specific offer with its price and asks for
   CPF directly (no separate confirm-question round trip) — never sent
   automatically.
5. A customer reply that doesn't clearly match any offered slot (by
   ordinal or embedding) produces an ordinary RAG-composed draft instead
   of a wrong/forced selection.
6. **(D-033)** A valid CPF reply produces a draft confirming the CPF and
   asking about payment; an invalid CPF reply produces a draft re-asking
   for a valid one — matching AA-10's own CPF-parsing behavior exactly
   (`extract_cpf`, reused not reimplemented) — still requiring explicit
   operator send at each step.
7. **(D-033)** An affirmative payment reply (in at least 3 distinct
   phrasings, not just "sim") produces a draft with AA-10's own final
   success wording; a negative/unclear reply produces a draft that
   re-asks the payment question, unlimited retries — matching AA-10's own
   payment-parsing behavior exactly (`extract_payment_confirmation`,
   reused not reimplemented).
8. `booking_script/service.py` and `booking_script/parsing.py` are
   byte-for-byte unmodified by this feature's implementation (a literal
   diff check in the acceptance protocol, mirroring how 004 verified AA-10's
   structural containment) — **except** that `guided_booking.py` now
   imports exactly two named functions from `booking_script.parsing`
   (`extract_cpf`, `extract_payment_confirmation`), verified precisely by
   `test_005_booking_script_containment.py` (D-033 correction) rather than
   asserting zero import coupling.
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
   matching for GB-2's closed 4-candidate classification, not a live LLM
   call, to stay consistent with this codebase's existing
   determinism-for-dynamic-answers precedent (AA-5/D-028) and avoid adding
   a new LLM-latency/cost path for what is fundamentally a classification
   problem over a small candidate set. (D-033 later replaced GB-4's own
   embedding-based yes/no classification with `booking_script.parsing`'s
   deterministic regex parsers — see item 4 below — so embedding
   similarity now applies only to GB-2's paraphrase fallback.)

## 10. Correction (2026-08-19, D-033)

Two real defects found through actual use, immediately after this
package's original acceptance closed:

4. **GB-2 needed deterministic ordinal/positional parsing, not just
   embedding similarity.** A reply like "segunda opção" or "3" shares no
   semantic content with an offer's own specialty/day/time description —
   embedding similarity cannot resolve this at any threshold, since it is
   not a calibration problem. Fixed by trying a small ordinal-word/digit
   parser first, falling back to the original embedding-similarity
   approach only when no ordinal is present or a named ordinal is out of
   range (§5 GB-2, revised).
5. **The standalone confirmation step (original GB-4) was removed.**
   Real use found the extra "Deseja que eu confirme o agendamento?"
   round trip, followed by requiring the customer to *independently* type
   a booking-intent phrase for AA-10 to start, felt broken rather than
   continuous. The human decided (2026-08-19) that once a slot's details
   are stated, the flow should proceed directly through CPF and payment —
   reusing AA-10's own fixed wording and deterministic parsers
   (`extract_cpf`, `extract_payment_confirmation`, imported from
   `booking_script.parsing` — the one disclosed, narrow exception to this
   package's original "zero import coupling with `booking_script/*`"
   claim, §5 GB-5 revised) — while still keeping every step an
   operator-approved N2 draft, explicitly re-confirming the N2-only
   decision from item 2 above rather than reopening it. The raw CPF/
   payment reply is parsed only at message-creation time, request-local,
   never persisted — the same principle AA-10 already followed, now
   extended to this parallel path (§5 GB-4, revised; `data-model.md` §9).

`booking_script/service.py` (home of the actual autonomous-send mechanism,
`send_scripted_message`) remains completely untouched and unimported by
this correction — only `booking_script/parsing.py`'s two pure functions
are reused, verified precisely by `test_005_booking_script_containment.py`.

## 11. Correction (2026-08-19, D-034)

Two more real defects found through further use, immediately after D-033
shipped:

6. **`latest_unconfirmed_offer_generation_id` never recognized a
   completed booking as finished.** After `GUIDED_BOOKING_COMPLETE`, the
   next customer message — even an unrelated clinical question — still
   matched the same 4 stale offers via embedding similarity instead of
   falling through to ordinary RAG/LLM composition. Fixed by treating any
   GB-flow-progress generation found after the offer-resolving one as
   proof the set is no longer pending.
7. **A genuinely uncovered clinical question could still surface a
   technically-`ANSWER` but substantively wrong draft** (e.g. an
   unrelated scheduling Q&A), instead of deflecting to a professional.
   The human decided against a hard clinical-topic gate in favor of a
   reranking step: the fixed clinical-deflection text becomes one more
   candidate compared, via one real LLM judgment call
   (`GenerationProvider.rerank_clinical`), against whatever the normal
   pipeline already produced — that candidate wins by default whenever
   adequate, the deflection wins only for a genuinely uncovered clinical
   question. Scoped outside the GB/scheduling flow and never applied
   against `full_parent_draft`'s own clinical-document match. New audit
   event `ai.clinical_deflection_applied` (`docs/architecture/EVENT_CATALOG.md`).

## 12. Correction (2026-08-19, D-035)

Human-requested after using the D-033 direct-to-CPF/payment flow:

8. **"Voltar"/"Cancelar"/"Alterar horário" (and natural variations) now
   let the customer step back to a fresh slot choice**, both while GB's
   CPF question is pending and while its payment question is pending.
   Checked before `extract_cpf`/`extract_payment_confirmation` in
   `interpret_cpf_reply`/`interpret_payment_reply` respectively; the
   response re-presents the *same* originally offered set (never a fresh
   query) as a numbered list, with a new `trigger='GUIDED_SLOT_RESELECTION'`
   (new allowed `ai_generations.trigger` value) so the next reply is
   routed back through GB-2's own ordinal/embedding matching instead of
   re-entering CPF/payment parsing.
9. **The GB-2/GB-4 message texts were reformatted** into multi-paragraph
   text (offer details, then the CPF/payment question, then a "Digite
   Voltar para escolher outro horário." hint), matching the exact format
   the human specified.
10. **`latest_unconfirmed_offer_generation_id`'s D-034 exclusion was
    revised from "was this trigger ever seen after the resolution" to
    "is the *latest* GB-flow trigger the terminal one"** — the original
    "ever" check permanently locked a picked offer set out of
    re-matching the moment `GUIDED_CPF_CONFIRMED` occurred even once,
    which broke "voltar" at the payment step specifically (by
    construction, reaching the payment step means `GUIDED_CPF_CONFIRMED`
    already happened). Only `GUIDED_BOOKING_COMPLETE` being the most
    recent GB-flow generation now excludes; D-034's original
    post-completion fix is unaffected since that state is always the
    latest one once reached (it is terminal — no further customer reply
    is specially interpreted after it).

Also answered a related human question, logged in `ROADMAP.md` rather
than implemented now: explicit calendar dates (e.g. "23/11/2026") are
**not** currently parsed by `extract_parameters` (AA-3) — only relative
keywords (`amanhã`, `sábado`, `semana que vem`, ...).
