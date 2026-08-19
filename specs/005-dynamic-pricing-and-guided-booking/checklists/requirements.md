# Requirements Checklist — Dynamic Pricing and Guided Booking Selection

- [x] Every FR (PL-1..4, PM-1..4, GB-1..5) has at least one acceptance
  outcome mapped in `spec.md` §8 and at least one real test in
  `traceability.md`.
- [x] No V1-004 invariant is weakened: explicit-operator-send-only
  (GB-5), append-only audit (unchanged event shapes reused), server-side
  citation/authorization enforcement (untouched), manual fallback on
  AI/RAG failure (GB-3, PL-4).
- [x] Data model changes are additive only: one new table, one widened
  CHECK constraint, no edit to any already-applied migration or
  `db/init/*.sql`.
- [x] Content changes (`documents/qa/qa-catalog.jsonl`) go through the
  existing content-hash-driven re-embedding path — no ingestion code
  change required.
- [x] Constitution Amendment 1.1.0's AA-10 boundary is not extended —
  explicit human decision recorded in `spec.md` §9 item 2, verified
  structurally by `test_005_booking_script_containment.py`.
- [x] `insurance_lookup`/`convenio` remains deferred — no code or content
  change touches it (`spec.md` §4 PM-4, §6).
- [x] Every new embedding-similarity threshold is calibrated against real
  provider output, not a guessed constant (`plan.md` §5.2/§5.3, measured
  evidence documented inline).
