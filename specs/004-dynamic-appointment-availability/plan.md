# Implementation Plan: Dynamic Appointment Availability

Ratifies `spec.md`'s confirmed outcomes (AA-1..AA-9, plus AA-3a) into
concrete architecture, data-model, and testing decisions. Written after
all four `spec.md` §5 clarification rounds were resolved with the human
(2026-08-18): the first shaped AA-1..AA-8; the second narrowed AA-2 to
purely read-only and added AA-9; the third deferred a full scheduling CRUD
to future work and identified the "customer doesn't know which specialty"
content gap; the fourth corrected how to close that gap — a seeded
**generalist** specialty (AA-3a), not an unfiltered search.

## 1. Technical summary

Three pieces, cleanly separated by who triggers them and what they're
allowed to do:

1. **Query path (AA-1..AA-8), purely read-only.** A new named resolver,
   `appointment_availability`, reachable only when
   `content.qa_entries.dynamic_resolver = 'appointment_availability'` and
   `dynamic_data_required = true`. It deterministically extracts a
   specialty/date-phrase/period from the customer's own query text — always
   resolving to *some* specialty, defaulting to the new generalist one when
   nothing more specific matched (AA-3a) — `SELECT`s real, current
   `scheduling.schedule_slots` rows, and renders a deterministic,
   template-substituted answer (no LLM call, no LLM rewrite) — or aborts to
   the existing `ABSTAIN`/`DYNAMIC_DATA_UNAVAILABLE` path. **It never
   writes anything, under any circumstance.**
2. **Seed action (AA-9), the only *runtime* write path, operator-triggered
   only.** A new button on the operator workspace calls a new endpoint
   that idempotently ensures exactly 1 available slot on D+1 and 3 on D+7
   exist (business-day-aware, reusing `scheduling.next_business_day()`),
   creating only what's missing, within 08:00-18:00. If already
   sufficient, it does nothing and reports so.
3. **One new migration (AA-3a), applied once, not a runtime write path.**
   Seeds the generalist `scheduling.specialties` row plus a small number of
   `professionals`/`professional_specialties` rows tied to it — reference
   data, the same kind the original `db/init/002_seed_and_schedule.sql`
   already contains, just added the correct way (a migration) instead of
   editing that frozen file.

This is no longer a purely internal, route-less change (unlike the plan's
first draft): AA-9 needs one new operator-only endpoint and one small
frontend button, and AA-3a needs one new migration. The query path
(AA-1..AA-8) itself still needs neither a route nor a migration of its
own — it only reads whatever rows exist, however they got there.

## 2. Module boundaries

New module: `app/customer_care/scheduling/` (mirrors `knowledge/` — a
sibling domain module, not a submodule of `knowledge/`, since it owns a
genuinely different schema and has nothing to do with knowledge-base CRUD):

- `scheduling/__init__.py`
- `scheduling/models.py` — new read-mostly ORM mappings for
  `scheduling.specialties`/`professionals`/`professional_specialties`/
  `units`/`schedule_slots` (§3).
- `scheduling/availability.py` — the **query path only**: keyword
  extraction, the read-only query, deterministic render. Exposes
  `resolve_appointment_availability(session, query_text) -> DynamicResolution`
  (reusing `knowledge/dynamic_binding.py`'s existing `DynamicResolution`/
  `DynamicResolutionError` types — no new result-shape vocabulary). **Never
  imports or calls anything that writes.**
- `scheduling/seeding.py` — the **seed action only** (AA-9): counts,
  decides what's missing, creates it. Exposes
  `ensure_seed_availability(session) -> SeedResult` (`created_d1: int`,
  `created_d7: int`, `already_sufficient: bool`). Deliberately a separate
  file from `availability.py`, not just a separate function in it — the
  query path's module never needs to import anything write-capable, so it
  structurally cannot (acceptance outcome 4 is provable by module-level
  introspection, not just by code review).
- `scheduling/router.py` — one endpoint,
  `POST /operator/scheduling/ensure-availability`, calling
  `ensure_seed_availability()` (§4b). Registered in `bootstrap.py` exactly
  like every other operator router.

`ai/router.py`'s `dynamic_pattern_result()` gains a small dispatch table
(unchanged from the first plan draft):

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
  (§5) — it just means no dimension gets filtered on.

## 3. Persistence: new read-mostly ORM mappings, plus two new migrations

**Correction (2026-08-19, found during the post-V3 production sync, before
Phase 1 started):** `db/init/001_schema.sql`/`002_seed_and_schedule.sql`
define the `scheduling` schema's *shape*, but define is all they do —
neither file is mounted as Postgres `initdb.d` content in
`docker-compose.yml`, referenced by any script, or ported into an Alembic
migration. Direct queries against both the local Docker Compose database
and the Neon production database confirm `scheduling.specialties` exists
in neither. D-024's "dormant" framing underclaimed this: the schema was
never activated at all, not created-once-then-idle. `spec.md` §2 (revised)
now states this correctly; this section and `data-model.md` §5 (new)
replace the "no schema change needed" framing this section originally had.

**This feature's Phase 1 therefore needs two things where the original
plan needed one:**

1. **A new schema-creation migration** (`data-model.md` §5) — creates the
   `scheduling` schema, but scoped to only what AA-2/AA-3a/AA-9 actually
   use: the `slot_status` enum, `units`, `specialties`, `professionals`,
   `professional_specialties`, `holidays` (+ its natural-key unique
   index), `schedule_slots`, and the `next_business_day()` function —
   ported faithfully from `001_schema.sql`, not redesigned. Also seeds the
   original 3 specialties/9 professionals/holidays from
   `002_seed_and_schedule.sql`, since the query path (AA-2/AA-3) needs
   real specialties to filter by from the moment this migration lands.
   Deliberately does **not** create `slot_offers`, `available_offers`, the
   `ensure_demo_availability()` function, `appointments`,
   `appointment_events`, or any `identity.*`/`billing.*`/`governance.*`
   table/schema — those remain exactly as unactivated as before (D-024,
   `spec.md` §6); this feature's own AA-9 write path replaces
   `ensure_demo_availability()`'s role, it does not need it to exist.
2. **The data-only AA-3a migration** (`spec.md` §5 item 10,
   `data-model.md` §6, unchanged in content from the original plan, only
   renumbered and now depending on migration 1 above having run first):
   seeding the new generalist specialty. This is reference/seed data, the
   same category of thing `002_seed_and_schedule.sql` already contains for
   the original 3 — it just can't go in that file (it is not wired into
   anything, per the correction above, and even if it were, V1 `plan.md`
   §1 froze it), so it goes in its own additive, forward-only Alembic
   migration, matching how V3's own migration also seeded reference data
   (its category backfill) alongside a schema change.

Once both migrations have run, the schema's shape needs no further
change for this feature — it needs SQLAlchemy `Mapped`/`mapped_column`
classes only. The `UNIQUE (professional_id, starts_at)` constraint the
seed action's idempotent insert relies on is created by migration 1, not
assumed to pre-exist.

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
already-correct output. Used only by `seeding.py`, §4b — the query path,
`availability.py`, has no reason to call it, since it no longer computes
D+1/D+7 at all.)

Neither `scheduling/models.py` nor `scheduling/availability.py` (the query
path) imports `bootstrap.py`'s route registration. `scheduling/router.py`
(the seed endpoint) does. Constitution Article VIII ("modular monolith...
no distributed infrastructure") is satisfied by construction: this is one
more module in the same backend process, reading/writing the same Postgres
instance, with no new service.

## 4. AA-1..AA-8 — Purely read-only query algorithm

```python
def resolve_appointment_availability(session: Session, query_text: str) -> DynamicResolution:
    """Reads only. Never writes. If `schedule_slots` has nothing to offer,
    this raises DynamicResolutionError — it does not generate data itself
    (that is exclusively scheduling/seeding.py's job, AA-9, triggered only
    by an explicit operator action, never as a side effect of a query)."""
    params = extract_parameters(query_text)  # §5
    query = (
        select(ScheduleSlot, Specialty, Professional, ProfessionalSpecialty, Unit)
        .join(Specialty, ScheduleSlot.specialty_id == Specialty.specialty_id)
        .join(Professional, ScheduleSlot.professional_id == Professional.professional_id)
        .join(ProfessionalSpecialty, and_(ProfessionalSpecialty.professional_id == ScheduleSlot.professional_id, ProfessionalSpecialty.specialty_id == ScheduleSlot.specialty_id))
        .join(Unit, ScheduleSlot.unit_id == Unit.unit_id)
        .where(ScheduleSlot.status == "available", ScheduleSlot.starts_at >= now_in_sao_paulo())
        .where(Specialty.slug == params.specialty_slug)  # always present — defaults to GENERALIST_SLUG (§5), never unfiltered
    )
    if params.date_range:
        query = query.where(ScheduleSlot.starts_at.between(*params.date_range))
    if params.period_hours:  # "manhã"/"tarde"
        query = query.where(extract(text("hour"), ScheduleSlot.starts_at).between(*params.period_hours))
    rows = session.execute(query.order_by(ScheduleSlot.starts_at).limit(4)).all()
    if not rows:
        raise DynamicResolutionError(cause=f"no schedule_slots matched params={params}")
    return DynamicResolution(pattern_text=render_offers(rows))
```

No `INSERT`/`UPDATE`/`DELETE` statement appears anywhere in this file — a
structural test (acceptance outcome 4) greps/introspects the module to
prove it, not just a behavioral test that happens not to trigger one.

## 4b. AA-9 — Seed action: algorithm, endpoint, and operator-workspace button

**Correction (2026-08-19, human decision: "faça este botão ir para a
oncologia geral"):** `count_available_on()` and `active_professional_specialty_pairs()`
below are now scoped to the generalist specialty (`GENERALIST_SLUG`,
`scheduling/availability.py`) specifically — both the count and the
candidate pairs filter on `Specialty.slug == GENERALIST_SLUG`. The
original design counted/created across all 4 specialties flat, which live
verification (Phase 5, `tasks.md`) showed meant the button would
essentially always seed `mastologia-oncologica` only (its professionals'
UUIDs sort lowest), never the generalist specialty most customer queries
actually need (AA-3a's default). `seeding.py` imports `GENERALIST_SLUG`
from `availability.py` to avoid duplicating the slug string — the reverse
import (`availability.py` importing from `seeding.py`) remains
structurally forbidden (§4/§9), this direction is not.

`scheduling/seeding.py`:

```python
SEED_HOUR_START, SEED_HOUR_END = 8, 18  # business hours, exclusive of 18:00 itself
TARGET_D1, TARGET_D7 = 1, 3

def ensure_seed_availability(session: Session) -> SeedResult:
    today = today_in_sao_paulo()
    d1 = next_business_day_sql(session, today + timedelta(days=1))
    d7 = next_business_day_sql(session, today + timedelta(days=7))
    count_d1 = count_available_on(session, d1)
    count_d7 = count_available_on(session, d7)
    if count_d1 >= TARGET_D1 and count_d7 >= TARGET_D7:
        return SeedResult(created_d1=0, created_d7=0, already_sufficient=True)
    created_d1 = create_slots_on(session, d1, TARGET_D1 - count_d1) if count_d1 < TARGET_D1 else 0
    created_d7 = create_slots_on(session, d7, TARGET_D7 - count_d7) if count_d7 < TARGET_D7 else 0
    return SeedResult(created_d1=created_d1, created_d7=created_d7, already_sufficient=False)

def count_available_on(session: Session, target_date: date) -> int:
    return session.scalar(
        select(func.count()).select_from(ScheduleSlot)
        .where(ScheduleSlot.status == "available", func.date(ScheduleSlot.starts_at) == target_date)
    )

def create_slots_on(session: Session, target_date: date, needed: int) -> int:
    """Tries (hour, professional×specialty) combinations in order —
    SEED_HOUR_START..SEED_HOUR_END-1, professionals round-robin within each
    hour — inserting with ON CONFLICT DO NOTHING and counting only actual
    inserts (a collision on an hour/professional pair already taken just
    moves to the next candidate, never double-counts). Stops as soon as
    `needed` real inserts have happened; with 9 seeded professionals × 10
    business hours = 90 candidate slots, this always has enough room for
    the small needed count (at most 3) this feature ever asks for."""
    created = 0
    pairs = active_professional_specialty_pairs(session)  # Professional.active == True only
    for hour in range(SEED_HOUR_START, SEED_HOUR_END):
        for professional_id, specialty_id, duration in pairs:
            if created >= needed:
                return created
            starts_at = combine_sao_paulo(target_date, hour)
            result = session.execute(
                pg_insert(ScheduleSlot)
                .values(unit_id=DEFAULT_UNIT_ID, specialty_id=specialty_id, professional_id=professional_id, starts_at=starts_at, ends_at=starts_at + duration, status="available")
                .on_conflict_do_nothing(index_elements=["professional_id", "starts_at"])
                .returning(ScheduleSlot.slot_id)
            )
            if result.first() is not None:
                created += 1
    return created
```

`next_business_day_sql()` — same one-line wrapper as before:
`session.execute(text("SELECT scheduling.next_business_day(:d)"), {"d": date_value}).scalar_one()`.
The `:d` bind parameter is always a Python `date` computed by this module,
never user/LLM-supplied text (§10).

`scheduling/router.py` (prefix `/operator/scheduling`, matching
`knowledge/router.py`'s own `/operator/knowledge` prefix convention):

```python
router = APIRouter(prefix="/operator/scheduling", tags=["Operator Scheduling"])

@router.post("/ensure-availability", status_code=200)
def ensure_availability(operator: CurrentOperator, session: DbSession, request: Request) -> dict:
    result = ensure_seed_availability(session)
    record_event(session, "scheduling.availability_seeded", "OPERATOR", actor_id=operator.id, correlation_id=request.state.request_id, payload={"created_d1": result.created_d1, "created_d7": result.created_d7, "already_sufficient": result.already_sufficient})
    session.commit()
    message = "Já tem 4 vagas disponíveis." if result.already_sufficient else f"Criadas {result.created_d1 + result.created_d7} vaga(s): {result.created_d1} em D+1, {result.created_d7} em D+7."
    return {"created_d1": result.created_d1, "created_d7": result.created_d7, "already_sufficient": result.already_sufficient, "message": message}
```

No `conversation_id`, no assignment-gating — this action is not about any
one customer's conversation (unlike `draft()`/`select_evidence()`), only
`CurrentOperator` authentication, matching how `/operator/knowledge/*`
routes are gated.

**Frontend**: one new button in `OperatorPage`, placed outside the
`{selected ? ... : ...}` conditional (so it's usable whether or not a
conversation is selected — this is a global ops action, not
conversation-scoped) — e.g. in the queue sidebar (`aside.card
aria-label="Fila de conversas"`) below the queue list. Label: "Garantir
disponibilidade (D+1/D+7)". On click, `POST`s the endpoint and displays the
returned `message` (a `role="status"`/`aria-live="polite"` line, matching
the existing `typing-indicator` pattern's accessibility treatment, not a
blocking `alert`). No new page, no new route — one button, one handler,
one status line, in the existing `main.tsx`.

## 5. AA-3/AA-3a — Deterministic keyword extraction, always resolving to a specialty

A small, explicit, testable vocabulary — not fuzzy matching, not an LLM
call. Revised 2026-08-18 (§5 item 10): `specialty_slug` is no longer
`str | None` — it always resolves to a real specialty, defaulting to the
new generalist one:

```python
GENERALIST_SLUG = "oncologia-geral"

SPECIALTY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "mastologia-oncologica": ("mastologia", "mama", "peito"),
    "cirurgia-colorretal": ("colorretal", "intestino", "cólon", "colon", "reto"),
    "segunda-opiniao": ("segunda opinião", "segunda opiniao"),
    GENERALIST_SLUG: ("generalista", "clínico geral", "clinico geral", "não sei qual", "nao sei qual", "triagem", "suspeita"),
}
DATE_KEYWORDS: dict[str, ...] = {"amanhã": ..., "amanha": ..., "semana que vem": ..., "próxima semana": ..., "sábado": ..., "sabado": ..., "domingo": ...}
PERIOD_KEYWORDS = {"manhã": (0, 12), "manha": (0, 12), "tarde": (12, 24)}

def extract_parameters(query_text: str) -> ExtractedParameters:
    text = query_text.lower()
    specialty_slug = GENERALIST_SLUG  # default: "no match" means generalist, not unfiltered
    for slug, keywords in SPECIALTY_KEYWORDS.items():
        if slug != GENERALIST_SLUG and any(kw in text for kw in keywords):
            specialty_slug = slug
            break
    ...  # date_range/period_hours extraction unchanged, still optional
    return ExtractedParameters(specialty_slug=specialty_slug, date_range=..., period_hours=...)
```

Matching is case-insensitive, **word-boundary-aware** substring search —
corrected from plain substring search during Phase 5 live verification
(2026-08-19): a real customer message containing "amanhã" was also
false-positive-matching the "manhã" period keyword, because "amanhã"
literally ends with the characters "manhã" — a naive substring check has
no way to tell the two apart. `_contains_keyword()` uses `\b{keyword}\b`
instead. This applies to every keyword dictionary here (specialty/date/
period), not just the one collision that was caught; the 3 diagnosis-specific
specialties are checked first, in a fixed order, and only if none of them
match does `specialty_slug` stay at its `GENERALIST_SLUG` default — which
is exactly the same outcome as if the customer had explicitly asked for a
generalist, so no separate code path exists for "unmatched" versus
"explicitly generalist" (one less thing to keep in sync, one less thing
to test twice). Date/period remain genuinely optional — an unmatched one
is simply not filtered on. This lives entirely in
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

Query path (resolutions) reuses `ai.dynamic_pattern_resolved`/
`ai.dynamic_pattern_fallback` exactly (no new event type —
`EVENT_CATALOG.md` gains a note, not a new row). `ai.dynamic_pattern_resolved`'s
payload gains two optional fields when the resolver used is
`appointment_availability`: `specialty_slug` (nullable — the matched
specialty, if any) and `slot_count` (how many rows were returned, always
1-4) — both safe, non-identifying, already-public-vocabulary values. The
failure path's `cause` string (already audit-only, never customer-facing,
per D-028) carries the same diagnostic detail the `f"no schedule_slots
matched params={params}"` example shows — parameters, not raw SQL.

The seed action (AA-9) gets its own **new** event,
`scheduling.availability_seeded` (it is not a resolution — no
`ai_generation_id` exists for it) — payload `{operator_id, created_d1,
created_d7, already_sufficient}`. `EVENT_CATALOG.md` gains this one new row.

## 8. Q&A content: evaluate and keep only what's necessary (`spec.md` §5 item 3)

Final entry list is authored in `tasks.md`/a data-seed task, but the shape
is decided here: keep a small set (roughly 4-6, plus the 2 new ones below)
of `agenda`-category entries with `dynamic_resolver =
'appointment_availability'`, `dynamic_data_required = true`, covering the
phrasings retrieval actually needs to match a real customer message to
*some* entry. The 5 entries describing booking/hold/identity/payment-
confirmation content that this feature does not implement (`spec.md` §6)
are **soft-deactivated** (`is_active = false`) via the existing V2-8 CRUD
mechanism — never hard-deleted — done through a one-off authenticated
operator-CRUD script (`scripts/`, matching `seed_evaluation_cases.py`'s
precedent) rather than editing `db/init/004_qa.sql` in place.

### New coverage gap identified by the human (2026-08-18): "primeira consulta," generalist (AA-3a)

The 3 originally-seeded specialties (`mastologia-oncologica`,
`cirurgia-colorretal`, `segunda-opiniao`) all assume the customer already
knows which one they need. Nothing covered someone who suspects they may
have cancer but does not yet know which specialty applies — a real, common
intake scenario. **Corrected 2026-08-18 (§5 item 10):** the fix is not
"search unfiltered across all specialties" — it's a real seeded
**generalist** specialty (`GENERALIST_SLUG = "oncologia-geral"`, §5, §3a),
so the customer is matched with an actual non-specialized professional for
an initial/triage consultation, the same way any other specialty match
works. Two new `agenda` entries, both `dynamic_resolver =
'appointment_availability'`, `dynamic_data_required = true`, `category =
'agenda'`, deliberately naming no *diagnosis-specific* specialty keyword
(so `extract_parameters()` falls through to the generalist default — §5):

```
Q: "Suspeito que posso ter câncer, mas ainda não sei qual especialidade
    preciso. Posso marcar uma primeira consulta?"
A: "Sim. Uma primeira consulta com um profissional generalista está
    disponível para investigação inicial, sem diagnóstico definido
    (simulação); a especialidade definitiva é indicada pela equipe depois
    dessa avaliação."

Q: "Quero agendar uma consulta simples para investigar uma suspeita, sem
    saber ainda qual especialista devo procurar."
A: "Sim, é possível. Apresentamos os horários disponíveis com um
    profissional generalista para essa primeira avaliação (simulação); o
    encaminhamento ao especialista correto acontece depois dessa consulta."
```

Both are authored here (not left to implementation time, unlike the rest
of §8's entry list) since the human specified the exact scenario;
`tasks.md` T070 seeds them verbatim, alongside the new `oncologia-geral`
migration (§3, `data-model.md` §6) they depend on.

## 8b. AA-10 — Booking script: the one exception to Article III

This is architecturally unlike everything else in this plan — every prior
section describes a *draft* that still needs an explicit operator send.
This section describes the one mechanism in the whole codebase authorized
to skip that (Constitution Amendment 1.1.0, `DECISIONS.md` D-031), so it
gets extra scrutiny: a dedicated module, a dedicated audit event, and
negative tests proving the exception cannot leak beyond its exact bounds.

### Module

New module `app/customer_care/booking_script/` — deliberately its own
domain, not a submodule of `scheduling/` (it orchestrates conversation
flow and message-sending, only *reading* one piece of `scheduling` data —
the price — same relationship `ai/` already has to `knowledge/`):

- `booking_script/__init__.py`
- `booking_script/parsing.py` — pure functions, no database, no I/O:
  - `extract_cpf(text: str) -> str | None` — a Pydantic model with a
    field validator: strip every non-digit character
    (`re.sub(r"\D", "", text)`), require exactly 11 digits remain (never
    the real CPF check-digit algorithm), format as `###.###.###-##` on
    success, return `None` on validation failure (caught, not raised past
    this function — the caller decides what to do with "invalid").
  - `extract_payment_confirmation(text: str) -> bool | None` —
    case-insensitive, word-boundary regex: `r"\bsim+\b"` for affirmative
    (matches "sim", "Sim", "SIM", "simm", ...), `r"\bn[ãa]o\b"` for
    negative (matches "não", "nao", "Não", ...). Returns `True` only on an
    affirmative-only match; `False`/`None` (negative, no match, or both
    matched — ambiguous, treated as unrecognized) all mean "not yet
    confirmed," handled identically by the caller (re-ask).
  - `detect_booking_intent(text: str) -> bool` — same small
    keyword-substring style as `scheduling/availability.py`'s
    `extract_parameters()` ("quero marcar", "pode agendar", "vou querer
    esse horário", "confirma esse horário", ...) — deliberately a
    separate, smaller vocabulary from `SPECIALTY_KEYWORDS`, not reused
    from it (a different question: "does this customer want to book?" vs.
    "which specialty?").
- `booking_script/service.py` — the state machine and the one exceptional
  send path:
  - `advance_booking_script(session, conversation, customer_message) ->
    None` — the single entry point (§ "Trigger" below).
  - `send_scripted_message(session, conversation, body, request_id) ->
    Message` — constructs an `author_type="OPERATOR"` `Message` directly
    (no `send_operator_message`, no operator-auth dependency — there is no
    operator in this call's context), sets the new
    `Message.autonomous_source = "booking_script"` (`data-model.md` §8),
    and records the new `booking_script.autonomous_message_sent` audit
    event (§ "Audit" below). **This is the only function in the entire
    codebase allowed to create a customer-visible `Message` without an
    authenticated operator dependency in its call chain** — grep-able,
    single-purpose, never imported anywhere except `booking_script/`
    itself.

### State machine

```python
class BookingScriptStep(str, Enum):
    AWAITING_CPF = "AWAITING_CPF"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    # None (Conversation.booking_script_step) means "not started" or "finished"

def advance_booking_script(session: Session, conversation: Conversation, customer_message: Message) -> None:
    step = conversation.booking_script_step
    if step is None:
        if not detect_booking_intent(customer_message.body):
            return
        if not has_recent_resolved_availability(session, conversation):
            return  # never start the script out of context — needs a real slot to have been shown first
        send_scripted_message(session, conversation, "Agendamento realizado")
        send_scripted_message(session, conversation, "Informe seu CPF - é uma simulação, informe qualquer número de 11 dígitos")
        conversation.booking_script_step = BookingScriptStep.AWAITING_CPF
        return

    if step == BookingScriptStep.AWAITING_CPF:
        cpf = extract_cpf(customer_message.body)
        if cpf is None:
            send_scripted_message(session, conversation, "CPF inválido. Informe um número válido de 11 dígitos")
            return  # stays on AWAITING_CPF, no retry limit
        send_scripted_message(session, conversation, f"CPF {cpf} confirmado")
        price = lookup_recent_specialty_price(session, conversation)  # §4/§4b's already-seeded data
        send_scripted_message(session, conversation, f"O valor da consulta é {format_price(price)}")
        send_scripted_message(session, conversation, "O valor foi pago? Responda sim ou não")
        conversation.booking_script_step = BookingScriptStep.AWAITING_PAYMENT
        return

    if step == BookingScriptStep.AWAITING_PAYMENT:
        if extract_payment_confirmation(customer_message.body) is not True:
            send_scripted_message(session, conversation, "O valor foi pago? Responda sim ou não")
            return  # stays on AWAITING_PAYMENT, no retry limit, regardless of "não" vs. unrecognized
        send_scripted_message(session, conversation, "Verificando pagamento")
        send_scripted_message(session, conversation, "Pagamento verificado")
        send_scripted_message(session, conversation, "Agendamento realizado com sucesso. Há algo mais que posso ajudar?")
        conversation.booking_script_step = None  # flow complete, reset — a later "quero marcar" can start fresh
        return
```

`has_recent_resolved_availability()` checks for an `AIGeneration` on this
conversation with `dynamic_pattern_used=true` and a resolver of
`appointment_availability` (i.e., a real successful AA-1..AA-9 answer) —
this is the concrete form of AA-10's own framing, "after a customer
expresses intent to book one of the real slots AA-1..AA-9 showed them."
`lookup_recent_specialty_price()` reads that same generation's
`category_slug` and joins to `ProfessionalSpecialty.fixed_price_cents`
(§3) — no new price source, reuses exactly what AA-1..AA-9 already read.

No artificial delay between "Verificando pagamento" and "Pagamento
verificado" — both send immediately in the same call. Adding a fake wait
would need a background timer/scheduler, which Constitution Article VIII
forbids without a measured need; none exists for a demo simulation.

### Trigger: hooked into the existing customer-message endpoint

`anonymous_access/router.py`'s `send_customer_message()` gains one call,
right before its existing `session.commit()`:

```python
message = Message(conversation_id=conversation.id, author_type="CUSTOMER", body=payload.body)
session.add(message)
session.flush()
conversation.last_message_at = message.created_at
conversation.last_customer_activity_at = message.created_at
record_event(session, "message.customer_received", ...)
advance_booking_script(session, conversation, message)  # new
session.commit()
```

Same transaction, same request — no debounce, no background job (unlike
V2-7's AI-draft trigger, whose debounce exists specifically to batch
LLM-costly generations; this script never calls an LLM, so there is
nothing to batch). Not hooked into the typing-heartbeat endpoint or any
GET/poll path — this script only ever reacts to an actual submitted
customer message, never to typing activity or an operator's page load.

### Audit

One new event type, `booking_script.autonomous_message_sent` — payload
`{conversation_id, message_id, step}` (the step the flow was *on* when
this message was sent — e.g. `"AWAITING_CPF"` for the "CPF inválido"
retry). **Never the customer's raw CPF or their raw payment-question
reply** (Article VI). This event type's entire purpose is to be
grep-able/reportable on its own: any audit review can answer "which
messages in this system were ever sent without an operator's click" with
one query — `SELECT * FROM audit_events WHERE event_type =
'booking_script.autonomous_message_sent'` — and get a complete,
exhaustive answer, by construction (§ "Prohibited shortcuts" repeats this
as a hard boundary).

### What is never persisted

- The raw CPF digits/formatted value — used once, in-memory, to build the
  confirmation message, then discarded. Not on `Conversation`, not in the
  audit payload, not anywhere.
- The raw payment-question reply text or the parsed `True`/`False` —
  same treatment. Only `Conversation.booking_script_step` persists, and
  it is an enum-like marker of *position in the script*, not of any
  customer-supplied value.

## 9. Security

- The query path is reachable only through the exact same authenticated-
  operator, assignment-gated, effective-N2 paths every other draft
  generation already requires (`draft()`/`select_evidence()`) — no new
  authorization surface, and it cannot write regardless (§4).
- The seed endpoint requires `CurrentOperator` — no anonymous or
  customer-token path reaches `/operator/scheduling/ensure-availability`.
  It is deliberately **not** conversation-scoped (no assignment check) —
  it is a shared ops action any authenticated operator may trigger, the
  same trust level as `/operator/knowledge/*`.
- `scheduling.*` read/write access is scoped to exactly the columns
  `scheduling/models.py` maps — no raw/dynamic SQL, no user-supplied table
  or column name reaches a query.
- `scheduling/seeding.py`'s `create_slots_on()` can only `INSERT ...
  ON CONFLICT DO NOTHING` against `schedule_slots`, bounded by `needed`
  (at most 3, ever, since `TARGET_D1=1`/`TARGET_D7=3`) — it cannot update
  an existing row's `status`, cannot delete, and cannot be made to
  over-create by concurrent/repeated calls (the count-then-create check
  plus the unique constraint make it self-limiting; acceptance outcome 9).
- `scheduling/availability.py` (query path) contains zero write statements
  and is not imported by `scheduling/router.py` or `scheduling/seeding.py`
  — the reverse dependency direction is also structurally impossible to
  get backwards by accident.
- No `identity.*`/`billing.*`/`scheduling.appointments` table is imported,
  queried, or referenced anywhere in this feature's code — a negative test
  (acceptance outcome 7) proves this structurally via module-level
  introspection, not just behaviorally.
- **`send_scripted_message()` (§8b) is the only place in the entire
  codebase that constructs a customer-visible `Message` without an
  authenticated-operator dependency anywhere in its call chain.** A
  structural test (acceptance outcome 14) greps every other
  `Message(author_type="OPERATOR", ...)` construction site in the codebase
  and asserts each one is reached only through a function that has
  `CurrentOperator` (or an equivalent already-authenticated context) in
  its parameter list — proving the exception is contained to exactly one
  function, not a pattern that quietly spread.
- `advance_booking_script()` is called from exactly one place
  (`send_customer_message()`) — not from the typing-heartbeat endpoint,
  not from any GET/poll path, not from the operator-authenticated message
  endpoints. It never fires for a conversation with no prior resolved
  `appointment_availability` generation (guards against a stray "quero
  marcar" in an unrelated conversation ever starting the script).
- `booking_script/parsing.py`'s functions take only the customer's own
  message text as input, return only a validated/normalized value or
  `None`/`False` — no raw customer text ever reaches
  `send_scripted_message()`'s `body` parameter (every scripted message is
  a fixed template string, at most interpolated with the *feature's own*
  data — the formatted CPF, the real seeded price — never verbatim
  customer input).

## 10. Testing implementation

Same approach as V1-V3: real PostgreSQL for integration tests, no fake
adapter needed (neither the query path nor the seed action ever calls the
LLM/embedding provider).

- `test_appointment_availability_keywords.py` — pure unit tests for
  `extract_parameters()`: each specialty/date/period keyword; explicit
  generalist keywords; **a query with no known keyword at all resolves
  `specialty_slug == GENERALIST_SLUG`, never `None` and never one of the 3
  diagnosis-specific specialties**; mixed-case.
- `test_appointment_availability_resolver.py` — integration tests against a
  real (test) database, query path only: a specialty-filtered query
  returns only that specialty's slots; **a query with no specialty keyword
  returns only the generalist specialty's slots, never a mix of the other
  3**; a period filter returns only matching-hour slots; zero-match (e.g.
  an unseeded/empty state) raises `DynamicResolutionError`; the rendered
  text contains no raw table/column/internal-error string; **a structural
  test asserts `scheduling.availability` module contains no
  `INSERT`/`UPDATE`/`DELETE` SQLAlchemy construct** (acceptance outcome 4).
- `test_appointment_seeding.py` — integration tests for
  `ensure_seed_availability()`: from zero, creates exactly 1×D+1/3×D+7,
  all within 08:00-18:00; a second immediate call creates zero more and
  reports `already_sufficient=True`; a partial state (e.g. D+1 already
  satisfied, D+7 missing 2) creates exactly the 2 missing D+7 slots and
  zero on D+1; a deactivated professional never receives a generated slot;
  D+1/D+7 correctly skip Sunday/holidays via `next_business_day()`.
- `smoke_v4_appointment_availability.py` (naming matches this feature's own
  identity, not literally "v4" — `spec.md` §5 item 5) — real end-to-end
  HTTP smoke: call the seed endpoint, confirm the reported counts and
  idempotent no-op on a second call; then a real customer message naming a
  specialty/day, generate a draft, confirm `ANSWER` with real (synthetic)
  slot data now available from that seeding, confirm `model ==
  "not-applicable"`, confirm no LLM provider was called, confirm
  `price_lookup`/`payment_simulator`/`insurance_lookup` Q&A entries (if any
  remain seeded) still abstain, confirm anonymous/customer-token
  credentials get `401` from the seed endpoint.
- Regression: existing `smoke_v2_dynamic_pattern.py` and its
  `qa_dynamic_bindings`-based fixture continue to pass unmodified — the
  fallthrough in `dynamic_pattern_result()` must not change generic-binding
  behavior for entries with no `dynamic_resolver` set at all.
- Frontend: `main.test.tsx` gains a test for the new button — click calls
  the endpoint, renders the returned message, works with no conversation
  selected.
- `test_booking_script_parsing.py` — pure unit tests, no database:
  `extract_cpf()` on the human's own two examples ("123456a8910" → `None`,
  "123.456..789.10" → `"123.456.789-10"`), plus a clean 11-digit input, a
  10-digit input, a 12-digit input, an empty string; `extract_payment_confirmation()`
  on the human's own two examples ("Então, não paguei" → `False`/not-`True`,
  "tabom simm paguei" → `True`), plus "sim", "Sim", "SIM", "não", "nao",
  "Não", a message containing neither, and a message containing both
  (must not resolve `True`); `detect_booking_intent()` on several phrasings
  and a negative (an unrelated message).
- `test_booking_script_flow.py` — integration tests against a real (test)
  database, driving `advance_booking_script()` message-by-message: the
  full happy path produces exactly the human's script verbatim; the
  invalid-CPF-then-valid branch; the não-then-sim branch (asserting the
  payment question repeats verbatim, not a modified prompt); a message
  with booking intent but no prior resolved availability generation never
  starts the script; a second "quero marcar" after a completed flow starts
  a fresh one (state correctly reset to `None`); **every sent message has
  `autonomous_source = "booking_script"` and a corresponding
  `booking_script.autonomous_message_sent` audit event with no raw
  CPF/payment-reply text in its payload**; the raw CPF and payment answer
  are never found in any table afterward (`Conversation`, `Message`,
  `AuditEvent` all checked).
- `test_booking_script_containment.py` — the structural negative test from
  §9: every other `Message(author_type="OPERATOR", ...)` construction site
  in the codebase is reached only through an authenticated-operator
  dependency; `send_scripted_message` is imported only within
  `booking_script/`.
- `smoke_v4_booking_script.py` — real end-to-end HTTP smoke: a real
  customer conversation, resolve availability (AA-1..AA-9) for real, send
  a booking-intent message, confirm the script's first two messages
  appear with no operator action; walk the full CPF/payment happy path via
  real customer message posts, confirm the exact final message; confirm
  no `identity.*`/`billing.*`/`scheduling.appointments` row was created at
  any point.

## 11. Performance

Query path: a single indexed `SELECT` with up to 4 joins, no write, no
loop — negligible cost, same order of magnitude as any other retrieval
query. Seed action: bounded by construction to at most 3 inserts per call
(`TARGET_D1 + TARGET_D7 = 4`, minus whatever already exists), each an
`INSERT ... ON CONFLICT DO NOTHING` against a unique-indexed table — a
handful of milliseconds, triggered only by an explicit operator click, never
automatically, never on the customer-facing hot path. No caching, no
background job, no new infrastructure — consistent with every other V1-V3
decision to avoid infrastructure until a measured need exists (Constitution
Article VIII; none exists here at demo scale). The booking script
(`advance_booking_script()`) runs synchronously inside the existing
customer-message request — a handful of string operations and at most 6
`INSERT`s (the human's script's longest single reaction, the CPF-confirmed
step) — negligible, no batching/queueing needed at demo scale.

## 12. Deliverables

- `app/alembic/versions/`: three new, additive, forward-only migrations —
  one creating the `scheduling` schema itself plus the original 3
  specialties' seed data (correction, `data-model.md` §5), one seeding the
  `oncologia-geral` generalist specialty/professionals/
  professional_specialties rows (AA-3a, `data-model.md` §6), one adding
  `Conversation.booking_script_step` and `Message.autonomous_source`
  (AA-10, `data-model.md` §8)
- `app/customer_care/scheduling/__init__.py`, `models.py`,
  `availability.py` (query, read-only), `seeding.py` (AA-9 write path),
  `router.py` (new endpoint)
- `app/customer_care/booking_script/__init__.py`, `parsing.py`,
  `service.py` (AA-10 — the one Article III exception)
- `ai/router.py`: `NAMED_RESOLVERS` dispatch, `dynamic_pattern_result()`
  signature gains `query_text`, both call sites updated
- `anonymous_access/router.py`: `send_customer_message()` gains the one
  call to `advance_booking_script()`
- `bootstrap.py`: register `scheduling_router`
- `frontend/src/main.tsx`: one new button + status line in `OperatorPage`
  (AA-9); no frontend change for AA-10 — its messages render through the
  conversation view exactly like any other `Message` row (a small
  "automático" badge is a nice-to-have, not required — see `tasks.md`)
- `contracts/openapi.yaml` (new file for this package): the one new
  `POST /operator/scheduling/ensure-availability` route — AA-10 adds no
  route of its own
- `docs/architecture/EVENT_CATALOG.md`: note on `ai.dynamic_pattern_resolved`'s
  two new optional payload fields; new rows for
  `scheduling.availability_seeded` and
  `booking_script.autonomous_message_sent` (the latter flagged prominently
  as the one event type marking a non-operator-gated send)
- Q&A content cleanup script (§8) — soft-deactivates the 5 out-of-scope
  `agenda` entries, keeps/edits the in-scope ones
- `app/tests/test_appointment_availability_keywords.py`,
  `test_appointment_availability_resolver.py`,
  `test_appointment_seeding.py`, `smoke_v4_appointment_availability.py`,
  `test_booking_script_parsing.py`, `test_booking_script_flow.py`,
  `test_booking_script_containment.py`, `smoke_v4_booking_script.py`
- `frontend/src/main.test.tsx`: one new test for the button
- `.specify/memory/constitution.md` (already amended, D-031), `spec.md`,
  `data-model.md`, `tasks.md`, `acceptance.md`, `analysis.md`,
  `checklists/{requirements,security,traceability}.md`

## 13. Prohibited shortcuts

- no raw/dynamic SQL built from user or LLM-provided strings anywhere in
  `scheduling/availability.py` or `scheduling/seeding.py` — every query is
  hardcoded, only the *values* (matched specialty id, date range, computed
  D+1/D+7 dates) are parameterized;
- no LLM call, no LLM rewrite, anywhere in the resolved-`ANSWER` path
  (AA-5) — `model` must be `"not-applicable"`, exactly like every other
  dynamic-pattern resolution;
- **the query path (`scheduling/availability.py`) must never write** —
  no `INSERT`/`UPDATE`/`DELETE` statement, no call into `seeding.py`, ever,
  under any circumstance (this is the core distinction the second
  clarification round introduced — do not reintroduce the first draft's
  "ensure on query" shortcut);
- the seed action must never create more than the exact number needed to
  reach `1×D+1`/`3×D+7` — no "round up" or "create extra for headroom"
  shortcut, and never outside 08:00-18:00;
- no write to `scheduling.appointments`/`appointment_events`,
  `identity.*`, or `billing.*` — not even a stub/placeholder row "for
  later," which would violate D-024's dormancy and pre-empt a not-yet-
  authorized future feature;
- no new scheduler/cron/background-job process — the seed action is
  triggered only by an explicit, authenticated operator click;
- no customer-facing endpoint for AA-9 — that button/endpoint stays
  operator-only (AA-10 has no endpoint at all, see below);
- **`send_scripted_message()` (AA-10) must never be called from anywhere
  outside `booking_script/service.py`'s own `advance_booking_script()`** —
  no other module, no other trigger, no future feature may reuse it "since
  it's already there." Constitution Amendment 1.1.0 authorizes exactly one
  script, not a general-purpose autonomous-send utility;
- **no message body passed to `send_scripted_message()` may ever be built
  from customer-supplied text** — only the fixed template strings from
  `spec.md` AA-10's script, at most interpolated with this feature's own
  data (the formatted CPF, the real seeded price). If a future change to
  this script ever needs to echo something the customer said, that is by
  definition no longer "a fixed, human-authored template" and falls
  outside the amendment — stop and get new authorization first, per
  `CLAUDE.md`'s stop conditions;
- **no LLM call anywhere in `booking_script/`** — the entire point of the
  amendment's narrow scope is that these messages are 100% deterministic
  and pre-written; introducing an LLM call here (even just to "phrase it
  more naturally") would combine autonomous send with unreviewed generated
  content, which is categorically outside what was authorized;
- the real Brazilian CPF check-digit algorithm must never be implemented
  here — `extract_cpf()` stays a pure digit-count check, matching the
  human's explicit "é uma simulação" framing; implementing real validation
  would misrepresent this as doing more than it does;
- no `scheduling.appointments`/`schedule_slots.status` write from
  `booking_script/` — "Agendamento realizado" is a scripted sentence, not
  a real state change; a real booking write would silently cross into
  D-026's still-deferred feature through the back door.
