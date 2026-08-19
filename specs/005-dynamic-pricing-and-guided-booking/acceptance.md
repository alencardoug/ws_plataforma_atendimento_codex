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

## Correction record (2026-08-19, D-033)

Found through real use immediately after the record above closed: (1) GB-2
could not resolve ordinal replies ("segunda opção", "3") at all — an
embedding-similarity design flaw, not a threshold problem; (2) the
standalone confirmation step felt broken in practice, with no continuous
path to CPF/payment without the customer independently typing a
booking-intent phrase.

| Area | Result | Real evidence |
|---|---|---|
| J — Ordinal slot-choice matching | PASS | `test_guided_booking.py::TestInterpretSlotChoice` (6 parametrized cases: "segunda opção", "a segunda", "2", "primeira", "1", embedded-in-sentence); `smoke_v5_guided_booking.py` real end-to-end with "segunda opção" against real offers. Out-of-range ordinal falls through without raising. |
| K — Direct-to-CPF/payment flow | PASS | `smoke_v5_guided_booking.py`: real HTTP flow — slot chosen (ordinal) → draft states details+price+CPF request in one message (no confirm question) → invalid CPF re-asks → valid CPF confirms + asks payment → negative payment re-asks → affirmative payment completes with AA-10's own exact final wording. Every step confirmed still draft-only (`assert ... not in [operator message bodies]` before send). |
| L — Reused, not reimplemented, parsing | PASS | `test_005_booking_script_containment.py::TestDisclosedParsingReuse` (2/2): exactly one `booking_script` import in `guided_booking.py`, exactly `extract_cpf`/`extract_payment_confirmation` — AST-verified, not text-matched (a docstring mentioning the forbidden function name by name, to explain why it's forbidden, must not false-positive; caught and fixed during this correction's own test-writing). |
| M — Raw CPF/payment never persisted, GB's own redaction | PASS | `test_guided_booking.py::TestRedaction` (3/3) + `smoke_v5_guided_booking.py`'s real DB assertion: `GB_CPF_INPUT_REDACTION`/`GB_PAYMENT_INPUT_REDACTION` present, all 4 raw customer inputs absent from every `Message.body` in the conversation. |
| N — AA-10 itself unaffected | PASS | `smoke_v4_booking_script.py` re-run unmodified: full 10-message autonomous script, zero operator clicks, still passes byte-for-byte identically. `booking_script/service.py`/`parsing.py` structural containment (`test_005_booking_script_containment.py`, `test_booking_script_containment.py`) both green. |
| O — Full regression | PASS | 153 backend tests (was 139 after the original D-032 close); all smoke scripts re-run (including `smoke_v4_appointment_availability.py`, `smoke_core`/`smoke_n2`/`smoke_v3_taxonomy_hcr` dependency-ordered sequences) pass. `smoke_ingestion_changed.py` not runnable from the local venv (hardcodes the Docker container's `/workspace/documents` path) — pre-existing environment constraint, unrelated to this correction, not newly introduced. |

**GO (correction).** Both real defects are fixed with real evidence; AA-10
itself (the constitutionally-scoped exception) is verified unmodified and
unaffected; the one narrow, disclosed coupling this correction introduces
(reusing two pure parsing functions) is verified precisely, not just
assumed absent.

## Correction record (2026-08-19, D-034)

Found through further real use immediately after D-033 closed: (1) a
completed booking never stopped being "the pending offer set" — the next
customer message, even an unrelated clinical question, still matched the
same 4 stale offers; (2) a genuinely uncovered clinical question could
surface a substantively wrong `ANSWER` draft instead of deflecting.

| Area | Result | Real evidence |
|---|---|---|
| P — Post-completion messages fall through | PASS | `test_guided_booking.py::TestLatestUnconfirmedOfferGenerationId` regression case; `smoke_v5_guided_booking.py`: after `GUIDED_BOOKING_COMPLETE`, "Em quanto tempo descubro se eu tenho câncer?" no longer routes to `GUIDED_SLOT_SELECTION`. |
| Q — Clinical-question reranker | PASS | `test_ai_providers.py` (3 new cases, deterministic + real-provider both directions); `smoke_v5_guided_booking.py`: the same post-completion clinical question resolves to `CLINICAL_DEFLECTION_TEXT` via one real LLM reranking call, confirmed never applied inside the GB flow or against `full_parent_draft`'s own match. |

**GO (correction).**

## Correction record (2026-08-19, D-035)

Human-requested after using the D-033 direct-to-CPF/payment flow in
practice: (1) "Voltar"/"Cancelar"/"Alterar horário" (and variations) must
let the customer step back to a fresh slot choice, both at the CPF step
and the payment step; (2) the GB-2/GB-4 message texts needed reformatting
to the exact multi-paragraph shape specified, ending with a "Digite
Voltar para escolher outro horário." hint.

| Area | Result | Real evidence |
|---|---|---|
| R — Step back at the CPF step | PASS | `test_guided_booking.py::TestInterpretCpfReply` (8 parametrized phrases + one end-to-end interpretation-layer test); `smoke_v5_guided_booking.py`: "na verdade quero voltar" during the CPF step returns `trigger=GUIDED_SLOT_RESELECTION` with the same original offers re-listed, never "CPF inválido"; a fresh ordinal choice afterward resolves normally. |
| S — Step back at the payment step | PASS | `test_guided_booking.py::TestInterpretPaymentReply` (8 parametrized phrases); `smoke_v5_guided_booking.py`: "quero voltar" after CPF confirmation also returns `trigger=GUIDED_SLOT_RESELECTION`; required fixing a real bug found via this same smoke run — the original "was this trigger *ever* seen" exclusion permanently blocked re-matching once `GUIDED_CPF_CONFIRMED` had occurred, which is *always* true by the time the payment step is reached; revised to "is the *latest* GB-flow trigger terminal" (`test_guided_booking.py::TestLatestUnconfirmedOfferGenerationId`, 5 cases covering every non-terminal trigger plus the CPF-then-voltar sequence). |
| T — Message reformatting | PASS | `smoke_v5_guided_booking.py`: exact-text assertions on the GB-2 slot-choice message (starts with `"Entendi que você escolheu:\n\n"`, ends with the Voltar hint) and both GB-4 messages (CPF-confirmed, payment re-ask). |
| U — Full regression | PASS | 178 backend tests (was 168 before this correction); `ruff`/`mypy` clean; full `smoke_v5_guided_booking.py` re-run passes end-to-end including both step-back points. |

**GO (correction).** Both requested behaviors are implemented with real
evidence; the payment-step exclusion bug found mid-implementation (not
present in the original ask) was fixed and locked in with a dedicated
regression test before this record was written, matching this package's
own acceptance protocol.
