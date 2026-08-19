# Implementation Plan: Dynamic Pricing and Guided Booking Selection

Governing spec: `spec.md`. Constitution: `.specify/memory/constitution.md`
(unchanged by this feature — see spec.md §6/§9).

## 1. Technical summary

Three independent pieces of work, ordered by risk (lowest first):

1. **PM** — content-only correction to 7 Q&A rows (`preco`
   QA-028/029/030, `pagamento` QA-031/032/033/034). No code.
2. **PL** — one new resolver function + one `NAMED_RESOLVERS` entry,
   following AA-1..AA-8's exact existing pattern in
   `scheduling/availability.py` and `ai/router.py`. Small, low-risk,
   already-proven shape.
3. **GB** — a new generation branch in `generate_draft()` plus one new
   table. The only genuinely new mechanism in this feature. Stays fully
   inside N2 (spec.md §5 GB-5, §6) — does not touch `booking_script/*`.

## 2. Module boundaries

- `scheduling/availability.py` — add `resolve_price_lookup()` alongside
  the existing `resolve_appointment_availability()`. Both are pure
  read-only query functions taking `(session, query_text)`.
- `ai/router.py` — register `"price_lookup"` in `NAMED_RESOLVERS`
  (one line); add the new GB branch to `generate_draft()`.
- **New module** `scheduling/guided_booking.py` — GB-2/GB-4's embedding
  classification logic and the GB-1 offer-persistence helper. Kept out of
  `availability.py` because it depends on `rag/service.py`'s embedding
  provider (a dependency `availability.py` does not otherwise have) and
  out of `ai/router.py` to keep that file's existing branch list
  (`full_parent_draft`/`dynamic_pattern_result`) readable as thin
  dispatch, matching how `dynamic_pattern_result` itself just calls into
  `knowledge/dynamic_binding.py`/`scheduling/availability.py` rather than
  inlining logic.
- `booking_script/*` — **not modified, not imported from, not importing
  from** this feature's new module. Verified by the same literal-diff
  acceptance check 004 used for AA-10 (spec.md §8 outcome 8).
- `knowledge/ingest.py` — untouched; PM's content edits go through the
  existing content-hash-driven re-embedding path with no code change.

## 3. Persistence

### 3.1 New table: `customer_service.appointment_offer_presentations`

One migration, additive only (no `db/init/*.sql` edits, matching 004's
own rule). See `data-model.md` for the full column list, indexes, and
constraints. Summary: one row per offer shown (up to 4 per resolving
generation), FK to `ai_generations.id`, carrying the `schedule_slots.slot_id`
it corresponds to, its rendered one-line description (embedded once at
insert time — the embedding itself is also stored, `vector(1536)` matching
the existing `content.qa_entries.embedding`/`content.knowledge_chunks.embedding`
column shape, so GB-2 never re-embeds the same 4 candidates on every
customer reply), and its 1-based `display_order`.

Never updated after insert (append-only, like `retrieval_hits`). A later
resolution for the same conversation simply inserts a fresh set tied to
its own new `ai_generation_id` — "the most recent unconfirmed offer set"
is a query (`ORDER BY created_at DESC LIMIT 1` scoped to the conversation,
joined through `ai_generations`), not a mutable pointer.

### 3.2 `content.qa_entries` content edits (PM)

Plain `UPDATE` statements (via the existing `/operator/knowledge/qa/{id}`
edit endpoint, run once as an operations task — not a migration, not a
seed-data change to `db/init/*.sql`, matching how 004 treated its own
`agenda` content review, spec.md §5 item 3). `dynamic_data_required` flips
to `false` for the 7 rows; `answer_markdown` is rewritten (exact copy is
an editorial task, `tasks.md`). `content_hash` changes automatically
recompute on next `ingest` run — no separate re-embed step needed.

### 3.3 No other schema change

`scheduling.*`, `booking_script_step`, `messages_check`, and every other
004 table/constraint are untouched.

## 4. PL — `price_lookup` algorithm

```python
def resolve_price_lookup(session: Session, query_text: str) -> DynamicResolution:
    params = extract_parameters(query_text)  # reused from AA-3, date/period ignored
    row = session.execute(
        select(Specialty.display_name, ProfessionalSpecialty.fixed_price_cents, ProfessionalSpecialty.appointment_duration_minutes)
        .join(ProfessionalSpecialty, ProfessionalSpecialty.specialty_id == Specialty.specialty_id)
        .where(Specialty.slug == params.specialty_slug)
        .order_by(ProfessionalSpecialty.professional_id)  # stable, deterministic first-row pick
        .limit(1)
    ).first()
    if row is None:
        raise DynamicResolutionError(cause=f"no professional_specialties row for specialty_slug={params.specialty_slug}")
    display_name, price_cents, duration_minutes = row
    text = (
        f"O valor da consulta de {display_name} é {format_price_brl(price_cents)} (simulação). "
        f"Duração aproximada: {duration_minutes} minutos."
    )
    return DynamicResolution(text, specialty_slug=params.specialty_slug, slot_count=None)
```

Registered as `NAMED_RESOLVERS["price_lookup"] = resolve_price_lookup`
(`ai/router.py`, one line next to the existing
`"appointment_availability"` entry). `dynamic_pattern_result()`'s existing
audit payload (`ai.dynamic_pattern_resolved` / `ai.dynamic_pattern_fallback`)
already handles any `specialty_slug`-carrying resolution generically — no
change needed there (`slot_count=None` is simply omitted from the payload,
same as any resolver that doesn't produce one).

## 5. GB — algorithm

### 5.1 GB-1: persisting presented offers

`resolve_appointment_availability()` gains one addition: on a successful
(non-raising) resolution, its caller (`dynamic_pattern_result()`, the one
call site that already has both the `AIGeneration` being built and the
resolver's row set) calls a new helper:

```python
def persist_presented_offers(session: Session, ai_generation_id: UUID, rows: Sequence[_SlotRow]) -> None:
    provider = configured_embedding_provider()  # same provider rag/service.py already uses
    descriptions = [_offer_description(row) for row in rows]  # one-line summary per offer, distinct from _render_offers' multi-line customer text
    vectors = provider.embed(descriptions)
    for order, (row, description, vector) in enumerate(zip(rows, descriptions, vectors, strict=True), 1):
        slot, *_ = row
        session.add(AppointmentOfferPresentation(
            ai_generation_id=ai_generation_id, slot_id=slot.slot_id,
            display_order=order, description=description, embedding=vector,
        ))
```

This requires `resolve_appointment_availability()` to return its row set
alongside the `DynamicResolution` (a small signature change) so the caller
can persist exactly what was shown — not re-run the query (which could
race against a concurrent AA-9 seed action or another customer's slot
consumption once real booking exists, §6 note: it doesn't exist yet, but
the design should not assume the query is idempotent across calls).

### 5.2 GB-2/GB-3: slot-choice branch in `generate_draft()`

New function `scheduling/guided_booking.py::interpret_slot_choice`:

```python
# cosine_distance (lower = more similar). Calibrated against real
# text-embedding-3-small output, not a guessed constant (spec.md §8
# outcome 4/5): genuine paraphrases of an offer measured 0.42-0.66
# (a generic "the morning one, whichever you have" scored 0.64; a specific
# "Thursday morning with Dr. Eduardo" scored 0.42), an unrelated message
# scored 0.70-0.71. 0.68 sits in that gap, biased toward the unrelated
# side since GB-3's fallback (ordinary RAG) is always safe.
SLOT_CHOICE_DISTANCE_THRESHOLD = 0.68

def interpret_slot_choice(session: Session, conversation_id: UUID, customer_text: str) -> AppointmentOfferPresentation | None:
    generation_id = latest_unconfirmed_offer_generation_id(session, conversation_id)  # None if none pending, or already confirmed
    if generation_id is None:
        return None
    provider = configured_embedding_provider()
    [vector] = provider.embed([customer_text])
    # Same idiom rag/service.py already uses (pgvector's cosine_distance
    # operator, SQL-side, index-eligible) rather than pulling rows into
    # Python to compute similarity — lower distance is a better match.
    best = session.execute(
        select(AppointmentOfferPresentation, AppointmentOfferPresentation.embedding.cosine_distance(vector).label("distance"))
        .where(AppointmentOfferPresentation.ai_generation_id == generation_id)
        .order_by("distance").limit(1)
    ).first()
    if best is None or best.distance > SLOT_CHOICE_DISTANCE_THRESHOLD:
        return None
    return best[0]
```

`generate_draft()` gets one new branch, tried **before** `full_parent_draft`
and `dynamic_pattern_result` (a pending offer selection takes priority
over ordinary retrieval — the customer is mid-flow, not asking a new
question) but only when `interpret_slot_choice` returns non-`None`; a
`None` result falls through to the existing branches unchanged, so GB-3's
"abort to normal RAG" requirement is satisfied by construction, not a
separate code path.

On a match, the result is a fixed template
(`GenerationResult("ANSWER", f"Entendi que você escolheu: {offer.description}. Deseja que eu confirme o agendamento?", None, [])`)
— `used_hit_ids` is empty (no retrieval evidence backs this branch; it is
grounded in the persisted offer row, not RAG). `dynamic_pattern_used` is
set `true` for this generation too (it is exactly as deterministic/
non-LLM as the existing dynamic-pattern branches, and V3-3/V3-4's Human
Correction Rate metrics should treat it the same way — reusing the
existing flag rather than adding a third one, `data-model.md` §2 confirms
no schema change needed for this).

### 5.3 GB-4: confirmation-intent branch

New function, same module:

```python
AFFIRMATIVE_REFERENCE_PHRASES = ("sim", "pode confirmar", "confirmo", "isso mesmo", "quero sim")
NEGATIVE_REFERENCE_PHRASES = ("não", "nao quero", "ainda não", "deixa pra depois", "não confirma")

# An absolute per-group threshold (like SLOT_CHOICE_DISTANCE_THRESHOLD)
# does not work here: measured against real embeddings, affirmative and
# negative reference phrases are not far apart from each other (both are
# short phrases about the same topic), so a clear affirmative reply
# routinely scores under any reasonable threshold against *both* groups
# (e.g. "Pode confirmar sim" measured 0.154 to the affirmative group but
# also 0.382 to the negative group — both would clear a 0.5+ threshold).
# Classification is instead by whichever group is closer, gated by a
# minimum *margin* between the two best distances. Measured genuine cases
# had margins of 0.13-0.23; an unrelated message had a margin of only
# 0.03. 0.08 sits safely between those two populations.
CONFIRMATION_MARGIN_THRESHOLD = 0.08

def interpret_confirmation_intent(customer_text: str, provider: EmbeddingProvider) -> bool | None:
    # Reference-phrase vectors are computed once per process (module-level
    # cache keyed by provider.model, invalidated only if the configured
    # model changes) — there is no table to query cosine_distance against
    # here (unlike interpret_slot_choice, these aren't persisted rows), so
    # this one function does the distance math in Python over a fixed
    # 10-vector set, not per-row SQL. best_affirmative/best_negative are the
    # minimum cosine distance to either reference group.
    ...  # classify by whichever group is closer, gated by
         # CONFIRMATION_MARGIN_THRESHOLD; margin too small -> None
         # (ambiguous/no-match alike, spec.md GB-4)
```

Triggered only when the conversation's most recent `OPERATOR` message has
`Message.source_generation_id` pointing at a generation with
`trigger = 'GUIDED_SLOT_SELECTION'` (the already-existing FK `Message`
carries for every sent draft — no new lookup mechanism, `data-model.md`
§3). `True` → fixed acknowledgement template, worded to *not* itself
contain a `BOOKING_INTENT_KEYWORDS` phrase (spec.md GB-4 constraint,
enforced by a unit test asserting the fixed string doesn't substring-match
any entry in `booking_script/parsing.py::BOOKING_INTENT_KEYWORDS`, so a
future edit to either list can't silently violate this). `False`/`None` →
fixed re-ask template, worded differently from the original question.

## 6. Security

- No new write path to `scheduling.*` — GB only reads `schedule_slots`
  (via the unchanged AA-2 query) and writes to the new
  `appointment_offer_presentations` table only, which has no bearing on
  slot availability/status.
- `booking_script/*` import graph is checked by the same acceptance-time
  static check 004 used (spec.md §8 outcome 8) to catch any accidental
  coupling immediately, not just at review time.
- The new table stores only already-customer-visible offer data (specialty,
  time, price — all already shown to the customer in AA-2's own rendered
  text) plus an embedding vector of that same non-sensitive description —
  no CPF, no payment data, nothing AA-10's redaction rules apply to.
- PL-3/PL-4 reuse AA-2/AA-8's exact read-only/fallback shape — no new
  security surface.

## 7. Testing implementation

- Unit: `resolve_price_lookup` against each of the 4 seeded specialties
  (including the AA-3a generalist default) and the no-row fallback.
- Unit: `interpret_slot_choice`/`interpret_confirmation_intent` against a
  fixed embedding fixture (reusing the existing
  `DeterministicTestEmbeddingProvider` pattern already used for RAG tests
  — no real OpenAI calls in unit tests), covering: correct match, no-match
  fallback, multiple phrasings per spec.md §8 outcomes 4/6.
- Integration: full `generate_draft()` branch ordering — GB takes priority
  over RAG only when applicable; PL takes priority over the generic
  `qa_dynamic_bindings` path when both could theoretically apply (they
  can't today — no `preco` entry has a `qa_dynamic_bindings` row — but the
  test documents the precedence explicitly rather than leaving it
  implicit).
- Static/structural: literal diff of `booking_script/service.py` and
  `booking_script/parsing.py` against their pre-feature `git` blobs,
  asserting byte equality (spec.md §8 outcome 8) — same technique 004's
  own AA-10 containment test used.
- Regression: full existing `smoke_*` suite (16 scripts) and
  `v1/v2/v3/v4` Playwright suite unmodified (spec.md §8 outcome 9).
- Content: after PM's edits and a re-ingest, confirm the 7 corrected rows
  retrieve correctly for their own questions and no longer carry
  `dynamic_data_required=true` (except the 3 PL rows, unchanged).

## 8. Performance

One extra embedding call per GB-1 persistence (4 short strings, batched in
one `provider.embed()` call — same batching `ingest.py` already does) and
at most one extra embedding call per customer message during an active
guided-selection window (GB-2/GB-4) — bounded, not per-poll, only on
actual draft generation. No new N+1 pattern; `latest_unconfirmed_offer_set`
is a single indexed query (`data-model.md` §1 index).

## 9. Deliverables

- Migration: `appointment_offer_presentations` table.
- `scheduling/availability.py`: `resolve_price_lookup`, `_offer_description`,
  `resolve_appointment_availability`'s row-set-returning signature change.
- `scheduling/guided_booking.py`: new module (GB-1 persistence helper,
  GB-2/GB-4 interpretation functions, confidence constants).
- `ai/router.py`: `NAMED_RESOLVERS["price_lookup"]`, new `generate_draft()`
  branch.
- Content edits: QA-028/029/030/031/032/033/034 (`answer_markdown`,
  `dynamic_data_required`).
- Tests per §7.
- `checklists/`, `acceptance.md`, `analysis.md` (Phase-end deliverables,
  `tasks.md` sequences these).

## 10. Prohibited shortcuts

- No LLM call anywhere in PL, GB-2, or GB-4 — embedding-similarity or
  fixed templates only, matching spec.md §9 item 3.
- No import of `booking_script/*` from any new module, and no import of
  any new module from `booking_script/*`.
- No mutation of `schedule_slots.status` or any `scheduling.*` write from
  GB code.
- No reuse of `BOOKING_INTENT_KEYWORDS` phrasing inside GB-4's fixed
  acknowledgement template (unit-tested, §5.3).
- No new customer-visible autonomous send — every GB output is an
  `AIGeneration`, reachable only through the existing explicit-send path.
