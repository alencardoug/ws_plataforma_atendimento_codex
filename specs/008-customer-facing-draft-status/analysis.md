# Analysis: Customer-Facing Draft Status

## Cross-artifact convergence review (2026-08-20)

- `spec.md` CS-1's code sketch was implemented verbatim in
  `anonymous_access/router.py`'s `customer_draft_status()`. One design
  question not fully settled by spec.md's sketch alone — whether to call
  `evaluate_automatic_trigger()` before `automatic_draft_status()`,
  matching the operator router's own pattern — was resolved during
  `plan.md` §2 by reading both functions' docstrings directly: the
  "callers must call this after evaluate_automatic_trigger" contract is
  about same-request ORM freshness after a *mutation*, and
  `read_conversation()` performs none, so omitting the call (matching
  spec.md's literal sketch) is correct, not an oversight. No drift.
- `plan.md` §2's decision to compose the field only into `read_conversation()`
  (not `create_conversation()`/`close_conversation()`) was implemented as
  planned — verified by reading the final diff.
- `tasks.md` T1-T3 (backend), T5-T6 (frontend) are complete. T4 (backend
  tests) is complete with 3 new unit tests, deliberately not duplicating
  `automatic_draft_status()`'s own already-existing eligibility test suite
  (outcome 4 is inherited, not re-tested). T7 (frontend tests) is complete,
  2 new Vitest tests. T8 (`v8.spec.ts`) is written, not executed. T9-T10
  (gates) are complete and passing. T11 (empty alembic diff; no
  `contracts/openapi.yaml` snapshot exists to diff — confirmed this
  package's own predecessor, `005-dynamic-pricing-and-guided-booking`,
  already left that directory empty, so this is consistent with
  established practice, not a new gap this package introduces) is
  confirmed. T12 (this document) is in progress, pending the deferred
  credential-backed run (T8/T9 of `tasks.md`'s gate phase).

## Regression risk assessment

Backend change is two additive lines in `anonymous_access/router.py`
(one new function, one dict-spread in `read_conversation()`) plus one new
optional-with-default Pydantic field. No existing endpoint's behavior
changes for any request that doesn't read the new field. `automatic_draft_status()`
itself is untouched — reused, not modified — so its own existing test
suite continues to be the source of truth for eligibility-logic
correctness; this package adds no new eligibility branch to that function.

Frontend change is additive (`preparing_response` optional field, one new
conditionally-rendered `<p>`) — no existing element removed or restructured.

## Verdict

**GO** — implementation matches spec/plan with no drift found. The
credential-backed batch run (2026-08-20, see `acceptance.md`) confirms all
gates pass, including `v8.spec.ts` against a real Compose stack with real
`gpt-5-mini` latency — which also surfaced and fixed two real test-timing
issues (see `acceptance.md`'s closure section). This package is DONE
(D-038) in `PROJECT_STATE.md`/`ROADMAP.md`/`DECISIONS.md`, closing
together with 006/007/009.
