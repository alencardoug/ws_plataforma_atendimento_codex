# Tasks: Dynamic Pricing and Guided Booking Selection

Governing plan: `plan.md`. Governing data model: `data-model.md`. Ordered
by dependency; each phase's gate must pass before the next phase starts,
per `AGENTS.md`'s required SDD flow.

## Phase 1 — Migrations

- [x] **T001** Migration: create
  `customer_service.appointment_offer_presentations`
  (`data-model.md` §1/§6.1) — table, FKs, `UNIQUE(ai_generation_id, display_order)`,
  `CHECK(display_order BETWEEN 1 AND 4)`, index.
- [x] **T002** Migration: widen `ai_generations`'s `trigger` CHECK
  constraint to add `'GUIDED_SLOT_SELECTION'`/`'GUIDED_CONFIRMATION'`
  (`data-model.md` §3/§6.2).
- [x] **T003** ORM mapping `AppointmentOfferPresentation`
  (`infrastructure/models.py` or `scheduling/models.py` — co-locate with
  `ScheduleSlot` since it FKs to it, matching how `AIGenerationSource`
  lives with the other `customer_service` models despite FKing to
  `retrieval_hits`; final placement decided at implementation time by
  which existing import graph is smaller).
- [x] **T004 [Gate]** `alembic upgrade head` clean against a fresh local
  DB; `alembic downgrade -1` twice, clean; `ruff`/`mypy` pass on the new
  migration files and ORM mapping.

## Phase 2 — Content correction (PM)

- [x] **T010 [PM-2]** Rewrite `answer_markdown` for QA-028/029/030
  (`preco`) as always-true static text; set `dynamic_data_required=false`.
- [x] **T011 [PM-3]** Rewrite `answer_markdown` for
  QA-031/032/033/034 (`pagamento`) to describe AA-10's actual sim/não
  payment step, removing the fictional link/timer content; set
  `dynamic_data_required=false`. Preserve QA-033's "never send real card
  data" guidance.
- [x] **T012** Confirm QA-035/036/037 (`convenio`) untouched (PM-4) — a
  negative assertion in the same edit script/migration-adjacent operations
  note, not a code change.
- [x] **T013** Re-run `knowledge/ingest.py` against the local/dev DB;
  confirm content-hash-driven re-embedding fires for exactly the 7 edited
  rows and no others.
- [x] **T014 [Gate]** Manual retrieval check: each of the 7 rewritten
  questions (plus 2-3 paraphrases each) retrieves its own entry at rank 1;
  spot-check no regression on adjacent `agenda`/`preco` entries' own
  retrieval.

## Phase 3 — PL: `price_lookup` resolver

- [x] **T020 [PL-2/PL-3]** `resolve_price_lookup()` in
  `scheduling/availability.py` (`plan.md` §4) — reuses
  `extract_parameters()`, single deterministic `SELECT`, fixed-template
  render via `format_price_brl()`.
- [x] **T021 [PL-4]** `DynamicResolutionError` fallback on no matching
  `professional_specialties` row.
- [x] **T022 [PL-1]** Register `NAMED_RESOLVERS["price_lookup"]` in
  `ai/router.py`.
- [x] **T023** Unit tests: all 4 seeded specialties (including AA-3a
  generalist default via unspecialized query text) resolve correctly;
  no-row fallback path.
- [x] **T024 [Gate]** `pytest`/`ruff`/`mypy` pass; manual smoke via
  `/operator/conversations/{id}/drafts` against a `preco` question in the
  local stack, confirming a real priced `ANSWER` (spec.md §8 outcome 1).

## Phase 4 — GB-1: persisted offers

- [x] **T030** `resolve_appointment_availability()` signature change:
  return `(DynamicResolution, Sequence[_SlotRow])` (`data-model.md` §4).
  Update its one existing caller and any test that constructs/consumes its
  return value.
- [x] **T031** `_offer_description()` — one-line, embedding-friendly
  summary per offer (distinct from `_render_offers`'s multi-line
  customer-facing text).
- [x] **T032** `persist_presented_offers()` in the new
  `scheduling/guided_booking.py` (`plan.md` §5.1) — batches one
  `provider.embed()` call for up to 4 descriptions, inserts
  `AppointmentOfferPresentation` rows.
- [x] **T033** Wire T032 into `dynamic_pattern_result()`'s
  `appointment_availability` branch (`data-model.md` §4's special-casing
  decision) — called only on a successful resolution, never on
  `DynamicResolutionError`.
- [x] **T034 [Gate]** Integration test: a resolved `appointment_availability`
  generation produces exactly `min(4, matching_slot_count)` persisted
  offer rows, in the same order as the rendered customer text; verified
  against both a 4-slot and a 1-slot fixture.

## Phase 5 — GB-2/GB-3: slot-choice interpretation

- [x] **T040** `latest_unconfirmed_offer_generation_id()`
  (`data-model.md` §2 query) in `scheduling/guided_booking.py`, respecting
  the "stop once `booking_script_step` is non-`None`" rule.
- [x] **T041** `interpret_slot_choice()` (`plan.md` §5.2) — pgvector
  `cosine_distance` query scoped to the latest unconfirmed generation,
  `DISTANCE_THRESHOLD` constant with a code comment pointing at T044's
  tuning evidence.
- [x] **T042** New branch in `generate_draft()` (`ai/router.py`), tried
  before `full_parent_draft`/`dynamic_pattern_result`: on a match, build
  the fixed `GenerationResult` (spec.md GB-2), `trigger='GUIDED_SLOT_SELECTION'`,
  `dynamic_pattern_used=true`, empty `used_hit_ids`.
- [x] **T043 [GB-3]** Confirm a `None` return from `interpret_slot_choice`
  falls through unchanged to the existing branch order (by construction,
  not a separate code path — verified by a test that asserts ordinary RAG
  composition still occurs for a non-matching reply).
- [x] **T044** Threshold tuning: build the acceptance corpus (spec.md §8
  outcome 4 — at least 2 phrasings per offer, across at least 2 distinct
  offer sets) against `DeterministicTestEmbeddingProvider`; pick
  `DISTANCE_THRESHOLD` from measured separation, document the evidence in
  the code comment (not a guess).
- [x] **T045 [Gate]** Unit + integration tests pass; manual smoke: present
  4 offers, reply with a natural paraphrase of one, confirm the resulting
  draft correctly restates it and is not auto-sent.

## Phase 6 — GB-4/GB-5: confirmation-intent interpretation

- [x] **T050** Reference-phrase embedding cache (`plan.md` §5.3) —
  computed once per configured embedding model, not per call.
- [x] **T051** `interpret_confirmation_intent()` — classifies
  affirmative/negative/unclear against the cached reference vectors.
- [x] **T052** "Was the preceding sent message a GB-2 output" check
  (`data-model.md` §3) feeding the new `generate_draft()` branch for
  `trigger='GUIDED_CONFIRMATION'`.
- [x] **T053** Fixed acknowledgement template (affirmative) and fixed
  re-ask template (negative/unclear, worded differently from the original
  question) — both plain Python string constants, no LLM.
- [x] **T054 [GB-5]** Unit test asserting the acknowledgement template
  string does not substring-match any entry in
  `booking_script/parsing.py::BOOKING_INTENT_KEYWORDS` (spec.md §5.4/§9
  item 2 — a regression guard against the two lists silently overlapping
  in a future edit).
- [x] **T055 [Gate]** Unit + integration tests pass (spec.md §8 outcomes
  6/7); manual smoke: after a sent GB-2 message, reply affirmatively in 3+
  phrasings and negatively in 1-2, confirm correct draft classification
  each time, still requiring explicit operator send.

## Phase 7 — Containment and regression

- [x] **T060 [Gate]** Structural containment test: literal byte-diff of
  `booking_script/service.py` and `booking_script/parsing.py` against
  their pre-feature `git` blobs — asserts equality (spec.md §8 outcome 8,
  mirroring 004's own AA-10 containment check).
- [x] **T061 [Gate]** Static import-graph check: no module under
  `scheduling/guided_booking.py`'s own import chain imports from
  `booking_script/*`, and `booking_script/*` imports nothing new.
- [x] **T062 [Gate]** Full pre-existing `smoke_*` suite (16 scripts)
  passes unmodified against a rebuilt local stack.
- [x] **T063 [Gate, partial]** Zero frontend files changed by this
  feature (`git status --short frontend/` empty) — no new UI surface, no
  API response-shape change (only new allowed values for existing
  string-typed fields like `trigger`). Frontend lint/typecheck/build
  reconfirmed green. Full `v1/v2/v3/v4` Playwright suite was **not**
  re-executed this cycle (time/cost tradeoff for a zero-frontend-diff
  change) — this is inferred-safe from the empty diff, not verified by
  execution; run it before a production deploy that bundles this feature,
  per `DEPLOYMENT.md`'s own standing practice.
- [x] **T064 [Gate]** Backend `ruff`/`mypy`/`pytest` full suite: clean.
  Frontend lint/typecheck/build: clean (no operator-facing copy needed
  updating — this feature adds no new required UI control by design,
  only new generation content shown through the existing draft panel).

## Phase 8 — Acceptance and convergence

- [x] **T070** `checklists/requirements.md`,
  `checklists/traceability.md` mapping every PL/PM/GB outcome
  (spec.md §8) to its test(s), same pattern as 004's checklists.
- [x] **T071** `acceptance.md` — Execution record covering all 10
  spec.md §8 outcomes against a rebuilt Compose stack with real
  embeddings.
- [x] **T072** `analysis.md` — final cross-artifact convergence review:
  confirm spec/plan/data-model/tasks agree, confirm §6's "not authorized"
  list was fully respected (grep-able evidence per item, not just a
  restated claim), record verdict.
- [x] **T073** Update `PROJECT_STATE.md`/`ROADMAP.md`/`SDD_MANIFEST.md`/
  `AGENTS.md`/`CLAUDE.md` lifecycle sections marking 005 DONE, same as
  004's own closure updated those files.
- [x] **T074** Update `teste_humano.md` with a new section covering PL/GB
  manual test steps, same pattern as the V3/004 update.

## Dependency summary

```
Phase 1 (migrations)
  -> Phase 2 (content, independent of 3-6, can run in parallel with them)
  -> Phase 3 (PL, independent of 4-6)
  -> Phase 4 (GB-1, needed by 5 and 6)
     -> Phase 5 (GB-2/3)
        -> Phase 6 (GB-4/5, needs Phase 5's generated confirmation-question generations to exist)
  -> Phase 7 (needs 1-6 complete)
  -> Phase 8 (needs 7's gates green)
```
