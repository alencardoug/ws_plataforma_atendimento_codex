# Cross-Artifact Analysis: Dynamic Appointment Availability

## 1. Method

Read `spec.md`, `plan.md`, `data-model.md`, `tasks.md`, and `acceptance.md`
together; checked every cited table/column/function/constraint name in
`plan.md`/`data-model.md` against the real source
(`db/init/001_schema.sql`, `002_seed_and_schedule.sql`,
`app/customer_care/infrastructure/models.py`, `ai/router.py`,
`knowledge/dynamic_binding.py`), not from memory, matching V1/V2/V3's own
pre-implementation `analysis.md` method (`tasks.md` T001).

This document covers two review rounds the same day: §2-5 are the
*original* round (the query path still auto-generated near-future slots as
part of resolution); §6-7 are the *revision* round after the human's
second clarification split that into a read-only query path plus a
separate seed action. §5's verdict is superseded by §7's; §2's finding and
§3's checks remain valid facts about the schema/code, re-confirmed still
applicable in §6.

## 2. Findings and repairs

1. **`ensure_near_future_slots()`'s original pseudocode iterated every
   `professional_specialties` row regardless of `Professional.active`.**
   `data-model.md` §1 correctly lists `active` as a mapped field, but
   `plan.md` §4's slot-generation loop did not filter on it — a
   deactivated professional would still have kept getting new near-future
   slots generated and offered to customers, which is wrong (a deactivated
   professional should stop being schedulable, the same way `is_active`
   already gates every other entity's visibility in this codebase — `V1`
   knowledge-base soft-delete, `V3` category `is_active`). Caught before
   any code exists, per Constitution Article I ("specification precedes
   implementation... if implementation reveals a required behavioral
   change, update the spec/plan/tasks before continuing" — same principle
   applied one step earlier, during planning itself). Fixed in `plan.md` §4
   (the loop now joins through `Professional` and filters
   `active.is_(True)`) and reflected in `tasks.md` T030/T032.

## 3. Checks that passed without repair

- Every table/column/function `plan.md`/`data-model.md` cites
  (`scheduling.specialties`/`professionals`/`professional_specialties`/
  `units`/`schedule_slots`/`holidays`, `scheduling.next_business_day()`,
  the `UNIQUE (professional_id, starts_at)` constraint, the `slot_status`
  enum's `available`/`held`/`booked`/`blocked` values) was verified against
  the real `db/init/001_schema.sql` DDL and matches exactly.
- `content.qa_entries.dynamic_resolver` was verified as already
  ORM-mapped (`infrastructure/models.py:141`) and already write-only in
  application code (`knowledge/ingest.py`, confirmed no read site exists
  today) — `spec.md` §2's claim about the current gap is accurate, not
  assumed.
- The `dynamic_pattern_result()` dispatch change (`plan.md` §2) was checked
  against its two real call sites (`generate_draft()`, `select_evidence()`)
  — both already have a natural source of query text to pass through
  (`query` in the former, `RetrievalRun.query_text` via `hit.retrieval_run_id`
  in the latter), so no call site needs new input it doesn't already have
  access to.
- The fallthrough behavior for `dynamic_resolver` values this cycle does
  not implement (`price_lookup`/`payment_simulator`/`insurance_lookup`) was
  traced through `resolve_dynamic_pattern(session, qa)`'s existing code
  path: with no `qa_dynamic_bindings` row for any of them, it already
  raises `DynamicResolutionError` today — confirming `spec.md` acceptance
  outcome 8 and `plan.md` §2's claim that "no special-casing is needed."
- `data-model.md`'s claim that no Alembic migration is required was checked
  against the actual current schema — every column/constraint this feature
  reads or writes already exists.
- `acceptance.md`'s 9 lettered sections (A-J including quality gates) map
  1:1 onto `spec.md` §4's 9 numbered acceptance outcomes via
  `checklists/traceability.md` — no orphaned outcome, no acceptance section
  without a spec outcome behind it.

## 4. Residual risks / deferred decisions (not contradictions, but open)

- **(Superseded by §6) `TARGET_D1=1`/`TARGET_D7=3` and the 08:00-18:00
  seeding window are demo constants**, not derived from any real clinical
  scheduling policy — acceptable for this synthetic/demo system
  (Constitution Article VI) but should not be read as a realistic staffing
  model if this pattern is ever extended toward a real deployment.
- **The deterministic keyword vocabulary (`plan.md` §5) only covers the 3
  seeded specialties' known synonyms and a small set of Portuguese date/
  period phrases.** A customer phrasing outside that vocabulary simply
  gets no dimension filtered on (falls back to "all specialties, nearest
  available slots") rather than a wrong match — a safe default, but a real
  limitation worth knowing about, not a defect to fix now (`spec.md` §5
  resolution 1 explicitly chose this trade-off over building genuine NLU).
- **Q&A content cleanup's exact final entry list (Phase 7, T070) is
  deliberately left to implementation time**, not fixed here — the human
  explicitly prioritized evaluating against the real, working resolver over
  pre-deciding chunk wording (`spec.md` §5 resolution 3).
- **(Superseded 2026-08-19 by §14 — the human corrected AA-9 to scope the
  seed action to the generalist specialty specifically.) Found during
  Phase 5 live verification, not a contradiction (`spec.md`
  AA-9 item 2 explicitly chose this): the seed action's flat, not-
  specialty-scoped count means which specialty actually receives the 4
  seeded slots is an accident of `professional_id` ordering, not a
  guarantee of coverage across all 4 specialties.** Concretely: because
  `mastologia-oncologica`'s 3 professionals were seeded with the lowest
  UUIDs (`30000000-...-0001/0002/0003`), `active_professional_specialty_pairs()`'s
  `ORDER BY professional_id` always exhausts `TARGET_D1=1`/`TARGET_D7=3`
  using only mastologia's professionals before any other specialty's
  pair is ever tried — one click of "Garantir disponibilidade" will
  essentially always seed mastologia only, never colorretal/segunda-opinião/
  generalist, under the current fixed-UUID data. This is spec-compliant
  (the human's own words: "a flat count, not scoped to any one
  specialty/professional"), so not a defect to fix — but it does mean
  Phase 7 (Q&A content cleanup, T070/T071) and Phase 10's acceptance
  automation should verify their positive-path examples against whichever
  specialty the seed action actually populated in that run, not assume
  the generalist default (or any specific non-mastologia specialty) will
  have live data — and should explicitly test at least one zero-match
  abstain for an un-seeded specialty as the honest, spec-correct outcome,
  not a bug to chase.

## 5. Verdict (first design, superseded — see §6)

No unresolved contradiction between `spec.md`, `plan.md`, `data-model.md`,
`tasks.md`, and `acceptance.md` as of this review; the one finding in §2 was
repaired in place before any implementation began. This verdict covered the
*original* design (query path auto-generates near-future slots as a side
effect of resolution). That design was superseded the same day by the
human's second clarification round — see §6.

## 6. Revision review — second clarification round (2026-08-18, same day)

The human split what had been one combined behavior into two: the query
path (AA-2) is now purely read-only, and a new, separate, explicit
operator-triggered seed action (AA-9) reinstates the D+1/D+7 rule with
exact idempotent semantics (1 slot on D+1, 3 on D+7, 08:00-18:00). All five
artifacts (`spec.md`, `plan.md`, `data-model.md`, `tasks.md`,
`acceptance.md`) and both checklists were rewritten for this split before
this re-review.

### Re-checked for the revision

- **No leftover reference to the old combined design.** Grepped for
  `ensure_near_future_slots` (the old function name) across all five
  artifacts after the rewrite — zero remaining references; every mention
  is now either `resolve_appointment_availability` (query, read-only) or
  `ensure_seed_availability`/`create_slots_on` (seed, the only write path).
- **The query path's "never writes" claim is independently testable, not
  just asserted.** `plan.md` §4/§9, `data-model.md` §1, and
  `acceptance.md` §C all describe the same structural test (grep/introspect
  `scheduling/availability.py` for write constructs and for an import of
  `scheduling/seeding.py`) — one verification method, stated consistently
  three times, not three different claims that could drift apart.
- **AA-9's flat (not per-specialty) counting was checked against `spec.md`
  §6's own new exclusion bullet** ("the seed action creating/counting
  slots for any specialty other than 'however many happen to exist'") —
  `plan.md` §4b's `count_available_on()`/`create_slots_on()` indeed count
  and create without any specialty filter, matching that exclusion exactly
  rather than silently reintroducing per-specialty semantics.
- **The new endpoint's route prefix was checked against the existing
  convention** (`knowledge/router.py`'s `/operator/knowledge` prefix
  pattern) and corrected in `plan.md` §4b during this review — the
  original pseudocode had the full path in the route decorator instead of
  using an `APIRouter(prefix=...)`, which every other operator router in
  this codebase uses. A documentation-only fix, caught before any code
  exists.
- **`Professional.active` filtering (§2 finding 1) still applies in the
  new location.** That logic now lives in `scheduling/seeding.py`'s
  `create_slots_on()`/`active_professional_specialty_pairs()` rather than
  the old `ensure_near_future_slots()` — re-confirmed present in `plan.md`
  §4b and reflected in `tasks.md` T040/T041.
- **`acceptance.md`'s now-11 lettered sections (A-K) map 1:1 onto `spec.md`
  §4's 10 numbered outcomes** via `checklists/traceability.md` (K is
  quality gates, not its own numbered outcome — consistent with V1/V2/V3's
  own pattern of an unnumbered quality-gates section) — no orphaned
  outcome, no section without an outcome behind it.
- **The frontend surface this revision adds (one button, one status line)
  was checked against `tasks.md`'s gate list** — Phase 6's gate now
  requires `eslint`/`tsc --noEmit`/`vitest`/`vite build`, and Phase 8's
  final gate was updated to include them too (the first design's plan
  explicitly said "no frontend gate applies," which is no longer true and
  has been corrected everywhere it was stated: `plan.md` §1/§13,
  `tasks.md` Phase 6/8 gates, `acceptance.md` §J/§K).

### New residual risk from this revision

- **The seed action's flat, specialty-agnostic count (1×D+1/3×D+7 total,
  not per-specialty) means a customer asking about a specific specialty
  could still get zero results even right after a successful seed call**,
  if all 4 seeded slots happened to land on a different specialty. This is
  the human's explicit, deliberate design choice (not a defect) — the seed
  button is described as guaranteeing "4 vagas disponíveis," not "4 vagas
  por especialidade." Worth knowing operationally (an operator demoing a
  specific specialty may need to check what actually got created), not
  worth fixing without a new instruction, since it would change the
  button's specified behavior.

## 7. Verdict (second design, superseded — see §8-9)

No unresolved contradiction between `spec.md`, `plan.md`, `data-model.md`,
`tasks.md`, and `acceptance.md` as of this revised review; §2's finding and
§6's five re-checks/one fix are all repaired in place before any
implementation began. This verdict covered the design after the *second*
clarification round (read-only query path + separate seed action). It was
superseded the same day by the third and fourth rounds — see §8.

## 8. Revision review — third and fourth clarification rounds (2026-08-18, same day)

The third round deferred a full scheduling CRUD to `ROADMAP.md` (no
artifact impact beyond that file) and identified a real content gap: no
seeded specialty covers a customer who doesn't yet know what's wrong. The
fourth round corrected how to close that gap: a customer with "no
specialty named" needs a **generalist** professional — a new seeded
specialty of its own (AA-3a) — not an unfiltered search across the 3
diagnosis-specific ones. This is the first time this feature adds new
reference data rather than only reading/reusing what already existed, so
it gets the same rigor as any other new-data decision in this codebase.

### Re-checked for this revision

- **`extract_parameters()`'s new default is unconditional, not a
  fallback-only path.** `plan.md` §5's pseudocode was checked line by line:
  `specialty_slug` is initialized to `GENERALIST_SLUG` before the loop
  runs, so "explicitly asked for a generalist" and "asked for nothing in
  particular" produce identical output through the same code path — no
  hidden branch could let one behave differently from the other by
  accident.
- **The query algorithm (`plan.md` §4) was checked to confirm it always
  filters by specialty now** — the old `if params.specialty_id:`
  conditional (which allowed an unfiltered query when nothing matched) was
  replaced with an unconditional `.where(Specialty.slug ==
  params.specialty_slug)`, consistent with `specialty_slug` never being
  `None` after §5's change. No leftover conditional path that could
  silently reintroduce the old "search everything" behavior.
- **The new migration (`data-model.md` §6, renumbered 2026-08-19 by the
  schema-creation correction, §12 below) was checked against the exact
  UUID ranges the original seed file used** (`specialty_id` prefix
  `20000000-...`, `professional_id` prefix `30000000-...`) — the new rows
  continue those ranges (`...0004`, `...0010-0012`) rather than colliding
  with or duplicating an existing id.
- **Pricing/duration for the new generalist consultation were checked
  against the other 3 specialties' seeded values** for internal
  consistency (`data-model.md` §6's table) — deliberately priced and timed
  lower than all 3 (R$600/45min vs. R$980-1450/60-90min), consistent with
  the human's own "consulta simples" framing, not an arbitrary number.
- **`tasks.md`'s Phase 1 gained T009 (the migration) ahead of T010/T011**,
  and Phase 2's independence from Phase 1 was re-justified explicitly
  (`GENERALIST_SLUG` is a Python constant, not a DB lookup — only Phase 3's
  query and Phase 7's Q&A seeding actually need T009 to have run) rather
  than asserted without reason.
- **`spec.md` §4 outcome 2 and `acceptance.md` §B were both checked for the
  stale "returns across all specialties" claim** the second/third rounds
  had left in place — found and corrected in both (this document's own
  method: grep the exact stale phrase across every artifact after a
  behavioral change, not just the file that prompted the change).

### New residual risk from this revision

- **The generalist specialty's 3 professionals are net-new synthetic
  identities**, not reassigned from the existing 9. This keeps the
  original 3 specialties' data untouched (lower risk of an unrelated
  regression) at the cost of a slightly larger seed dataset — a reasonable
  trade a real deployment might revisit, not a concern for this synthetic
  demo (Constitution Article VI).

## 9. Verdict (third design, superseded — see §10-11)

No unresolved contradiction between `spec.md`, `plan.md`, `data-model.md`,
`tasks.md`, and `acceptance.md` as of this review. This verdict covered
the design through the fourth clarification round (the generalist
specialty). It was superseded the same day by the fifth round, which adds
a materially different kind of outcome — see §10.

## 10. Revision review — fifth clarification round: the booking script and Constitution Amendment 1.1.0 (2026-08-18, same day)

This round is categorically different from every prior one in this
package: it is the first time any artifact in this entire project
authorizes a customer-visible message to be sent without an authenticated
operator action. That makes this review's job different too — not just
"is the design internally consistent" (§2-9's method) but "is the
exception this design implements airtight, and does it leak."

### What was checked, and how

- **The constitutional text itself** (`.specify/memory/constitution.md`
  Amendment 1.1.0) was read against `plan.md` §8b/§13 line by line: every
  bound the amendment states (fixed templates only, never LLM-composed,
  no real persistence, does not extend to any other outbound path) has a
  corresponding, specific enforcement mechanism in the plan — not just a
  restated promise. Table:

  | Amendment bound | Plan.md enforcement |
  |---|---|
  | "fixed, human-authored template set... never LLM-composed" | `advance_booking_script()`'s every `send_scripted_message()` call site uses a literal string, interpolated only with this feature's own data (CPF format, seeded price) — no LLM/embedding provider is imported anywhere in `booking_script/` (§13) |
  | "does not extend to any other outbound message" | `send_scripted_message()` is called from exactly one place (`advance_booking_script()`), itself called from exactly one place (`send_customer_message()`); a dedicated structural test (T096) greps every other operator-message construction site in the codebase |
  | "no real booking, payment, or identity persistence" | no new column holds a CPF or payment answer — only `booking_script_step`, an enum-like position marker (`data-model.md` §8, renumbered 2026-08-19); no `scheduling.appointments`/`schedule_slots.status` write anywhere in `booking_script/` (§13) |
- **The `CHECK` constraints in the new migration** (`data-model.md` §8)
  were verified to enumerate the *only* legal values at the database
  level, not just in Python — so even a future bug in application code
  cannot write an unauthorized `booking_script_step`/`autonomous_source`
  value; the database itself refuses it.
- **The trigger's scope was checked for false positives**: `plan.md` §8b's
  `has_recent_resolved_availability()` guard was added specifically so a
  stray "quero marcar" in an unrelated conversation (one that never saw a
  real availability answer) cannot start the script — re-derived from
  `spec.md` AA-10's own intro sentence ("after a customer expresses intent
  to book one of the real slots AA-1..AA-9 showed them"), not invented
  independently.
- **Audit traceability was checked for the specific claim `plan.md` §8b
  makes** — that a reviewer can enumerate every autonomously-sent message
  in the system with one query. Confirmed: `messages.autonomous_source`
  (queryable directly) and `booking_script.autonomous_message_sent`
  (queryable via the existing audit-event table) both independently answer
  that question, redundantly, so neither being incomplete alone hides
  anything.
- **The decision record was checked against what actually happened in
  this conversation**: `DECISIONS.md` D-031 states the human was shown the
  one-click-per-message alternative and its zero constitutional impact
  before choosing the exception, and was asked to confirm a second time
  after that explanation. Both are factually accurate to how this
  clarification round actually unfolded, not a retroactively cleaned-up
  account.
- **`spec.md` §6's exclusion list was re-checked for internal
  contradiction** with the new AA-10 outcome — found and fixed three
  places where "CPF/payment/identity" and "autonomous send" were
  previously stated as flatly excluded (accurate before this round, wrong
  after it); each was rewritten to state the *narrower* thing that remains
  excluded (real persistence, real payment processing, every *other*
  outbound path) rather than deleting the exclusion outright.

### New residual risks from this revision

- **This is the first exception to a previously-absolute rule in this
  project.** Even though it is narrowly bound today, its mere existence
  changes the shape of a future "can we make X automatic too" request —
  the next such request can no longer be answered with "there has never
  been an exception," only "there is exactly one, this narrow, for this
  reason." Worth naming explicitly so a future reviewer doesn't
  under-weight how deliberately this one was scoped.
- **`booking_script_step`'s `CHECK` constraint enumerates exactly 2
  values today.** Any future extension of the script (a new step) needs
  its own migration to widen that constraint — a good thing (forces
  deliberate schema review before the script can grow), but worth flagging
  so it isn't mistaken for an oversight if a future change trips it.
- **The generalist specialty's price (`data-model.md` §6, R$600) is the
  number AA-10's script will actually display** for a "primeira consulta"
  booking — this is the first place in the feature where AA-3a's pricing
  choice has a second-order customer-facing effect beyond the availability
  answer itself; still a reasonable, deliberately-lower-than-the-others
  number, not a new concern, just newly load-bearing.

## 11. Verdict (fifth-round design, superseded — see §12-13)

No unresolved contradiction between `spec.md`, `plan.md`, `data-model.md`,
`tasks.md`, and `acceptance.md` as of this latest review; §2's finding and
§6's/§8's/§10's re-checks/fixes are all repaired in place before any
implementation began. Every bound Constitution Amendment 1.1.0 states has
a specific, checked enforcement mechanism (§10's table) — this is not a
promise resting on prose alone. `checklists/requirements.md`'s final item
("cross-artifact analysis reports no material contradiction") is satisfied
by this document. This feature is ready to move from artifact authoring
into `tasks.md` Phase 1 implementation, per `AGENTS.md`'s required SDD
flow. Given AA-10's exceptional nature, `tasks.md` Phase 10/T082 must
re-run this containment review one more time against the *real*
implementation before the feature can be declared DONE — a stronger bar
than this package's other outcomes get.

## 12. Revision review — sixth round: scheduling schema creation correction (2026-08-19)

Found not during a human clarification round, but while executing the
human's "sync com prod, then start Phase 1" instruction: applying the V3
migration to Neon production succeeded, but a direct verification query
(`SELECT count(*) FROM scheduling.specialties`) returned `relation
"scheduling.specialties" does not exist`. Investigation showed the same is
true of the local Docker Compose database — `docker-compose.yml` does not
mount `db/init/` as Postgres `initdb.d` content, nothing in the repo
references `db/init/001_schema.sql`/`002_seed_and_schedule.sql` outside
`specs/`, and the V1 baseline Alembic migration
(`20260810_0001_v1_baseline.py`) only creates `content`/`customer_service`.
**Every prior version of `spec.md` §2, `plan.md` §3, and `data-model.md`
that described the `scheduling` schema as "real," "already exists," or
needing "no schema change" was wrong in every environment this project
has, not just production** — D-024's "dormant" framing was accurate in
spirit (the schema was always meant to stay inert until a feature like
this one activated it) but the artifacts overstated *how* dormant: not
created-and-unused, but never created at all.

- **Repair:** `spec.md` §2 gained a correction bullet; `plan.md` §3 was
  rewritten to describe two migrations instead of one; `data-model.md`
  gained a new §5 (the schema-creation migration, ported faithfully from
  `db/init/001_schema.sql`/`002_seed_and_schedule.sql` for only the
  objects this feature uses) and renumbered its old §5-§8 to §6-§9;
  `tasks.md` Phase 1 gained **T008** ahead of T009, with T009 now chained
  after it; `acceptance.md` §0 now checks both migrations, including a
  spot-check that T008 does *not* create `slot_offers`/
  `ensure_demo_availability()`/`appointments`/`identity.*`/`billing.*`;
  `checklists/security.md`/`traceability.md`/`requirements.md` gained
  matching items.
- **Scope check:** this is a mechanical/deployment-correctness repair, not
  a new outcome or a change to any of AA-1 through AA-10 — the schema's
  *shape* T008 creates is an unmodified port of what `001_schema.sql`/
  `002_seed_and_schedule.sql` already specified (scoped down to exclude
  the tables D-024 keeps dormant), not a redesign. No new human decision
  was required; this does not touch Constitution Article III/VIII/IX, and
  Amendment 1.1.0's scope (§10 above) is unaffected — T008 does not touch
  `customer_service.conversations`/`messages` at all.
- **Consistency re-check:** confirmed no other artifact in this package
  still asserts the `scheduling` schema pre-exists — grepped for
  "already exist"/"predates Alembic"/"no schema change" across
  `spec.md`/`plan.md`/`data-model.md`/`tasks.md`/`acceptance.md`/
  `checklists/*.md` after the repair; every remaining hit is either this
  section's own history (§3/§5, deliberately preserved as a record of what
  was believed before this correction, per this document's own convention
  of appending rather than rewriting past sections) or refers to a
  genuinely unrelated already-existing column (`content.qa_entries.dynamic_resolver`,
  `spec.md` §2's first bullet, correctly unaffected by this finding).

## 13. Verdict (sixth-round design, superseded — see §14-15)

No unresolved contradiction between `spec.md`, `plan.md`, `data-model.md`,
`tasks.md`, and `acceptance.md` as of this latest review; §2's finding,
§6's/§8's/§10's re-checks/fixes, and §12's schema-creation correction are
all repaired in place before Phase 1 implementation began (T008 had not
yet been executed at the time of this review — the repair is to the
artifacts, ahead of the code). Every bound Constitution Amendment 1.1.0
state still has a specific, checked enforcement mechanism (§10's table),
untouched by §12's correction. `checklists/requirements.md`'s final item
("cross-artifact analysis reports no material contradiction") is satisfied
by this document. This feature is ready to proceed with `tasks.md` Phase 1
implementation, starting with T008. Given AA-10's exceptional nature,
`tasks.md` Phase 10/T082 must still re-run the containment review one more
time against the *real* implementation before the feature can be declared
DONE — a stronger bar than this package's other outcomes get.

## 14. Revision review — seventh round: AA-9 scoped to the generalist specialty (2026-08-19)

Human instruction, given after Phase 5 was already done and Phase 4's own
live verification had already surfaced the mastologia-only consequence as
a residual risk (§4's now-superseded bullet): "faça este botão ir para a
oncologia geral." Unlike §12's finding, this one *is* a human decision
about product behavior, not a factual correction of a wrong claim — AA-9's
original "flat count, not scoped to any specialty" was accurate to what
the code did and was a deliberate choice at the time; the human has now
chosen differently, informed by seeing the real consequence.

- **Repair:** `spec.md` AA-9 items 2 and 4 rewritten to require
  specialty-scoping to `oncologia-geral`; `plan.md` §4b gained a
  correction note ahead of the algorithm; `scheduling/seeding.py`'s
  `count_available_on()`/`active_professional_specialty_pairs()`/
  `create_slots_on()` all gained a `specialty_id` parameter, and a new
  `_generalist_specialty_id()` resolves it once per call in
  `ensure_seed_availability()`; `acceptance.md` §D/§E updated; §4's
  residual-risk bullet marked superseded rather than deleted.
- **Import direction check:** `seeding.py` now imports `GENERALIST_SLUG`
  from `availability.py` to avoid duplicating the slug string. This is the
  *reverse* of the one direction this package structurally forbids
  (`availability.py` must never import `seeding.py`, verified by T031's
  structural test) — confirmed `availability.py` still imports nothing
  from `seeding.py` after this change; the forbidden direction remains
  forbidden and untouched.
- **Test repair:** `test_appointment_seeding.py`'s
  `test_deactivated_professional_never_receives_a_generated_slot` was
  deactivating a *mastologia* professional (`...0001`) — meaningless
  now that the seed action never considers non-generalist professionals
  at all. Repointed to one of the generalist specialty's own 3
  professionals (`...0010`). All `count_available_on()` call sites across
  the test file updated to pass the generalist `specialty_id` explicitly.
  Live-verified after the fix: all 4 seeded slots land on
  `oncologia-geral` (previously `mastologia-oncologica`), and a real
  no-keyword customer query now resolves against real generalist data
  end-to-end (`"Oncologia geral (triagem) — Dr. Eduardo Vasconcelos
  (simulação)..."`) instead of silently zero-matching against a specialty
  the button never populates.
- **Scope check:** touches only AA-9's own seed-action scoping — does not
  change AA-1 through AA-8, does not touch Constitution Article III/VIII/IX,
  and does not affect Amendment 1.1.0's booking-script exception (§10's
  table remains unaffected — AA-10 reads whichever specialty a prior
  resolved `appointment_availability` generation was about, not a fixed
  one, so it already handles either mastologia or generalist data
  correctly without change).

## 15. Verdict (eighth-round design, superseded — see §16-17)

No unresolved contradiction between `spec.md`, `plan.md`, `data-model.md`,
`tasks.md`, and `acceptance.md` as of this latest review; §2's finding,
§6's/§8's/§10's re-checks/fixes, §12's schema-creation correction, and
§14's AA-9 generalist-scoping correction are all repaired in place and
verified against the real implementation (unlike §12, this one *was*
implemented and live-verified as part of this same review — `tasks.md`
Phase 4's evidence updated accordingly). Every bound Constitution
Amendment 1.1.0 state still has a specific, checked enforcement mechanism
(§10's table), unaffected by §14. `checklists/requirements.md`'s final
item is satisfied by this document. Phases 1-5 remain DONE with corrected,
re-verified evidence; Phase 6 (the operator-workspace button) is next.

## 16. Revision review — Phase 9 implementation: two findings in the amendment's own mechanism (2026-08-19)

Both found while actually implementing `send_scripted_message()`, not
during artifact review — the kind of gap only implementing the exact
authorized behavior surfaces. Given extra scrutiny per `plan.md` §8b/§13's
own emphasis, both are recorded here in full rather than only in
`tasks.md`.

- **Finding 1 — the exception was structurally impossible without a
  schema change.** `customer_service.messages`' V1-baseline `messages_check`
  constraint required every `OPERATOR`-authored row to carry a non-null
  `operator_id`. `send_scripted_message()` has no operator in its call
  context by design (that is the entire point of the amendment) — its
  first real insert attempt failed the constraint outright. This was not
  caught by any prior artifact review because every review to this point
  reasoned about the *application-level* call graph (who calls what,
  which dependency gates which path) and never checked the *database's
  own* pre-existing invariants for a conflict with the newly-authorized
  behavior.
  - **Repair:** migration `20260819_0004` adds exactly one disjunct to the
    constraint: `author_type='OPERATOR' AND operator_id IS NULL AND
    autonomous_source='booking_script'`. This is not a loosening for its
    own sake — it is drawn as narrowly as the amendment itself, reusing
    the same `autonomous_source` column (`CHECK`-constrained to its one
    legal value) as the gate. `data-model.md` §8 updated;
    `checklists/security.md`'s AA-10 item group still holds — this
    strengthens it (a `NULL` `operator_id` on an `OPERATOR` message is now
    *only* reachable when `autonomous_source='booking_script'`, at the
    database level).
- **Finding 2 — same-transaction messages could display out of order.**
  Postgres's `now()` (the `created_at` column's server default) is fixed
  for the entire transaction, not per-statement. `advance_booking_script()`
  sends 2-3 messages per call, all in one transaction (by design — no
  debounce, `plan.md` §8b "Trigger"), so they would all receive an
  *identical* `created_at`. The real customer-facing message ordering
  (`conversations/projections.py`: `ORDER BY created_at, id`) then
  tie-breaks on `id`, a random UUID — meaning, e.g., "Informe seu CPF..."
  could have displayed to the customer *before* "Agendamento realizado."
  Surfaced by `test_booking_script_flow.py`'s own
  `test_second_booking_intent_after_completed_flow_starts_fresh` failing
  under full-suite execution (timing-sensitive) while passing in
  isolation — a genuine flake, not a test bug, traced to its root cause
  rather than papered over with a retry.
  - **Repair:** `send_scripted_message()` now sets `created_at` from
    Python's wall clock (`datetime.now(UTC)`) explicitly, rather than
    relying on the column's server default. Each call already does a real
    `session.flush()` (a DB round-trip) before the next, so consecutive
    calls are guaranteed measurably distinct in practice. Verified stable
    across 3 consecutive full-suite runs after the fix.
  - **Scope check:** this is scoped to `send_scripted_message()`'s own
    inserts only — the shared `Message` model's `server_default=now()`
    behavior is unchanged for every other (V1/V2/V3) code path, all of
    which only ever create one message per transaction and were never at
    risk of this collision.

## 17. Verdict (current)

No unresolved contradiction between `spec.md`, `plan.md`, `data-model.md`,
`tasks.md`, and `acceptance.md` as of this latest review. Both §16
findings are implementation-mechanics corrections, not scope or outcome
changes — they do not touch AA-1 through AA-9, and Amendment 1.1.0's
bound-by-bound enforcement table (§10) is strengthened, not weakened, by
Finding 1. `tasks.md` Phase 9 (T093-T098) is DONE with full evidence,
including both findings. Phases 1-9 are now DONE; Phase 10 (acceptance
automation) remains, per this package's own Handoff note, for a fresh
session to pick up.

## 18. Phase 10 post-implementation convergence and final verdict (2026-08-19)

T082 repeated the V2/V3 closure method against the real implementation,
not merely the artifacts: each `spec.md` outcome was traced through
`plan.md`, migrations/models/services/routes, executable tests,
`acceptance.md`, and the live Postgres/OpenAPI surfaces. Containers were
rebuilt from the worktree; Alembic was at `20260819_0004`; the database
catalog showed 4 specialties/12 professionals, the generalist's exact
price/duration, both AA-10 `CHECK` constraints, and no deferred
appointments/identity/billing tables.

### Findings and repairs

| Finding | Evidence | Repair |
|---|---|---|
| **AA-10 raw-input non-retention was false-green.** `spec.md` outcome 13 said CPF/payment inputs were never persisted, but `send_customer_message()` created the ordinary customer `Message` with `payload.body` before calling the script. T095 inspected only operator-message bodies and audit payloads, so it could pass while the customer row retained exactly the submitted value. | Direct call-path review of `anonymous_access/router.py`; comparison with T095's query predicate. This is material because it concerns the amendment's own privacy boundary, not test wording. | Added `persisted_customer_body()`: at `AWAITING_CPF`/`AWAITING_PAYMENT`, parsing still receives request-local text but the durable customer message contains a fixed disclosure marker. T095 now inspects **all** message rows. The real HTTP booking smoke also queries `Message` and `AuditEvent` and rejects every submitted string. Spec/plan/data-model/acceptance/checklists were clarified consistently: the formatted CPF remains only in the exact fixed confirmation output the human required, never as structured identity state. |
| Artifact count/status drift after implementation. | Implementation has four migrations (the fourth is §16's `messages_check` correction), while spec/plan/data-model still summarized three. Spec §6 retained the superseded specialty-agnostic AA-9 rule; plan summary omitted AA-10; traceability called live tests "planned" and said scheduling shape was unchanged. | Updated the governing artifacts to four migrations, generalist-scoped AA-9, four separated technical pieces, accurate write boundaries, real audit payload shape, and executed evidence. Historical revision sections remain intact. |
| Full E2E suite contained timing/locator assumptions below the real runtime envelope. | First full Playwright run: 3 failures while DB rows showed real-provider generation durations of 5.284s and 8.741s; subsequent focused runs exposed `.first()` re-resolution after queue polling and whole-panel text comparisons that included controls. | Bounded the affected scenarios (20s/45s assertions; 90s/150s tests), captured the selected conversation label before clicking, and compared `.message-body` elements. No product assertion was removed. Final full run: 11 passed, 1 maturity-mode skip by design. |
| Requested smoke inventory said three new V4 scripts; repository/package has two. | `git ls-tree 1810d1a` and `rg --files app/tests` both show only `smoke_v4_appointment_availability.py` and `smoke_v4_booking_script.py`. | Stopped and reported the mismatch; after the human said "Prossiga", executed both real scripts and all 14 pre-existing scripts. Recorded the discrepancy in acceptance rather than inventing coverage. |

### Independent AA-10 containment re-verification

The handoff's strongest instruction was executed independently after the
implementation review:

| Bound | Phase 10 evidence | Result |
|---|---|---|
| One exceptional construction function | AST enumeration found exactly `booking_script/service.py::send_scripted_message`; the ordinary site remains `send_operator_message(CurrentOperator, ...)`. | PASS |
| One import/call boundary | `send_scripted_message` has no import outside `booking_script/`; `advance_booking_script` is called exactly once, from `send_customer_message`. | PASS |
| One provenance value | Every exceptional row has `autonomous_source='booking_script'`; every send emits `booking_script.autonomous_message_sent` with IDs/step only. | PASS |
| Database-level containment | `messages_check` permits null `operator_id` only for `author_type='OPERATOR' AND autonomous_source='booking_script'`; the autonomous-source column accepts no other non-null value. | PASS |
| Fixed/non-LLM output | Booking module imports no AI provider; real HTTP smoke reproduced all 10 exact outputs and both retry branches with zero operator clicks. | PASS |
| Context guard | Script starts only after a real resolved `appointment_availability` generation; dedicated negative integration test passes. | PASS |
| Sensitive-input boundary | Raw CPF/payment submissions remain request-local and are replaced before durable customer-message insertion; HTTP smoke verifies `Message`/`AuditEvent` directly. | PASS |

Command rerun specifically required by the handoff:

```text
pytest -q tests/test_booking_script_containment.py
....  4 passed
```

### Final execution evidence

- backend: `ruff` PASS; `mypy customer_care` PASS (48 source files);
  `pytest -q` PASS (119 tests) against the real Docker Postgres;
- frontend: ESLint PASS; `tsc --noEmit` PASS; Vitest 17/17 PASS;
  production build PASS;
- rebuilt Compose: Postgres 17/pgvector healthy, backend ready, frontend
  served the new build, Alembic at head;
- smoke: all 16 actual `smoke_*.py` scripts PASS, including real-provider
  smoke and both V4 scripts; corpus restored through the real provider
  after the changed-ingestion test;
- Playwright: 11 applicable scenarios PASS, 1 N1-only branch skipped by
  design, against the rebuilt containers;
- OpenAPI: live operator-only route/security matches the package delta.

**Final verdict: GO / DONE.** All 15 `spec.md` §4 outcomes have real
execution evidence; T080-T082 are complete; the AA-10 exception remains
contained to one function/one trigger and now also satisfies its raw-input
non-retention requirement. No unresolved material divergence remains.
