# Feature Specification: Dynamic Appointment Availability

**Feature ID:** `004-dynamic-appointment-availability`
**Status:** Clarification complete (2026-08-18) — planning, tasks, analysis,
and acceptance coverage required before implementation
**Authorized for specification:** 2026-08-18
**Scope:** read-only appointment-availability consultation only (see §6)

## 1. Purpose

`ROADMAP.md`'s "Future feature — Dynamic appointment availability" has been
deferred since V1 (`DECISIONS.md` D-026), with one narrow exception already
carved out and implemented: D-028's safety correction, which made
`dynamic_data_required=true` evidence resolve through a deterministic,
allowlist-only chunk-pattern substitution (no LLM rewrite) instead of ever
being passed through as a literal answer or silently fabricated
(`specs/002-v2-commercial-product-experience/` Phase 7, DONE). That
correction built the *safety* mechanism. It did not build a *resolver* for
appointment availability — no `qa_dynamic_bindings` row or equivalent exists
for the Q&A entries seeded with `dynamic_resolver = 'appointment_availability'`
(`db/init/004_qa.sql`, originally QA-011..QA-024), so they all correctly
abstain today.

This feature closes that gap for **availability consultation only**: let the
chatbot answer "is there an appointment available soon / this week / on a
given day / with a given specialty" using the real (synthetic) data already
sitting dormant in the `scheduling` schema (`db/init/001_schema.sql`,
`002_seed_and_schedule.sql` — `units`, `specialties`, `professionals`,
`professional_specialties`, `holidays`, `schedule_slots`, and
`scheduling.next_business_day()`). It does **not** build booking, holds,
payment, identity, or any other resolver name (`price_lookup`/
`payment_simulator`/`insurance_lookup` remain separately deferred,
unauthorized by this cycle — see §6).

The human's clarification (2026-08-18, §5) explicitly prioritized correct,
simple *logic* over preserving the existing `slot_offers`/`available_offers`/
`ensure_demo_availability()` D+1-and-D+7-window machinery or the exact
wording of the 14 seeded `agenda` Q&A entries verbatim — both may be
redesigned or replaced where that produces a cleaner implementation.

## 2. What already exists (verified against the real schema/code, not assumed)

- `content.qa_entries.dynamic_resolver` is an ORM-mapped, DB-seeded `text`
  column. It is currently **write-only** in the codebase — `knowledge/ingest.py`
  persists it from the seed/CRUD payload, but nothing in `ai/router.py`'s
  resolution path (`dynamic_pattern_result()`) ever reads it. Resolution
  today is entirely driven by `qa.dynamic_data_required` plus a
  `qa_dynamic_bindings` row (V2's generic table/filter/output-columns
  mechanism, `knowledge/dynamic_binding.py`). No `qa_dynamic_bindings` row
  exists for any `agenda` entry, so they all abstain
  (`DYNAMIC_DATA_UNAVAILABLE`) today — correctly, per D-028.
- The `scheduling` schema is real and seeded: `units`, `specialties`,
  `professionals`, `professional_specialties` (carries
  `fixed_price_cents`/`appointment_duration_minutes` per
  professional×specialty), `holidays`, `schedule_slots` (real
  `starts_at`/`ends_at timestamptz`, already `America/Sao_Paulo`-aware, with
  a `status` — `available`/etc.), and `scheduling.next_business_day(date)`
  (a real, reusable Saturday-is-a-business-day / Sunday-and-holiday-aware
  function). This feature's resolver builds on these directly.
- `scheduling.slot_offers`/`scheduling.available_offers`/
  `scheduling.ensure_demo_availability()` are the *existing* D+1/D+7-window
  materialization machinery — kept in the schema (harmless, unused) but this
  feature does not depend on them (§5 resolution 2): they are only ever
  seeded once at container-init time and go stale, and the human explicitly
  authorized disregarding that specific windowing rule rather than building
  freshness machinery to keep it alive.
- `scheduling.appointments`/`appointment_events`, `identity.patients`/
  `consent_records`, and `billing.payments` also already exist (D-024,
  dormant) but are **out of scope** for this cycle (§6) — this feature never
  reads or writes any of those tables.

## 3. Confirmed outcomes

### AA-1 — Resolver allowlist, not a generic table binding

`dynamic_resolver = 'appointment_availability'` is resolved by a
server-side-allowlisted, named resolver — distinct from V2's generic
`qa_dynamic_bindings` table/filter/output-columns mechanism, which has no way
to express "compute the next available business day" or apply the
Saturday/Sunday/holiday rule. Only `appointment_availability` is implemented
by this cycle; every other `dynamic_resolver` value already present in seed
data (`price_lookup`, `payment_simulator`, `insurance_lookup`) remains
unresolved/abstaining, exactly as today — this cycle does not authorize them.

### AA-2 — Read-only, on-demand, no freshness machinery needed

The resolver only ever `SELECT`s `scheduling.schedule_slots` (joined to
`specialties`/`professionals`/`professional_specialties`/`units`) for slots
with `starts_at` in the future relative to the real query time, computed
fresh on every resolution — never a pre-materialized, date-stamped
`slot_offers` row that can go stale. No row in `scheduling.appointments`,
`schedule_slots.status`, `identity.*`, or `billing.*` is ever written by this
feature. If too few future slots exist to answer (the seed data has been
exhausted by the passage of time), the resolver may deterministically ensure
more exist for the near future (an idempotent, allowlisted, read-adjacent
operation — never a customer/operator-triggered write path) rather than
either fabricating an answer or requiring a human to remember a manual reseed
step (§5 resolution 2).

### AA-3 — Deterministic parameter extraction from the customer's message

The customer's own message text (the same text already selected as this
generation's context) is parsed by a small, non-LLM, deterministic keyword
matcher for: a specialty (matched against `scheduling.specialties.slug`/
`display_name`, the same vocabulary the knowledge base already uses), a
date/day phrase ("amanhã", "semana que vem", a weekday name), and a period
("manhã"/"tarde"). No parameter match is required for the resolver to
produce an answer — an unmatched dimension is simply not filtered on (e.g.
"tem vaga amanhã?" with no specialty named returns the next available slot
per specialty). This is a new, small, purpose-built component — V2's proven
static-per-entry-filter alternative was considered and rejected because the
existing Q&A wording is generic, not per-specialty (§5 resolution 1).

### AA-4 — Structured, timezone-aware evidence

The resolver's output carries enough structure (specialty, professional,
unit, start/end time in `America/Sao_Paulo`, price) for both the
customer-facing rendered text and the operator's evidence view — matching
the `retrieval_hit_id`-anchored evidence shape every other draft already
uses, not a bespoke parallel format.

### AA-5 — Deterministic template rendering, never LLM-composed

Matches D-028's existing precedent exactly for every other
`dynamic_data_required=true` case (§5 resolution 4): the final customer-
facing text is a fixed template with the resolved slots' fields substituted
in — never an LLM rewrite, paraphrase, or "made to sound more natural" pass.

### AA-6 — Explicit operator send is the only customer-visible outbound action

Unchanged V1 invariant (Constitution Article III). This resolver produces an
internal draft exactly like every other trigger; nothing about "real-looking"
availability data changes who is allowed to send it to a customer.

### AA-7 — Append-only audit with safe provenance

Every resolution (success or failure) is audited, following the existing
V2-6 pattern (`ai.dynamic_pattern_resolved` / `ai.dynamic_pattern_fallback`)
rather than inventing a parallel event shape — extended only as needed to
carry which specialty/date/period was matched, never a query string or
table/column name in a customer-facing field.

### AA-8 — Manual fallback for unavailable, empty, or failed data

Matches D-028's existing safety correction exactly: zero matching slots or a
resolution error must produce the *existing* `ABSTAIN`/
`DYNAMIC_DATA_UNAVAILABLE` path — never a fabricated slot, never an exposed
cause string, never a partial answer.

## 4. Acceptance outcomes to develop into executable tests

1. A customer/operator query the resolver can serve produces real slots from
   `scheduling.schedule_slots`, rendered deterministically (no LLM rewrite)
   with `America/Sao_Paulo` times, price, and a "(simulação)" marker.
2. A query naming a real specialty only returns slots for that specialty; a
   query naming no specialty returns across all specialties with seeded
   availability.
3. A query for a day that resolves to Sunday or a holiday is silently
   redirected to the correct next business day by the existing
   `scheduling.next_business_day()` — the customer-facing text reflects the
   actual resolved date, never a raw "Sunday" slot.
4. A query for a Saturday only returns slots within whatever Saturday hours
   the resolver's own slot generation defines (documented in `plan.md`, not
   necessarily the old 8h-12h figure if the demo generation is redesigned).
5. Repeated resolutions on different days never require a manual reseed step
   to keep answering correctly — the near-future slot generation this
   feature owns is triggered deterministically as part of resolution, not by
   an external scheduler/cron (Constitution Article VIII).
6. Zero matching slots (e.g., a specialty with no seeded professional, or a
   date filter that matches nothing) aborts to the existing `ABSTAIN`/
   `DYNAMIC_DATA_UNAVAILABLE` path with no internal cause exposed, mirroring
   D-028's existing negative test.
7. No `scheduling.appointments`/`identity.*`/`billing.*` row is ever
   created, updated, or read by this feature — a negative test proves this
   structurally (no import/call path exists), not just "the demo happens not
   to trigger it."
8. `price_lookup`/`payment_simulator`/`insurance_lookup` (and any other
   `dynamic_resolver` value this cycle does not implement) continue to
   abstain exactly as they do today — a regression test proves this cycle
   did not accidentally widen the allowlist.
9. All V1/V2/V3 acceptance outcomes this spec's baseline lists as preserved
   still pass unmodified (spot-check, not a full rerun).

## 5. Decisions resolved with the human (2026-08-18)

1. **Parameter derivation: deterministic keyword extraction from the
   customer's message** (not V2's static-per-entry-filter pattern, not an
   unfiltered "show everything" fallback). Chosen because the existing Q&A
   wording is generic (no specialty named per entry); a small non-LLM parser
   over a known, limited vocabulary (specialty names, a handful of date/
   period phrases) stays deterministic and testable without inventing an NLU
   dependency. See AA-3.
2. **No freshness machinery for the existing D+1/D+7 `slot_offers`
   materialization — that windowing rule is explicitly disregarded.**
   Instead, the resolver computes against real-time `schedule_slots` and may
   deterministically top up near-future slots as part of resolving a query,
   never via a new scheduler/cron process (Constitution Article VIII still
   applies; this is a data-generation detail, not new infrastructure). See
   AA-2, AA-8, and `plan.md` for the exact mechanism.
3. **Scope of the existing 14 `agenda` Q&A entries: logic over preserving
   exact chunks.** The human explicitly authorized evaluating each entry
   against the new resolver's actual logic and keeping only what is
   necessary — entries may be edited, deleted, or newly created; the
   original QA-011..QA-024 identifiers/wording are not a constraint.
   `plan.md`/`tasks.md` will record the final entry set and, for each one
   removed or added, why. Booking/hold/identity/payment-confirmation content
   (matching what was QA-016/021/022/023/024) remains out of this feature's
   scope regardless of exact final numbering (§6).
4. **Deterministic, template-rendered response — confirmed, no LLM
   rewrite**, matching D-028's existing precedent for every
   `dynamic_data_required=true` case. See AA-5.
5. **Feature/folder naming confirmed as-is**: `004-dynamic-appointment-
   availability`, following the existing sequential `00N-` numbering,
   deliberately not `004-v4-...` since `ROADMAP.md`'s own "V4" already names
   a different, unrelated feature (N3 governed autonomy).

## 6. Explicitly out of scope unless newly approved

- holding, reserving, confirming, rescheduling, or cancelling appointments
  (`scheduling.appointments`/`appointment_events` writes) — unchanged from
  `ROADMAP.md`'s existing deferral;
- CPF, customer identity/profile persistence, consent capture
  (`identity.*` writes);
- payment (`billing.*`, the `payment_simulator` resolver);
- price lookup (`price_lookup` resolver) and insurance lookup
  (`insurance_lookup` resolver) — structurally similar read-only patterns,
  but not authorized by this cycle; each would need its own explicit
  authorization the same way this feature just received one;
- any booking/hold/identity/payment-confirmation Q&A content (§5 item 3);
- autonomous AI-to-customer send in any form — unchanged N4/Era-C exclusion;
- N3 governed autonomy/policy enforcement — unchanged V4 exclusion;
- the specialist-escalation workflow — unchanged V5 exclusion;
- real patient data — unchanged Constitution Article VI exclusion.

## 7. Required next artifacts

- `plan.md` with the resolver's exact architecture (dispatch mechanism,
  the deterministic keyword-extraction vocabulary, near-future slot
  generation mechanism, audit event shape), UI impact (likely none beyond
  existing evidence rendering), security, and testing decisions;
- `data-model.md` documenting any new column (if the chosen resolver
  architecture needs one — likely none, `dynamic_resolver` already exists)
  and confirming no change to the dormant `scheduling`/`identity`/`billing`
  tables' shape beyond ordinary reads;
- `contracts/openapi.yaml` delta (likely none — this is an internal
  resolution-path change, not a new endpoint, matching V2-6's own
  no-new-route precedent);
- `tasks.md`, `acceptance.md`, and a cross-artifact `analysis.md` before any
  implementation, per `AGENTS.md`'s required SDD flow.
