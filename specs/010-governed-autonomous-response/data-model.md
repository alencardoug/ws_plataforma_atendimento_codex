# Data Model: Governed Autonomous Response (N3/N4)

## 1. New column: `content.categories.autonomy_enabled` (GA-1)

```sql
ALTER TABLE content.categories
  ADD COLUMN autonomy_enabled boolean NOT NULL DEFAULT false;
```

One column on the existing `Category` model
(`app/customer_care/infrastructure/models.py`, `content.categories`) —
not a new table. Matches this project's existing precedent of adding a
narrow, targeted column for a new per-row flag (e.g.
`conversations.guided_booking_selected_offer_id`, 007) rather than a
separate policy table for a single boolean.

## 2. New table: `customer_service.system_settings`

Single-row settings table — this project has no existing precedent for
global mutable settings (`get_settings()` reads environment/`.env` only,
which is not operator-editable at runtime), so this is a genuinely new
table, kept as small as this cycle needs and left open to future
settings rather than pre-building a generic key-value store (Constitution
Article XII — model only what this cycle actually needs).

```sql
CREATE TABLE customer_service.system_settings (
    id boolean PRIMARY KEY DEFAULT true,
    CONSTRAINT system_settings_singleton CHECK (id),
    autonomy_window_seconds integer NOT NULL DEFAULT 30,
    autonomy_kill_switch_enabled boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now(),
    updated_by_operator_id uuid REFERENCES customer_service.operator_users(id)
);
INSERT INTO customer_service.system_settings (id) VALUES (true);
```

The `id boolean PRIMARY KEY DEFAULT true` + `CHECK (id)` pattern
guarantees exactly one row can ever exist (a second `INSERT` violates the
primary key), a common singleton-table technique — simpler than a
separate application-level lock for a table this narrow.
`autonomy_window_seconds` default of 30 is a placeholder or the first
operator to touch the settings panel; kill switch defaults `false`
(off) so autonomy is fully opt-in at every level (matches GA-1's own
`autonomy_enabled` default).

## 3. New table: `customer_service.pending_autonomous_sends`

```sql
CREATE TABLE customer_service.pending_autonomous_sends (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    generation_id uuid NOT NULL REFERENCES customer_service.ai_generations(id),
    conversation_id uuid NOT NULL REFERENCES customer_service.conversations(id),
    category text NOT NULL REFERENCES content.categories(slug),
    window_seconds integer NOT NULL,
    opens_at timestamptz NOT NULL DEFAULT now(),
    resolves_at timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'SENT', 'PAUSED', 'EDITED', 'TAKEN_OVER')),
    resolved_at timestamptz,
    resolved_by_operator_id uuid REFERENCES customer_service.operator_users(id),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX pending_autonomous_sends_one_pending_per_generation
    ON customer_service.pending_autonomous_sends (generation_id)
    WHERE status = 'PENDING';
CREATE INDEX pending_autonomous_sends_resolvable
    ON customer_service.pending_autonomous_sends (resolves_at)
    WHERE status = 'PENDING';
```

- `window_seconds` is captured per-row at creation time (a copy of
  `system_settings.autonomy_window_seconds` at that moment) — a later
  change to the global setting never retroactively changes an
  already-open window's own `resolves_at`, matching `plan.md`'s own
  stated intent.
- `resolves_at = opens_at + window_seconds` computed at insert time (not
  a generated column, to keep the insert a plain value the application
  computes once — this project has no existing precedent for generated
  columns and this doesn't need one).
- The partial unique index on `(generation_id) WHERE status='PENDING'`
  is the actual double-resolution guard `plan.md` §7 describes — a
  concurrent second attempt to open a window for the same generation (not
  expected given the trigger functions' own idempotency markers, but
  cheap insurance) fails at the DB level rather than relying solely on
  application logic.
- `resolved_by_operator_id` is `NULL` for `status='SENT'` (nothing
  "resolved" it — the window's own elapse did) and for a race where the
  window elapsed before resolution ran even if an operator's action is
  mid-flight (last-write-wins at the DB level via the `WHERE
  status='PENDING'` guard on every resolving `UPDATE`).

## 4. `customer_service.ai_generations.operator_id` and `customer_service.retrieval_runs.operator_id` become nullable

```sql
ALTER TABLE customer_service.ai_generations
  ALTER COLUMN operator_id DROP NOT NULL;
ALTER TABLE customer_service.retrieval_runs
  ALTER COLUMN operator_id DROP NOT NULL;
```

Per `plan.md` §2 — the single new call site
(`evaluate_unclaimed_autonomous_trigger()`) is the only producer of
`operator_id IS NULL`; every existing call site is unaffected and
continues to always pass a real operator id. `retrieval_runs.operator_id`
was found to need the identical treatment during implementation (not
anticipated when `spec.md`/this plan were first written): `generate_draft()`
calls `rag.service.retrieve()` before constructing the `AIGeneration` row,
and `retrieve()` independently persists a `RetrievalRun` with the same
`operator_id` — both FKs must accept `NULL` for the unclaimed path to
work at all. `retrieve()`'s own `operator_id: UUID` parameter type widens
to `UUID | None` accordingly.

## 5. `customer_service.messages.autonomous_source` gains a new value

```sql
ALTER TABLE customer_service.messages DROP CONSTRAINT messages_autonomous_source_check;
ALTER TABLE customer_service.messages ADD CONSTRAINT messages_autonomous_source_check
    CHECK (autonomous_source IS NULL OR autonomous_source IN ('booking_script', 'governed_autonomy'));
```

Found during implementation, correcting this section's own original
claim of "no schema change": a live `messages_autonomous_source_check`
CHECK constraint already restricted this column to `NULL` or
`'booking_script'` — not visible from the ORM model alone
(`Mapped[str | None]` gives no hint of a DB-level CHECK), only from
inspecting the live schema directly. `'governed_autonomy'` is a second
allowed value from this cycle onward.

A second, independent constraint, `messages_check`, needed the same
widening:

```sql
ALTER TABLE customer_service.messages DROP CONSTRAINT messages_check;
ALTER TABLE customer_service.messages ADD CONSTRAINT messages_check CHECK (
    (author_type = 'CUSTOMER' AND operator_id IS NULL)
    OR (author_type = 'OPERATOR' AND operator_id IS NOT NULL)
    OR (author_type = 'OPERATOR' AND operator_id IS NULL AND autonomous_source IN ('booking_script', 'governed_autonomy'))
);
```

This is a second, DB-level enforcement of the exact same containment
invariant `test_booking_script_containment.py` checks at the Python/AST
level — this project already had defense in depth for Amendment 1.1.0's
own exception (an `author_type='OPERATOR'` message with `operator_id IS
NULL` was previously only valid when `autonomous_source='booking_script'`),
and Amendment 1.2.0's own exception needed the identical widening.

## 6. New audit event types (Article IX)

Reusing the existing `customer_service.audit_events` table (no schema
change) with three new `event_type` values:

- `autonomy.category_policy_changed` — `payload_json`: `{category, before, after}`.
- `autonomy.kill_switch_toggled` — `payload_json`: `{before, after}`.
- `autonomy.window_duration_changed` — `payload_json`: `{before_seconds, after_seconds}`.

All three use `actor_type='OPERATOR'`, `actor_id=<operator.id>` — matches
every other operator-attributed audit event already in the catalog
(`docs/architecture/EVENT_CATALOG.md`, updated by this cycle's tasks).

## 7. No other schema change

`ai_generations.trigger`'s existing CHECK constraint is unchanged — a
governed-autonomous generation's own `trigger` stays `'AUTOMATIC'` (spec.md
§5's own explicit statement); the new lifecycle lives entirely in
`pending_autonomous_sends.status`, not as new trigger values.
