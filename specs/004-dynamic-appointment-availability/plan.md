# Implementation Plan: Dynamic Appointment Availability

Ratifies `spec.md`'s confirmed outcomes (AA-1..AA-8) into concrete
architecture, data-model, and testing decisions. Written after all `spec.md`
§5 clarifications were resolved with the human (2026-08-18).

## 1. Technical summary

Add one new named resolver, `appointment_availability`, reachable only when
`content.qa_entries.dynamic_resolver = 'appointment_availability'` and
`dynamic_data_required = true` — everything else about draft generation is
unchanged. The resolver:

1. deterministically extracts a specialty/date-phrase/period from the
   customer's own query text (already available at the call site — no new
   input surface);
2. ensures near-future `scheduling.schedule_slots` rows exist for the next
   few business days (idempotent, insert-only, never touches an existing
   slot's status) using the existing, proven
   `scheduling.next_business_day()` SQL function rather than reimplementing
   its Saturday/Sunday/holiday logic;
3. queries real, current `schedule_slots` (never a pre-materialized,
   date-stamped `slot_offers` row — sidestepping the staleness problem
   entirely, per `spec.md` §5 resolution 2);
4. renders a deterministic, template-substituted answer (no LLM call, no
   LLM rewrite — matching D-028's precedent exactly) or aborts to the
   existing `ABSTAIN`/`DYNAMIC_DATA_UNAVAILABLE` path.

No new API route, no new frontend surface, no new migration for the
`scheduling` schema's shape (it already exists and is correct for this).
One small, additive migration is needed for new SQLAlchemy ORM mappings'
supporting indexes if profiling shows they're missing (§3) — otherwise this
is a backend-only, internal resolution-path change plus a Q&A content
cleanup pass.

## 2. Module boundaries

New module: `app/customer_care/scheduling/` (mirrors `knowledge/` — a
sibling domain module, not a submodule of `knowledge/`, since it owns a
genuinely different schema and has nothing to do with knowledge-base CRUD):

- `scheduling/__init__.py`
- `scheduling/models.py` — new read-mostly ORM mappings for
  `scheduling.specialties`/`professionals`/`professional_specialties`/
  `units`/`holidays`/`schedule_slots` (§3). Not added to
  `infrastructure/models.py` — that file is `content`/`customer_service`
  schema only today; scheduling gets its own file for the same reason
  `knowledge/dynamic_binding.py` keeps its allowlist separate from the
  generic CRUD router.
- `scheduling/availability.py` — the resolver itself: keyword extraction,
  slot-ensure, query, deterministic render. Exposes one function,
  `resolve_appointment_availability(session, query_text) -> DynamicResolution`
  (reusing `knowledge/dynamic_binding.py`'s existing `DynamicResolution`/
  `DynamicResolutionError` types — no new result-shape vocabulary).

`ai/router.py`'s `dynamic_pattern_result()` gains a small dispatch table:

```python
from customer_care.scheduling.availability import resolve_appointment_availability

NAMED_RESOLVERS: dict[str, Callable[[DbSession, str], DynamicResolution]] = {
    "appointment_availability": resolve_appointment_availability,
}

def dynamic_pattern_result(session, evidence, query_text: str) -> ...:
    ...
    qa = session.get(QAEntry, hit.matched_qa_id)
    if not qa or not qa.dynamic_data_required:
        return None
    try:
        resolver = NAMED_RESOLVERS.get(qa.dynamic_resolver) if qa.dynamic_resolver else None
        resolution = resolver(session, query_text) if resolver else resolve_dynamic_pattern(session, qa)
        return GenerationResult("ANSWER", resolution.pattern_text, None, [str(evidence[0].retrieval_hit_id)]), True, None
    except DynamicResolutionError as exc:
        return GenerationResult("ABSTAIN", "", "DYNAMIC_DATA_UNAVAILABLE", []), False, exc.cause
```

When `qa.dynamic_resolver` is set to a name **not** in `NAMED_RESOLVERS`
(`price_lookup`, `payment_simulator`, `insurance_lookup` — unauthorized by
this cycle), the `resolver` lookup returns `None` and execution falls
through to the existing generic `resolve_dynamic_pattern(session, qa)` path
— which raises `DynamicResolutionError` exactly as it does today, because no
`qa_dynamic_bindings` row exists for them. **No special-casing is needed to
keep those three abstaining** — it is a direct, structural consequence of
this fallthrough, not a separate check that could later be forgotten
(acceptance outcome 8).

`query_text` is threaded from both call sites:

- `generate_draft()` already builds `query` (joined selected-message bodies
  + manual search text) for retrieval — the same string is passed through.
- `select_evidence()` (the "Buscar evidências" single-hit path) has no
  message context by design (V2-3 invariant: independent of
  `message_selections`). It fetches the originating `RetrievalRun.query_text`
  for the hit being selected (`hit.retrieval_run_id`) and passes that —
  the operator's own manual-search text, the closest analog to a "customer
  query" available at that call site. An empty/missing value is valid input
  (§4) — it just means no dimension gets filtered on.

## 3. Persistence: new read-mostly ORM mappings, no schema migration

The `scheduling` schema (`db/init/001_schema.sql`) already has the exact
shape this feature needs (verified `spec.md` §2) — it predates Alembic and
was preserved as a "legacy... dormant" asset (D-024). This feature is the
first to actually read it, so it needs SQLAlchemy `Mapped`/`mapped_column`
classes, but **not** a migration: the tables, columns, indexes, and the
`UNIQUE (professional_id, starts_at)` constraint this feature's idempotent
insert relies on all already exist.

`scheduling/models.py`:

```python
class Specialty(Base):
    __tablename__ = "specialties"
    __table_args__ = {"schema": "scheduling"}
    specialty_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)

class Professional(Base):
    __tablename__ = "professionals"
    __table_args__ = {"schema": "scheduling"}
    professional_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    display_name: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean)

class ProfessionalSpecialty(Base):
    __tablename__ = "professional_specialties"
    __table_args__ = {"schema": "scheduling"}
    professional_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("scheduling.professionals.professional_id"), primary_key=True)
    specialty_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("scheduling.specialties.specialty_id"), primary_key=True)
    fixed_price_cents: Mapped[int] = mapped_column(Integer)
    appointment_duration_minutes: Mapped[int] = mapped_column(Integer)

class Unit(Base):
    __tablename__ = "units"
    __table_args__ = {"schema": "scheduling"}
    unit_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text)

class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"
    __table_args__ = {"schema": "scheduling"}
    slot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    unit_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("scheduling.units.unit_id"))
    specialty_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("scheduling.specialties.specialty_id"))
    professional_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("scheduling.professionals.professional_id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text)
```

(`holidays` is read via a raw scalar call to the existing
`scheduling.next_business_day(date)` SQL function, not mapped as an ORM
entity — no Python code needs a `Holiday` row directly, only the function's
already-correct output.)

This module is intentionally **not** imported by `bootstrap.py`'s
route registration — it has no router, no endpoint. It is imported only by
`scheduling/availability.py` and by tests. Constitution Article VIII
("modular monolith... no distributed infrastructure") is satisfied by
construction: this is one more module in the same backend process, reading
the same Postgres instance, with no new service.

## 4. AA-2/AA-8 — Slot-ensure and query algorithm

```python
BUSINESS_DAYS_AHEAD = 3  # small, fixed; not user-configurable (no settings sprawl for a demo constant)
SLOT_HOURS_WEEKDAY = (9, 11, 14, 16)
SLOT_HOURS_SATURDAY = (8, 9, 10, 11)

def ensure_near_future_slots(session: Session) -> None:
    """Idempotent: INSERT ... ON CONFLICT (professional_id, starts_at) DO
    NOTHING for the next BUSINESS_DAYS_AHEAD business days, one slot per
    professional per fixed hour. Never updates/deletes an existing slot —
    an already-consulted/held slot (once booking exists, out of this
    feature's scope) is never silently regenerated out from under it. Only
    `professional_specialties` rows for an `active=true` professional are
    considered — a deactivated professional never gets new slots generated
    (found during this plan's own cross-artifact review, `analysis.md`
    finding 1: the pseudocode originally iterated every
    `professional_specialties` row regardless of `Professional.active`).
    Called at the start of every resolution — cheap (a handful of
    idempotent inserts against a unique-indexed table) and requires no
    scheduler/cron (Constitution Article VIII)."""
    reference = today_in_sao_paulo()
    for offset in range(1, BUSINESS_DAYS_AHEAD + 1):
        target = next_business_day_sql(session, reference + timedelta(days=offset))
        hours = SLOT_HOURS_SATURDAY if target.isoweekday() == 6 else SLOT_HOURS_WEEKDAY
        active_pairs = select(ProfessionalSpecialty.professional_id, ProfessionalSpecialty.specialty_id).join(Professional).where(Professional.active.is_(True))
        for professional_id, specialty_id in session.execute(active_pairs):
            for hour in hours:
                starts_at = combine_sao_paulo(target, hour)
                session.execute(
                    pg_insert(ScheduleSlot)
                    .values(unit_id=DEFAULT_UNIT_ID, specialty_id=specialty_id, professional_id=professional_id, starts_at=starts_at, ends_at=starts_at + duration, status="available")
                    .on_conflict_do_nothing(index_elements=["professional_id", "starts_at"])
                )

def resolve_appointment_availability(session: Session, query_text: str) -> DynamicResolution:
    ensure_near_future_slots(session)
    params = extract_parameters(query_text)  # §5
    query = select(ScheduleSlot, ...).where(ScheduleSlot.status == "available", ScheduleSlot.starts_at >= now_in_sao_paulo())
    if params.specialty_id:
        query = query.where(ScheduleSlot.specialty_id == params.specialty_id)
    if params.date_range:
        query = query.where(ScheduleSlot.starts_at.between(*params.date_range))
    if params.period:  # "manhã"/"tarde"
        query = query.where(extract_hour_in(params.period_hours))
    rows = session.execute(query.order_by(ScheduleSlot.starts_at).limit(4)).all()
    if not rows:
        raise DynamicResolutionError(cause=f"no schedule_slots matched params={params}")
    return DynamicResolution(pattern_text=render_offers(rows))
```

`next_business_day_sql()` is a one-line
`session.execute(text("SELECT scheduling.next_business_day(:d)"), {"d": date_value}).scalar_one()`
wrapper — reusing the existing, already-correct SQL function rather than
reimplementing the holiday/Saturday rule in Python (single source of truth;
`scheduling.holidays` stays the only place that rule's data lives). The
`:d` bind parameter is always a Python `date` computed by this module, never
user/LLM-supplied text (§13).

## 5. AA-3 — Deterministic keyword extraction

A small, explicit, testable vocabulary — not fuzzy matching, not an LLM
call:

```python
SPECIALTY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "mastologia-oncologica": ("mastologia", "mama", "peito"),
    "cirurgia-colorretal": ("colorretal", "intestino", "cólon", "colon", "reto"),
    "segunda-opiniao": ("segunda opinião", "segunda opiniao"),
}
DATE_KEYWORDS: dict[str, ...] = {"amanhã": ..., "amanha": ..., "semana que vem": ..., "próxima semana": ..., "sábado": ..., "sabado": ..., "domingo": ...}
PERIOD_KEYWORDS = {"manhã": (0, 12), "manha": (0, 12), "tarde": (12, 24)}
```

Matching is case-insensitive substring search over the query text, first
match wins per dimension (no dimension is required — an unmatched one is
simply not filtered on, `spec.md` AA-3). This lives entirely in
`scheduling/availability.py`, is pure/synchronous/side-effect-free, and is
unit-tested directly with no database — the highest-value, cheapest tests
this feature has.

## 6. AA-4/AA-5 — Evidence shape and deterministic rendering

`resolve_appointment_availability` returns up to 4 rows. Each becomes an
`AIGenerationSource`-eligible evidence item exactly like every other
resolved generation (`use_order` 1..4, all cited — matches how
`full_parent_draft`/the generic dynamic-pattern path already report their
`used_hit_ids`, except here there is one synthetic evidence item per
returned slot rather than one for the whole resolution, since a customer
choosing between four real times is the actual UX this data is for). The
`retrieval_hit_id` used for these evidence items is the *matched QA entry's*
single hit (unchanged from today) — the four slots are additional structured
fields on the rendered text, not additional `RetrievalHit` rows (no new
table; `scheduling.schedule_slots.slot_id` values appear only inside the
rendered `pattern_text`/audit payload, never as a citable knowledge-evidence
identifier of their own — this stays consistent with `RetrievalHit` meaning
"a knowledge-base match," not "a live data row").

Rendering template (fixed, Portuguese, matches the existing Q&A tone):

```
{specialty_display_name} — {professional_name}, {unit_name}
{weekday_pt} {DD/MM} às {HH:MM} (America/São_Paulo) — R$ {price} (simulação)
```

joined, one line per slot, up to 4 — never composed or rewritten by an LLM
call (AA-5; matches D-028's `dynamic_pattern_result()` contract of
`model = "not-applicable"` for every dynamic-pattern-resolved generation).

## 7. AA-7 — Audit

Reuses `ai.dynamic_pattern_resolved`/`ai.dynamic_pattern_fallback` exactly
(no new event type — `EVENT_CATALOG.md` gains a note, not a new row,
mirroring how V3-2/V3-6 needed none). `ai.dynamic_pattern_resolved`'s
payload gains two optional fields when the resolver used is
`appointment_availability`: `specialty_slug` (nullable — the matched
specialty, if any) and `slot_count` (how many rows were returned, always
1-4) — both safe, non-identifying, already-public-vocabulary values (a
specialty slug is public marketing copy, not PII). The failure path's
`cause` string (already audit-only, never customer-facing, per D-028)
carries the same diagnostic detail the `f"no schedule_slots matched
params={params}"` example above shows — parameters, not raw SQL, not table
internals beyond what the existing dynamic-pattern fallback cause already
allows.

## 8. Q&A content: evaluate and keep only what's necessary (`spec.md` §5.3)

Final entry list is authored in `tasks.md`/a data-seed task, but the shape
is decided here: keep a small set (roughly 4-6) of `agenda`-category entries
with `dynamic_resolver = 'appointment_availability'`,
`dynamic_data_required = true`, covering the phrasings retrieval actually
needs to match a real customer message to *some* entry (exact wording
matters far less than usual here, since every match dispatches to the same
deterministic resolver regardless of which entry's canned `answer_markdown`
matched — the resolver's own output replaces it entirely on a successful
resolution). The 5 entries describing booking/hold/identity/payment-
confirmation content that this feature does not implement (`spec.md` §6) are
**soft-deactivated** (`is_active = false`) via the existing V2-8 CRUD
mechanism — never hard-deleted (this project's established pattern
everywhere else: preserve historical/audit continuity, `data-model.md`
precedent throughout V1-V3) — done through a one-off authenticated
operator-CRUD script (`scripts/`, matching `seed_evaluation_cases.py`'s
precedent of seeding through the real API, not raw SQL) rather than editing
`db/init/004_qa.sql` in place (that file is frozen historical/bootstrap
data per V1's own `plan.md` §1 rule: "do not edit or treat them as the
migration history").

## 9. Security

- The resolver is reachable only through the exact same authenticated-
  operator, assignment-gated, effective-N2 paths every other draft
  generation already requires (`draft()`/`select_evidence()`) — no new
  authorization surface.
- `scheduling.*` read access is scoped to exactly the columns
  `scheduling/models.py` maps — no raw/dynamic SQL, no user-supplied table
  or column name reaches a query (unlike V2-6's dynamic-binding mechanism,
  this resolver is fully hardcoded Python, so there is no allowlist to
  bypass in the first place).
- `ensure_near_future_slots()` only ever `INSERT ... ON CONFLICT DO NOTHING`
  against `schedule_slots` — it cannot update an existing row's `status`,
  cannot delete, and is not reachable from any request the *customer*
  originates directly (only as a side effect of an operator-triggered draft
  resolution).
- No `identity.*`/`billing.*`/`scheduling.appointments` table is imported,
  queried, or referenced anywhere in `scheduling/models.py` or
  `scheduling/availability.py` — a negative test (acceptance outcome 7)
  proves this structurally via module-level introspection, not just
  behaviorally.

## 10. Testing implementation

Same approach as V1-V3: real PostgreSQL for integration tests, no fake
adapter needed (there is no external provider in this resolver's path —
it never calls the LLM/embedding provider, matching `model = "not-applicable"`).

- `test_appointment_availability_keywords.py` — pure unit tests for
  `extract_parameters()`: each specialty/date/period keyword, no match
  (all dimensions `None`), mixed-case, and a query containing no known
  keyword at all.
- `test_appointment_availability_resolver.py` — integration tests against a
  real (test) database: `ensure_near_future_slots()` is idempotent
  (calling it twice produces the same row count); a specialty-filtered
  query returns only that specialty's slots; a Saturday-only query returns
  only `SLOT_HOURS_SATURDAY` times; a Sunday/holiday date phrase resolves
  through `next_business_day()`; zero-match (e.g. an unseeded specialty)
  raises `DynamicResolutionError`; the rendered text contains no raw
  table/column/internal-error string.
- `smoke_v4_appointment_availability.py` (naming matches this feature's own
  identity, not literally "v4" — see `spec.md` §5.5) — real end-to-end HTTP
  smoke: a real customer message naming a specialty/day, generate a draft,
  confirm `ANSWER` with real (synthetic) slot data, confirm
  `model == "not-applicable"`, confirm no LLM provider was called, confirm
  `price_lookup`/`payment_simulator`/`insurance_lookup` Q&A entries (if any
  remain seeded) still abstain.
- Regression: existing `smoke_v2_dynamic_pattern.py` and its
  `qa_dynamic_bindings`-based fixture continue to pass unmodified — the
  fallthrough in `dynamic_pattern_result()` must not change generic-binding
  behavior for entries with no `dynamic_resolver` set at all.

## 11. Performance

`ensure_near_future_slots()` is O(business days × professionals × hours) —
with today's seed data (9 professionals × 4 hours × 3 days = 108 rows,
`ON CONFLICT DO NOTHING`), this is a handful of milliseconds against a
unique-indexed table, run synchronously inside the existing draft-generation
request. No caching, no background job, no new infrastructure — consistent
with every other V1-V3 decision to avoid infrastructure until a measured
need exists (Constitution Article VIII; none exists here at demo scale).

## 12. Deliverables

- `app/customer_care/scheduling/__init__.py`, `models.py`, `availability.py`
- `ai/router.py`: `NAMED_RESOLVERS` dispatch, `dynamic_pattern_result()`
  signature gains `query_text`, both call sites updated
- `docs/architecture/EVENT_CATALOG.md`: note on `ai.dynamic_pattern_resolved`'s
  two new optional payload fields (no new event type)
- Q&A content cleanup script (§8) — soft-deactivates the 5 out-of-scope
  `agenda` entries, keeps/edits the in-scope ones
- `app/tests/test_appointment_availability_keywords.py`,
  `test_appointment_availability_resolver.py`,
  `smoke_v4_appointment_availability.py`
- `data-model.md`, `tasks.md`, `acceptance.md`, `analysis.md`,
  `checklists/{requirements,security,traceability}.md`

## 13. Prohibited shortcuts

- no raw/dynamic SQL built from user or LLM-provided strings anywhere in
  `scheduling/availability.py` — every query is hardcoded, only the *values*
  (matched specialty id, date range) are parameterized;
- no LLM call, no LLM rewrite, anywhere in the resolved-`ANSWER` path
  (AA-5) — `model` must be `"not-applicable"`, exactly like every other
  dynamic-pattern resolution;
- no write to `scheduling.appointments`/`appointment_events`,
  `identity.*`, or `billing.*` — not even a stub/placeholder row "for
  later," which would violate D-024's dormancy and pre-empt a not-yet-
  authorized future feature;
- no new scheduler/cron/background-job process for freshness — the
  idempotent-insert-on-resolution approach is the whole answer;
- no new customer-facing endpoint or frontend change — this is entirely an
  internal resolution-path change, exactly like V2-6's original dynamic-
  binding mechanism.
