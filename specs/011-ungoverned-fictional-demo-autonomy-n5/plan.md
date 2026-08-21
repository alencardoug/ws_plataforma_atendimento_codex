# Implementation Plan: Ungoverned Fictional-Demo Autonomy (N5)

## 1. Technical summary

N5 hooks into the exact same lazily-evaluated entry point N3/N4 already
uses (`evaluate_automatic_trigger()` / `evaluate_unclaimed_autonomous_trigger()`
→ `maybe_open_autonomous_window()`), so no new scheduler/poll path is
introduced. The one function that composes eligibility,
`maybe_open_autonomous_window()`, gains a second branch: if the existing
N3/N4 conditions (category matched, `ANSWER`, category policy on, N3/N4
kill switch on) don't already open a window, and N5's own independent kill
switch is on, a fresh **ungoverned** completion is generated and its own
`PendingAutonomousSend` row is opened — reusing the identical veto-window/
PAUSE/EDIT/TAKE OVER machinery feature 010 already built.

## 2. `GenerationProvider` gains one new method

`generate(...)` requires evidence and can return `ABSTAIN`; N5 needs
neither. Rather than overload `generate()` with optional evidence and a
"never abstain" flag (which would let a caller quietly weaken the
evidence-gated path by mistake), a **separate, explicitly-named** method is
added to the `Protocol` and both implementations:

```python
def generate_ungoverned(self, history: list[dict[str, str]], system_prompt: str) -> str: ...
```

- `OpenAIGenerationProvider.generate_ungoverned`: a plain chat completion
  (no `response_format=json_object`, no evidence payload, no ABSTAIN
  option) — the model always returns free text. System prompt reuses
  `load_prompt()`'s existing content (keeps the fictional-clinic persona
  consistent with the evidence-gated path) plus one appended instruction:
  always give the customer *some* helpful, in-character response — never
  refuse, never say it lacks information, never break character to
  mention being an AI or a demo (the demo disclosure is the frontend
  banner's job, not the in-conversation persona's).
- `DeterministicTestGenerationProvider.generate_ungoverned`: fixed,
  deterministic text (same precedent as its `generate()`/`rerank_clinical()`
  stand-ins) — real-quality output is smoke-tested against the real
  provider only.

## 3. `generate_ungoverned_reply()` — new function, `ai/router.py`

```python
def generate_ungoverned_reply(session, conversation, prior_generation) -> AIGeneration:
```

- Builds `history` the same way `_uncovered_customer_run()`'s caller
  already does (reuses `prior_generation`'s own selected-message chain —
  no new retrieval, no new customer-message lookup).
- Calls `provider.generate_ungoverned(history, prompt.content)`.
- Persists a **new** `AIGeneration` row (not a mutation of
  `prior_generation`): `status="ANSWER"`, `draft_text=<the ungoverned
  text>`, `provider="ungoverned-n5"`, `trigger="AUTOMATIC"`,
  `prior_generation_id=prior_generation.id` (the existing chain-linking
  field, same one "regenerate" already uses — makes the evidence-gated
  attempt that preceded it inspectable, not discarded),
  `retrieval_run_id=prior_generation.retrieval_run_id` (reuses the
  already-attempted retrieval run for Article V traceability — no second
  retrieval call), `category_slug=None`, `operator_id=prior_generation.operator_id`.
- Records `ai.draft_generated` (actor_type `"SYSTEM"`, matching
  `resolve_elapsed_autonomous_sends()`'s own precedent for a
  non-operator-triggered event) plus a dedicated
  `autonomy.n5_ungoverned_reply_generated` event.
- No evidence sources are attached (`AIGenerationSource` rows) — there is
  none to attach; this is the one legitimate case in the codebase where an
  `ANSWER`-status generation has zero evidence, which is exactly why it
  must never be reachable through the evidence-gated send path (N3/N4
  itself still requires `category_slug` to be set — this generation
  deliberately never gets one).

## 4. `maybe_open_autonomous_window()` — restructured

```python
def maybe_open_autonomous_window(session, generation, conversation) -> None:
    if generation.trigger != "AUTOMATIC":
        return
    settings = session.get(SystemSettings, True)
    if not settings:
        return

    # N3/N4 path (010) — unchanged conditions, unchanged behavior.
    if generation.status == "ANSWER" and generation.category_slug and settings.autonomy_kill_switch_enabled:
        category = session.get(Category, generation.category_slug)
        if category and category.autonomy_enabled:
            _open_pending(session, generation, conversation, category=category.slug,
                           mechanism="governed_autonomy", window_seconds=settings.autonomy_window_seconds)
            return  # a real grounded answer already exists — N5 adds no value here

    # N5 path (011) — only reached when the block above did not open a window.
    if settings.n5_kill_switch_enabled:
        ungoverned = generate_ungoverned_reply(session, conversation, generation)
        _open_pending(session, ungoverned, conversation, category=None,
                      mechanism="ungoverned_n5", window_seconds=settings.autonomy_window_seconds)
```

`_open_pending()` is the existing row-construction logic extracted verbatim
(no behavior change for the N3/N4 case — same fields, same values, just
callable from two sites instead of one).

This satisfies spec.md N5-2 precisely: a category-matched `ANSWER` under
an autonomy-on category with N3/N4's kill switch on is sent via the
existing grounded path and never duplicated; everything else (`ABSTAIN`,
no category, or N3/N4's own gate closed for any reason) falls through to
N5 whenever N5's own switch is on.

## 5. `resolve_elapsed_autonomous_sends()` — one-line change

`autonomous_source="governed_autonomy"` (hardcoded) becomes
`autonomous_source=pending.mechanism` — the column now carries exactly the
value that was decided at window-open time, for both mechanisms. No other
line of this function changes; the double-resolution guard, the
`session.refresh` re-check, and the audit event are all untouched.

## 6. `automatic_trigger_idle_seconds` (N5-5)

`AUTOMATIC_TRIGGER_IDLE_SECONDS` (module constant) is replaced at both its
two call sites (`automatic_draft_status()`, `_uncovered_customer_run()`)
with `get_system_settings(session).automatic_trigger_idle_seconds` — both
functions already take `session` as a parameter, so no signature change is
needed beyond the read. The module constant itself is deleted, not kept as
a fallback default (the column's own `DEFAULT 8` migration value is the
only default that matters, matching how `autonomy_window_seconds`/
`autonomy_kill_switch_enabled` have no Python-level fallback either).

`get_system_settings()` currently lives in `operator_workspace/router.py`;
`ai/router.py` needs it too. Moved to `customer_care/shared/settings_service.py`
(new, tiny module) to avoid a circular import (`operator_workspace/router.py`
already imports from `ai/router.py`), re-exported from
`operator_workspace/router.py` for its existing call sites so nothing else
there changes.

## 7. Settings endpoint and frontend

`SetAutonomySettingsIn` gains `n5_kill_switch_enabled: bool | None` and
`automatic_trigger_idle_seconds: int | None`. `set_autonomy_settings()`
gains two more `if payload.X is not None:` branches, each its own audit
event (`autonomy.n5_kill_switch_toggled`, `autonomy.idle_seconds_changed`)
— same pattern as the two existing branches, not a generalized loop (this
project's own established style keeps each field's audit-event type
explicit and greppable, not templated).

Frontend (Knowledge Management settings panel, next to the existing
window/kill-switch controls): one more number input
("Tempo de espera antes do rascunho automático (s)") and one more checkbox
("Autonomia sem filtro de evidência — N5 (ativa apenas em ambiente de
demonstração)"). Badge for an N5-sent message: distinct tooltip text
("Enviada automaticamente sem evidência — modo N5, demonstração"), same
`.badge` class, no new CSS needed beyond what feature 010 already added.

`PendingAutonomousSendSummary`/`PendingAutonomousSend` TypeScript
interfaces: `category: string | null` (was `string`), `mechanism:
"governed_autonomy" | "ungoverned_n5"` added.

## 8. Test plan

- `test_ungoverned_n5.py` (new, mirrors `test_governed_autonomy.py`'s
  structure/fixture discipline): N5-off-N3/N4-off (nothing sends),
  N5-off-N3/N4-on (010 regression, unchanged), N5-on-category-matched
  (grounded answer wins, `mechanism='governed_autonomy'`),
  N5-on-ABSTAIN (`mechanism='ungoverned_n5'`, no category),
  N5-on-unclaimed (GA-6-style: status stays `WAITING`), PAUSE/EDIT/TAKE
  OVER all resolve an N5-pending row identically to a 010 one,
  `automatic_trigger_idle_seconds` change measurably shifts trigger
  timing, exactly one audit event per settings change.
- `test_011_ungoverned_n5_containment.py` (new, AST-based, same technique
  as `test_010_governed_autonomy_containment.py`): confirms
  `generate_ungoverned_reply()` is the only site that ever constructs an
  `AIGeneration` with `provider="ungoverned-n5"`, and that
  `resolve_elapsed_autonomous_sends()` (unchanged call site count) remains
  the only non-operator-authenticated `Message`-construction site in the
  codebase — N5 does not add a second one, it only adds a second
  *upstream generation path* feeding the same existing send mechanism.
- `smoke_v11_ungoverned_n5.py` (new, real end-to-end HTTP, mirrors
  `smoke_v10_governed_autonomy.py`'s structure): a genuinely uncovered
  question (real embeddings confirm no category match) still gets an
  autonomous reply when N5 is on and N3/N4 is off.
- `frontend/e2e/v11.spec.ts` (new, mirrors `v10.spec.ts`): N5 checkbox
  toggles independently of the N3/N4 checkbox; an N5-sent message shows
  the distinct badge tooltip.
- Re-run the full pre-existing suite (backend pytest, smoke, Playwright)
  exactly as feature 010's own closure did — regressions are found by
  actually running the suite, not assumed absent from code review.

## 9. Risks

- **Ungoverned LLM output quality/tone**: no evidence, no ABSTAIN safety
  valve — the model could produce something off-persona or low-quality.
  Mitigated by scope (N5 only reachable behind its own explicit kill
  switch, in a project whose customer-facing surface already discloses
  it's fictional per Amendment 1.3.0 clause (e)) — not by any content
  filter this cycle adds, which spec.md §4 does not authorize.
- **`prior_generation.retrieval_run_id` reuse**: if the prior generation's
  retrieval genuinely found nothing (the common `ABSTAIN` case), the
  linked `retrieval_run` will show zero/low-relevance hits next to an
  `ANSWER`-status ungoverned generation — an intentional, documented
  asymmetry (spec.md N5-4), not a bug; Article V's traceability
  requirement is about capturing what was attempted, not requiring it to
  have succeeded.
- **`get_system_settings()` relocation**: touches two modules' imports;
  mitigated by keeping the function's own body byte-for-byte identical,
  only moving its location and re-exporting for the existing caller.
