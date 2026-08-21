# Data Model: Ungoverned Fictional-Demo Autonomy (N5)

## 1. `customer_service.system_settings` gains two columns

```sql
ALTER TABLE customer_service.system_settings
    ADD COLUMN n5_kill_switch_enabled boolean NOT NULL DEFAULT false,
    ADD COLUMN automatic_trigger_idle_seconds integer NOT NULL DEFAULT 8;
```

`DEFAULT 8` matches the current hardcoded `AUTOMATIC_TRIGGER_IDLE_SECONDS`
exactly (confirmed by direct inspection of
`app/customer_care/ai/router.py`, not assumed) — the migration changes
where this value lives, not its behavior, for every existing deployment
until an operator explicitly changes it.

## 2. `customer_service.pending_autonomous_sends` — two changes

```sql
ALTER TABLE customer_service.pending_autonomous_sends
    ALTER COLUMN category DROP NOT NULL;

ALTER TABLE customer_service.pending_autonomous_sends
    ADD COLUMN mechanism text NOT NULL DEFAULT 'governed_autonomy';
ALTER TABLE customer_service.pending_autonomous_sends
    ADD CONSTRAINT pending_autonomous_sends_mechanism_check
        CHECK (mechanism IN ('governed_autonomy', 'ungoverned_n5'));
ALTER TABLE customer_service.pending_autonomous_sends
    ALTER COLUMN mechanism DROP DEFAULT;
```

`category` becomes nullable: an N5-opened row (`generation.category_slug`
is always `None` by construction, per `plan.md` §3) has no category to
record — `ALTER ... DROP NOT NULL` never breaks an existing row, only
widens what future rows may contain. `mechanism` is added `NOT NULL
DEFAULT 'governed_autonomy'` specifically so every pre-existing row (all
of which really were opened by the 010 governed-autonomy path, before N5
existed) gets a correct, non-fabricated value — then the default is
dropped so every future insert must state its mechanism explicitly (the
code always does, per `plan.md` §4's `_open_pending()` signature).

`Mapped` model changes (`infrastructure/models.py`):

```python
category: Mapped[str | None] = mapped_column(ForeignKey("content.categories.slug"))
mechanism: Mapped[str] = mapped_column(String)
```

## 3. `customer_service.messages.autonomous_source` — widen both CHECK constraints again

Feature 010 found (data-model.md §5 of that package) that this column is
governed by **two independent** CHECK constraints,
`messages_autonomous_source_check` and `messages_check`. Both need the
same widening this cycle adds:

```sql
ALTER TABLE customer_service.messages DROP CONSTRAINT messages_autonomous_source_check;
ALTER TABLE customer_service.messages ADD CONSTRAINT messages_autonomous_source_check
    CHECK (autonomous_source IS NULL OR autonomous_source IN ('booking_script', 'governed_autonomy', 'ungoverned_n5'));

ALTER TABLE customer_service.messages DROP CONSTRAINT messages_check;
ALTER TABLE customer_service.messages ADD CONSTRAINT messages_check CHECK (
    (author_type = 'CUSTOMER' AND operator_id IS NULL)
    OR (author_type = 'OPERATOR' AND operator_id IS NOT NULL)
    OR (author_type = 'OPERATOR' AND operator_id IS NULL AND autonomous_source IN ('booking_script', 'governed_autonomy', 'ungoverned_n5'))
);
```

Both constraints' exact current text was confirmed by reading
`app/alembic/versions/20260820_0010_v10_widen_autonomous_source_check.py`
and `20260820_0011_v10_widen_messages_check.py` directly — this is not a
guess at what they currently say.

## 4. `customer_service.ai_generations` — no schema change

`provider: Mapped[str]` is already a free-text column; N5's ungoverned
generations are distinguished by the value `'ungoverned-n5'` in this
existing column, not a new one. `category_slug` is already nullable
(pre-dates this cycle). `retrieval_run_id` stays `NOT NULL` — N5 reuses
the prior generation's own retrieval run rather than requiring a new one
(`plan.md` §3), so no relaxation is needed here, unlike feature 010's own
`operator_id` nullability finding.

## 5. New audit event types (Article IX)

- `autonomy.n5_kill_switch_toggled` — payload `{before, after}`.
- `autonomy.idle_seconds_changed` — payload `{before_seconds, after_seconds}`.
- `autonomy.n5_ungoverned_reply_generated` — payload
  `{ai_generation_id, prior_generation_id}`, recorded by
  `generate_ungoverned_reply()` itself (actor_type `SYSTEM`, matching
  `resolve_elapsed_autonomous_sends()`'s own precedent).

`resolve_elapsed_autonomous_sends()`'s existing `autonomy.message_sent`
event is unchanged in shape — its payload already includes `category`
(now sometimes `null` for an N5 row, which is accurate, not a bug) and
does not currently include `mechanism`; add it to the payload so an
auditor can distinguish the two mechanisms without joining back to the
now-resolved `pending_autonomous_sends` row.

## 6. No other schema change

No new tables. `content.categories` is untouched — N5 deliberately has no
per-category policy (spec.md N5-2: it applies uniformly whenever its
switch is on). `AIGenerationSource` gains no new rows for an ungoverned
generation (§3's "no schema change" note above) — this is intentional: an
ungoverned generation genuinely has no evidence to attribute, and the
existing `AIGenerationSource` table has no way to represent "attempted but
irrelevant," so it correctly stays empty rather than encoding a false
attribution.
