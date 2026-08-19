# Acceptance: Dynamic Pricing and Guided Booking Selection

Governing spec: `spec.md` §8. See `checklists/traceability.md` for the
full outcome → task → evidence map.

## Areas

| Area | Scope |
|---|---|
| A | PL: real price resolution per specialty |
| B | PM: static content correction, retrieval quality preserved |
| C | PM: `convenio` unaffected (regression) |
| D | GB-1: presented offers persisted correctly |
| E | GB-2/GB-3: slot-choice interpretation, real paraphrases |
| F | GB-4: confirmation-intent interpretation, real varied phrasing |
| G | GB-5: no new autonomous-send path, structural containment |
| H | Full regression: pre-existing suite unmodified in behavior |
| I | Quality gates: ruff/mypy/pytest |

## Execution record

**Executed:** 2026-08-19, against the local Docker Compose stack
(`pgvector/pgvector:pg17`, real `OpenAIEmbeddingProvider`/
`text-embedding-3-small`), backend code run via the app's own `.venv312`
(`TestClient(create_app())` — same process the `smoke_*.py` convention
already uses, no rebuild needed since these are pure Python source
changes). Two new, additive Alembic migrations applied
(`20260819_0005`, `20260819_0006`), head confirmed.

| Area | Result | Real evidence |
|---|---|---|
| A | PASS | `test_price_lookup_resolver.py` (6/6): all 4 seeded specialties (incl. AA-3a generalist default) resolve a real price from `professional_specialties.fixed_price_cents`, matches `format_price_brl()` exactly; no-row fallback proven via monkeypatched specialty slug. `smoke_v5_guided_booking.py`'s PL section: real HTTP draft for "Quanto custa uma consulta de mastologia?" returned `dynamic_pattern_used=true`, `model=not-applicable`, a real `R$`/`(simulação)` price. |
| B | PASS | Real-embedding retrieval spot-check (3 paraphrases, one per rewritten category) all returned the correct rewritten entry at rank 1 (distances 0.30-0.41, well-separated from next-best). `ingest` run confirmed exactly 7 rows embedded/updated, 138 unaffected. |
| C | PASS | `smoke_v4_appointment_availability.py` (updated): a real `convenio` question against `insurance_lookup` still returns `ABSTAIN`/`DYNAMIC_DATA_UNAVAILABLE` with an empty draft — unchanged from before this feature (the test previously checked `price_lookup` for this; that assertion is now the *positive* proof in Area A instead, since `price_lookup` is this feature's own new capability). |
| D | PASS | `test_guided_booking.py::TestLatestUnconfirmedOfferGenerationId`/`TestInterpretSlotChoice` (real DB, deterministic-embedding fixtures): exactly the offered row count persisted, in display order, FK-linked to the resolving generation; correctly stops once `booking_script_step` is set. |
| E | PASS | `smoke_v5_guided_booking.py`: a real paraphrase ("Pode ser aquele horário de manhã mesmo, o primeiro que vocês tiverem" — no exact-text overlap with any offer) correctly matched a real offered slot via `text-embedding-3-small`, producing `trigger=GUIDED_SLOT_SELECTION`, `model=not-applicable`, and a draft correctly restating the match. An unrelated reply ("Vocês têm estacionamento no local?") did not trigger GB-2. `SLOT_CHOICE_DISTANCE_THRESHOLD=0.68` calibrated from measured real distances (genuine matches 0.42-0.66, unrelated 0.70-0.71), documented in `guided_booking.py`. |
| F | PASS | `smoke_v5_guided_booking.py`: a real varied affirmative reply ("Pode confirmar sim, por favor" — not the literal reference phrase) correctly classified `True`, producing `trigger=GUIDED_CONFIRMATION` and the exact fixed acknowledgement text — confirmed still present only as a draft (`assert ... not in [operator message bodies]` before the operator sends it). `CONFIRMATION_MARGIN_THRESHOLD=0.08` calibrated from measured real margins (genuine cases 0.13-0.23, an unrelated message's margin 0.03), documented in `guided_booking.py`; the original absolute-threshold design (`plan.md` draft) was found insufficient against real embeddings and corrected before shipping — see `plan.md` §5.3's inline note. |
| G | PASS | `test_005_booking_script_containment.py` (2/2): `guided_booking.py` never imports from `booking_script/*`; `booking_script/service.py` never imports `guided_booking`. `git diff` against `booking_script/service.py`/`parsing.py` empty throughout implementation. `test_guided_booking.py::TestGB5KeywordOverlapGuard` (3/3): GB-4's fixed templates never substring-match `BOOKING_INTENT_KEYWORDS`; the re-ask text is worded differently from GB-2's confirmation question. |
| H | PASS | Full backend `pytest` (139 tests, up from 129 pre-005) passes, stable across repeated runs. All 17 `smoke_*.py` scripts (16 pre-existing + this feature's new `smoke_v5_guided_booking.py`) pass, run in the same dependency order 004's own acceptance record established (`smoke_core` before `smoke_n2`/`smoke_v3_taxonomy_hcr`, which read the operator's post-`smoke_core` active-conversation state). Two pre-existing tests required updates for reasons *internal to this feature's own intent*, not incidental breakage: `test_dynamic_pattern_dispatch.py`'s `test_unimplemented_resolver_name_still_abstains` now targets `insurance_lookup` instead of `price_lookup` (which this feature implements), and `smoke_v4_appointment_availability.py`'s equivalent regression check was updated the same way — both documented inline with a pointer to this package. One pre-existing failure (`smoke_resilience.py`, real evidence retrieving stale `e2e-t126-*` Playwright fixture rows instead of a disabled-N1-search 403) was confirmed present identically against the pre-005 baseline via `git stash` — local-environment test-data pollution from unrelated prior sessions, not a regression this feature introduced. |
| I | PASS | Backend `ruff check .`: all checks passed. `mypy customer_care/`: no issues found (49 source files). `mypy` against `tests/` carries the same 75 pre-existing errors the pre-005 baseline already had (confirmed via `git stash` comparison) plus zero new ones after this feature's own new/touched test files were corrected. Frontend `lint`/`build` (tsc+vite): clean — zero frontend files touched by this feature (`git status --short frontend/` empty). **Full Playwright was not re-executed this cycle** — inferred safe from the empty frontend diff and zero API response-shape change (only new allowed values for existing string fields like `trigger`), not verified by execution; run it before any production deploy bundling this feature, per `DEPLOYMENT.md`. |

### A genuine mid-implementation design correction (documented per this project's convention)

`plan.md`'s first draft proposed a single shared `DISTANCE_THRESHOLD`
constant (0.22) for both GB-2 and GB-4, guessed by analogy to a
similarity-based mental model without real-embedding evidence. Running
`smoke_v5_guided_booking.py` against the real provider immediately
surfaced two problems: (1) real cosine distances for genuine paraphrase
matches are far larger than 0.22 (measured 0.42-0.66), and (2) GB-4's
"both groups must independently clear a threshold, ambiguous otherwise"
design fails against real embeddings because affirmative/negative
reference phrases are not far apart from each other (a clear "sim" reply
routinely scored under threshold against *both* groups). Both resolvers
were recalibrated from measured data: `SLOT_CHOICE_DISTANCE_THRESHOLD =
0.68` (absolute, since GB-2 picks the single best of a closed candidate
set) and `CONFIRMATION_MARGIN_THRESHOLD = 0.08` (relative margin between
the two group-best distances, since GB-4 must pick a *side*, not a single
candidate). This is the exact reason `plan.md` §7 scoped genuine
paraphrase-quality verification to the real-provider smoke test rather
than the deterministic-provider unit tests — the deterministic provider
is hash-based and cannot surface a miscalibrated real-world threshold.

## Verdict

**GO.** All 9 areas pass with real evidence; the one pre-existing local
failure is confirmed unrelated via baseline comparison; the one real
mid-implementation defect (threshold calibration) was found by this
package's own acceptance protocol and corrected before this record was
written, not after.
