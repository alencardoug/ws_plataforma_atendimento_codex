# Requirement Traceability Checklist — Dynamic Pricing and Guided Booking Selection

Maps `spec.md`'s FRs (§3-§5) and acceptance outcomes (§8) to `tasks.md`
tasks and their real evidence. V1-004 traceability is unchanged and still
governs everything this feature leaves untouched (§6).

| FR | Primary tasks | Real evidence |
|---|---|---|
| PL-1 `price_lookup` named resolver | T022 | `NAMED_RESOLVERS["price_lookup"]`, `ai/router.py` |
| PL-2 Deterministic specialty-only extraction | T020 | reuses `extract_parameters()` |
| PL-3 Read-only, single-row, never LLM-composed | T020 | `resolve_price_lookup()`, `scheduling/availability.py` |
| PL-4 Manual fallback on no pricing row | T021 | `test_price_lookup_resolver.py::TestPriceLookupFallback` |
| PM-1 Only 3 `preco` entries stay dynamic | (content) | `documents/qa/qa-catalog.jsonl` QA-025/026/027 unchanged |
| PM-2 3 `preco` entries become static | T010 | QA-028/029/030 `dynamic_data_required=false` |
| PM-3 4 `pagamento` entries become static+accurate | T011 | QA-031/032/033/034 rewritten, no fictional link/timer |
| PM-4 `convenio` untouched | T012 | QA-035/036/037 unchanged, still abstain |
| GB-1 Presented offers persisted | T030-T033 | `appointment_offer_presentations`, `test_guided_booking.py::TestLatestUnconfirmedOfferGenerationId` |
| GB-2 Slot-choice interpretation, draft-only | T040-T042 | `smoke_v5_guided_booking.py` real-paraphrase match |
| GB-3 Below-confidence aborts to normal RAG | T043 | `smoke_v5_guided_booking.py` unrelated-message case |
| GB-4 Confirmation-intent interpretation, draft-only | T050-T053 | `smoke_v5_guided_booking.py` real varied-affirmative case |
| GB-5 No new autonomous-send path | T054, T060, T061 | `test_005_booking_script_containment.py`, `test_guided_booking.py::TestGB5KeywordOverlapGuard` |

## `spec.md` §8 acceptance outcomes

| # | Outcome | Real evidence |
|---|---|---|
| 1 | Specific specialty price → real ANSWER | `test_price_lookup_resolver.py`, `smoke_v5_guided_booking.py` PL section |
| 2 | Price/payment policy question → accurate static ANSWER | `test_guided_booking.py` retrieval spot-checks (`teste_humano.md` manual protocol) |
| 3 | `convenio` still abstains (regression) | `smoke_v4_appointment_availability.py` (updated to check `insurance_lookup` instead of the now-implemented `price_lookup`) |
| 4 | Slot-choice draft correctly restates the offer, never auto-sent | `smoke_v5_guided_booking.py` GB-2 section |
| 5 | Non-matching reply falls to ordinary RAG | `smoke_v5_guided_booking.py` GB-3 section, `test_guided_booking.py::TestInterpretSlotChoice::test_no_pending_offers_returns_none` |
| 6 | Varied affirmative reply → invite-to-proceed draft, still requires send | `smoke_v5_guided_booking.py` GB-4 section |
| 7 | Negative/unclear reply → differently-worded re-ask | `test_guided_booking.py::TestGB5KeywordOverlapGuard::test_reask_is_worded_differently...` |
| 8 | `booking_script/*` untouched, no import coupling | `test_005_booking_script_containment.py` |
| 9 | Full pre-existing regression suite passes unmodified in behavior (2 tests updated for the *expected* price_lookup/dynamic_pattern_result signature changes, documented) | full `pytest`/`smoke_*.py` run, this document's Execution record |
| 10 | No new customer-visible autonomous send | `test_005_booking_script_containment.py`, GB-5 |
