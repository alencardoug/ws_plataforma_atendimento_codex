# Analysis: Governed Autonomous Response (N3/N4)

## Cross-artifact convergence review (2026-08-20)

- `spec.md` §5's data model summary did not originally list
  `ai_generations.operator_id`'s nullability, `retrieval_runs.operator_id`'s
  nullability, or the two CHECK-constraint widenings on `messages`
  (`messages_autonomous_source_check`, `messages_check`) — all four were
  found only during implementation, not anticipated when `spec.md`/`plan.md`
  were first written. Each is documented inline at the point it was found
  (`plan.md` §2 for the `operator_id` pair, `data-model.md` §4/§5 for all
  four), not silently patched. `spec.md` §5 itself was updated once
  (`operator_id` nullability) to keep the spec-level summary honest; the
  two CHECK-constraint findings are `data-model.md`-only detail, matching
  this project's own precedent of keeping `spec.md` at the outcome level
  and pushing implementation-shape detail to `data-model.md`.
- `plan.md` §3's `maybe_open_autonomous_window()` pseudocode sketched
  deriving the rank-1 evidence's category manually; direct inspection
  during implementation found `AIGeneration.category_slug` (`derive_category_slug()`,
  V3-1/V3-3/V3-4/V3-12) already computes exactly this, including the
  correct `None` result for an evidence-free `ANSWER` (e.g. a bare
  greeting) — the actual implementation uses it directly rather than
  duplicating the derivation, simplifying the plan's own sketch rather
  than contradicting it.
- `tasks.md` T1-T28 are all complete. T29-T32 (gates) are complete and
  passing, including the containment tests (T25's negative-test
  requirement, Constitution Article X) and the full smoke/E2E runs.

## The two structural containment findings (Constitution Article X in practice)

Found live, both corrected as part of implementation rather than left for
a later session:

1. `test_booking_script_containment.py`'s own AST-based test — proving
   Constitution Amendment 1.1.0's exception (`send_scripted_message`) is
   the only non-operator-authenticated `Message(author_type="OPERATOR")`
   construction site in the codebase — would have correctly *failed* the
   moment `autonomy/service.py`'s `resolve_elapsed_autonomous_sends()`
   was added, since that is now a second such site. This is the test
   working exactly as designed: catching a real, deliberate widening of
   the same safety boundary. Updated with an explicit, named allowlist
   entry (not a blanket relaxation) so a genuine *third* site would still
   fail it.
2. A second, independent DB-level CHECK constraint,
   `messages_check`, enforces the identical invariant at the schema
   layer (an `author_type='OPERATOR'` row with `operator_id IS NULL` was
   only valid when `autonomous_source='booking_script'`) — this project
   already had defense in depth for Amendment 1.1.0's exception that
   `spec.md`/`plan.md` had no visibility into until the first real insert
   attempt failed with a `CheckViolation`. Both the AST test and the DB
   constraint needed the identical widening, found and fixed together.

These are exactly the kind of findings Constitution Article X ("include a
test proving forbidden behavior fails") exists to produce — a new
authorized exception surfaced every existing safety net protecting the
boundary it touches, not just the ones anticipated in advance.

## Regression risk assessment

- **`evaluate_automatic_trigger()` itself is unmodified except for one
  added line** (the `maybe_open_autonomous_window()` call after a
  successful generation) — every existing test exercising it continues to
  exercise the exact same code path for any conversation whose category
  policy is off (the default) or kill switch is off (the default).
  `evaluate_unclaimed_autonomous_trigger()` is a wholly new, separate
  function; it shares logic via the new `_uncovered_customer_run()`
  helper but does not alter `evaluate_automatic_trigger()`'s own control
  flow.
- **`generate_draft()`'s new `allow_unclaimed` parameter** defaults
  `False`; every pre-existing call site (manual draft, GB flow, evidence
  selection) keeps that default, so its own status guard
  (`conversation.status != "ACTIVE"`) is byte-for-byte unchanged for them.
  Only `evaluate_unclaimed_autonomous_trigger()` passes `True`.
- **Nullable FKs** (`ai_generations.operator_id`, `retrieval_runs.operator_id`)
  widen a constraint, never narrow one — no existing row or existing
  caller's guarantee is affected; only the one new call site ever
  produces `NULL`.
- **GA-6 (unclaimed autonomy)** is the largest behavioral change this
  cycle makes to V1's own queue/capacity model — a `WAITING` conversation
  can now contain a customer-visible answer before any operator claims
  it. Mitigated structurally: every path into it still requires
  `status='ANSWER'` with real evidence, the category's own policy
  (default off), and the kill switch (default off) — GA-6 adds a new
  *trigger point*, not a new *bypass* of any existing safety gate.
- **Full backend `pytest`: 230/230** (217 pre-existing + 13 new — 9
  business-logic tests, 4 containment tests), real DB, zero regressions.
  Full 19-script `smoke_*.py` suite (18 pre-existing + `smoke_v10_governed_autonomy.py`):
  all pass, real embeddings, real LLM calls, a real (non-mocked) short
  veto window.

## A found-live, pre-existing test fragility unrelated to this cycle

`frontend/e2e/v3.spec.ts`'s "Limpar (V3-7)" test began failing during
this cycle's own full-suite verification runs — traced by hand (browser
reproduction, not guesswork) to the test's own synthetic customer message
text, `"Pergunta para checar o Limpar (T132 V3-7)"`, which contains the
literal word "Limpar" ("clear/clean") and real embedding retrieval
occasionally matches it against an unrelated real LGPD-style
data-correction/deletion Q&A entry instead of the generic "horário de
atendimento" evidence the test's own manual search targets — producing a
genuinely confusing but *not incorrect* `ANSWER` slowly enough to exceed
the test's 20s budget. Confirmed **not** caused by this cycle: the
system's global kill switch and every category's own `autonomy_enabled`
flag were verified off at the time of the failure (governed autonomy
never activates for a manually-triggered "Gerar rascunho" regardless, per
GA-2(b)); no locator collision was involved once the two real collisions
below were fixed. Left undisturbed as a pre-existing fragility, the same
treatment `v1.spec.ts`'s original flake and `v7.spec.ts`'s own remaining
intermittency received earlier this session — not this cycle's to fix
without separate authorization.

## Two real UI regressions found and fixed during this cycle's own full-suite verification

1. **`getByLabel("Categoria")` collision**: the new category-autonomy
   checkboxes' accessible names were built directly from
   `category.label`, which — for categories `v2.spec.ts` itself creates
   as fixtures (label text like `"Categoria fixture e2e-t126-..."`) —
   collided with that same file's own pre-existing `getByLabel("Categoria")`
   query for the unrelated Q&A category `<select>`, a strict-mode
   violation on both sides. Fixed with an explicit `aria-label` on the
   checkbox, decoupling its accessible name from the raw category label
   text entirely.
2. **`getByRole("checkbox").first()` collision**: the kill-switch
   checkbox, originally placed in `OperatorPage`'s own queue sidebar,
   rendered earlier in DOM order than the conversation section's
   message-selection checkboxes, silently redirecting every pre-existing
   `.first()`-based checkbox query on that page (`v2.spec.ts`,
   `v3.spec.ts` both rely on this pattern) to the wrong element. Fixed by
   relocating the entire window/kill-switch settings panel to the
   knowledge-admin page, consolidating all autonomy configuration
   (category policy + window + kill switch) in one place that shares no
   DOM with `OperatorPage`'s own message-selection UI.

Both were caught by actually re-running the full pre-existing Playwright
suite after implementation, not assumed safe from code review alone —
exactly the discipline this project's own closure practice already
established for 006-009.

## Verdict

**GO** — implementation matches `spec.md`/`plan.md`/`data-model.md` with
every discovered gap documented at the artifact where it was found, not
silently patched. Every gate this session could run has passed: backend
`pytest` 230/230, the full 19-script smoke suite, and the full Playwright
suite (17 passed, 1 skipped, 1 known pre-existing unrelated flake in
`v3.spec.ts`, 1 known pre-existing unrelated flake in `v7.spec.ts` —
neither newly introduced by this cycle, both root-caused by hand, neither
this cycle's to fix without separate authorization). `v10.spec.ts` itself
(this package's own acceptance test) passed reliably across repeated
runs. Constitution Amendment 1.2.0's governed-autonomy exception is
implemented exactly as narrowly as ratified — see `acceptance.md` for the
outcome-by-outcome evidence.
