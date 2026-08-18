-- V3-4: documented, versioned read-only metrics — resolved 2026-08-18 as
-- SQL, not a dashboard screen (spec.md V3-4; a dashboard is deferred to
-- V4's supervisor interface, which needs one regardless). Extends the
-- manual queries teste_humano.md §4/§4.7 already started.
--
-- No write statement exists anywhere in this file — "read-only enforced
-- server-side, not just omitted from the UI" (spec.md acceptance outcome
-- 4) holds by construction: there is no API surface here to disable.
--
-- Every query is parameterizable by date range and, where noted, by
-- category. Run with psql -v flags to scope the window, e.g.:
--   psql "$DATABASE_URL" \
--     -v start_date="'2026-08-01'" -v end_date="'2026-09-01'" \
--     -f docs/metrics/v3_queries.sql
-- Runs as-is with no -v flags too — the \if blocks below default to
-- "all time" only when the caller hasn't already set a value.

\if :{?start_date}
\else
\set start_date '''-infinity'''
\endif
\if :{?end_date}
\else
\set end_date '''infinity'''
\endif

-- =============================================================================
-- 1. Abstention rate — overall and by category (spec.md §5 outcome 1)
-- =============================================================================
-- "sem categoria" (category_slug IS NULL) is an explicit row, never a
-- silently dropped or misattributed one — clinical-grounded, evidence-free
-- (e.g. plain-greeting), and ABSTAIN generations all fall here by design
-- (plan.md §3.1's category-scope note).
SELECT
  COALESCE(category_slug, '(sem categoria)') AS category,
  COUNT(*) AS generation_count,
  COUNT(*) FILTER (WHERE status = 'ABSTAIN') AS abstain_count,
  ROUND(
    COUNT(*) FILTER (WHERE status = 'ABSTAIN')::numeric / NULLIF(COUNT(*), 0),
    4
  ) AS abstention_rate
FROM customer_service.ai_generations
WHERE created_at >= :start_date::timestamptz
  AND created_at < :end_date::timestamptz
GROUP BY ROLLUP (COALESCE(category_slug, '(sem categoria)'))
ORDER BY category NULLS LAST;

-- =============================================================================
-- 2. Human Correction Rate — overall and by category (spec.md §5 outcome 3)
-- =============================================================================
-- Formula (plan.md §6): share of sent generations classified `edit`
-- (ai.draft_edited) out of all sent generations (edit + approve, i.e.
-- ai.draft_edited + ai.draft_accepted, including V3-2 quick-approve sends
-- — quick-approve has no dedicated event type, it produces ai.draft_accepted
-- through the same send_operator_message path every other unmodified send
-- uses). Computed only from durably stored audit facts — reproducible by
-- an independent query, per spec.md acceptance outcome 3.
SELECT
  COALESCE(g.category_slug, '(sem categoria)') AS category,
  COUNT(*) FILTER (WHERE a.event_type = 'ai.draft_accepted') AS approve_count,
  COUNT(*) FILTER (WHERE a.event_type = 'ai.draft_edited') AS edit_count,
  ROUND(
    COUNT(*) FILTER (WHERE a.event_type = 'ai.draft_edited')::numeric
      / NULLIF(COUNT(*) FILTER (WHERE a.event_type IN ('ai.draft_edited', 'ai.draft_accepted')), 0),
    4
  ) AS human_correction_rate
FROM customer_service.audit_events a
JOIN customer_service.ai_generations g
  ON a.payload_json->>'ai_generation_id' = g.id::text
WHERE a.event_type IN ('ai.draft_edited', 'ai.draft_accepted')
  AND a.occurred_at >= :start_date::timestamptz
  AND a.occurred_at < :end_date::timestamptz
GROUP BY ROLLUP (COALESCE(g.category_slug, '(sem categoria)'))
ORDER BY category NULLS LAST;

-- =============================================================================
-- 3. Generation volume by trigger and category (spec.md §5 outcome 1)
-- =============================================================================
-- COALESCE is applied to both grouping expressions themselves (not just in
-- the SELECT list) so a genuine "no category" subtotal within one trigger
-- is never visually conflated with the trigger-level (all categories)
-- subtotal — GROUPING SETS nulls out an excluded dimension's *grouping
-- expression*, so wrapping it in COALESCE first makes that null distinct
-- from a real NULL category_slug's COALESCE result.
SELECT
  COALESCE(trigger, '(todos os gatilhos)') AS trigger,
  COALESCE(category_slug, '(sem categoria)') AS category,
  COUNT(*) AS generation_count
FROM customer_service.ai_generations
WHERE created_at >= :start_date::timestamptz
  AND created_at < :end_date::timestamptz
GROUP BY GROUPING SETS (
  (COALESCE(trigger, '(todos os gatilhos)'), COALESCE(category_slug, '(sem categoria)')),
  (COALESCE(trigger, '(todos os gatilhos)')),
  ()
)
ORDER BY trigger NULLS LAST, category NULLS LAST;

-- =============================================================================
-- 4. Satisfaction (V3-12) — average score and resolved-rate, overall and
--    by category (spec.md §5 outcome 13)
-- =============================================================================
SELECT
  COALESCE(category_slug, '(sem categoria)') AS category,
  COUNT(*) AS response_count,
  ROUND(AVG(score)::numeric, 2) AS average_score,
  ROUND(
    COUNT(*) FILTER (WHERE resolved)::numeric / NULLIF(COUNT(*), 0),
    4
  ) AS resolved_rate
FROM customer_service.conversation_satisfaction_responses
WHERE submitted_at >= :start_date::timestamptz
  AND submitted_at < :end_date::timestamptz
GROUP BY ROLLUP (COALESCE(category_slug, '(sem categoria)'))
ORDER BY category NULLS LAST;

-- =============================================================================
-- Optional: scope any of the above to a single category by adding, e.g.:
--   AND COALESCE(category_slug, '(sem categoria)') = :'category_slug'
-- to that query's WHERE clause (before the GROUP BY), and dropping the
-- ROLLUP/GROUPING SETS if only one row is wanted. Pass
-- -v category_slug=agenda on the command line (quoted as a plain SQL
-- string via :'category_slug', not :category_slug, since this one is a
-- bare value rather than a pre-quoted fragment like start_date/end_date).
-- =============================================================================
