# Analysis: Specialty Citation and Scheduling Breadth

## Cross-artifact convergence review (2026-08-20)

- `spec.md` SS-3's claim ("resolve_price_lookup/resolve_appointment_availability
  need zero code change") was re-verified accurate by direct inspection
  before writing `plan.md`, and confirmed again by the fact this package's
  implementation indeed touches neither function's query logic — only
  `SPECIALTY_KEYWORDS` (a data table) and `extract_parameters()`'s own
  optional fallback path.
- `spec.md` §7's open question about ND-4's `prompt_version` field
  location ("most likely a new nullable column... or a dedicated field on
  RetrievalRun") was resolved in `plan.md`/`data-model.md` as **neither** —
  a new audit event instead (`ai.date_intent_extracted`), matching this
  codebase's own existing precedent for a resolution-adjacent fact that
  isn't the generation's own prompt. Documented explicitly as a
  resolution, not left ambiguous.
- `plan.md` §5.3 identified a real tension `spec.md`'s ND-2 requirement
  did not itself resolve: `extract_parameters()` is documented and relied
  upon (by ~20 existing tests and by `resolve_price_lookup()`'s own
  documented indifference to dates) as pure/deterministic/no-I/O. Adding
  an unconditional LLM fallback would have broken that contract for every
  existing caller. Resolved with a keyword-only `allow_llm_date_fallback`
  parameter, defaulting to `False` — verified correct by actually running
  the full pre-existing keyword test suite unmodified (15/15 pass,
  outcome 7) rather than assuming backward compatibility.
- `plan.md` §4's SV-2 illustrative "(08:00, 08:45, ..., 17:15)" example
  was found, during test-writing, to be arithmetically inconsistent with
  its own stated 45-minute/13-slot/18:00-exclusive rule (45×12=9h, giving
  17:00 as the last start, not 17:15). Documented inline in
  `seeding.py`'s docstring and `plan.md`; implemented per the operative
  numeric rule, treating the illustrative endpoint as spec.md's own typo
  rather than silently picking one interpretation without a record of the
  discrepancy.
- `tasks.md` T1-T20 (SC through ND) are all complete. T21-T22 (gates) are
  complete and passing, including two genuine defects found and fixed by
  actually running what could run in this sandbox (a content keyword bug,
  a test-authoring calendar-fact error — see `acceptance.md`). T23
  (`smoke_v6...py`, full DB-dependent test execution) is written, not
  executed. T24 (this document) is in progress, pending the deferred
  batch run.

## Regression risk assessment

SC is pure content addition (new Q&A rows, new categories) — cannot
regress any existing retrieval path by construction (new content only
ever competes for retrieval slots it previously couldn't have won). SS is
pure reference-data addition plus 4 new keyword-dict entries, checked for
non-collision against every existing entry (test-verified, not just
inspected). SV is a wholly new function/endpoint, touching no existing
seeding logic (`ensure_seed_availability`/`create_slots_on` are untouched
— confirmed by diff). ND is the only piece touching an existing,
widely-depended-on function (`extract_parameters()`), and its
`allow_llm_date_fallback=False` default is the load-bearing safeguard —
verified by an actual full-suite run, not assumed.

The one cross-cutting risk this package introduces — `scheduling/
availability.py` now imports from `ai/providers.py` (a new module
coupling, `scheduling` → `ai`) — was checked for import cycles by direct
import at runtime in this session (`python3 -c "from customer_care.scheduling
import availability; from customer_care.ai import providers"` succeeded),
not just by static reasoning about each module's own import list.

## Verdict

**GO** — implementation matches spec/plan with all identified drift
explicitly resolved and documented (never silently). The credential-backed
batch run (2026-08-20, see `acceptance.md`) confirms all gates pass
against a real DB, real embeddings, and real LLM calls: backend `pytest`
217/217, `smoke_v6_specialty_scheduling_breadth.py` pass, full 18-script
smoke suite 18/18, Playwright 16 passed/1 skipped/1 known-pre-existing V1
failure (confirmed unrelated by `git diff HEAD` on `main.tsx` — the queue
badge race predates this cycle by one commit). Two additional real defects
were found and fixed during the credential-backed run itself (see
`acceptance.md`'s "Credential-backed closure" section) — exactly the kind
of finding this project's practice expects a real run against real data to
catch, not something a written-but-unexecuted test could have surfaced.
This is the last of the four packages authorized 2026-08-20
(D-036/D-037/D-038/D-039) — all four are now DONE; `PROJECT_STATE.md`'s
"Immediate next action" section is rewritten to reflect the cycle's
closure and `ROADMAP.md`'s priority-ordering note (V4/V9, then Telegram)
becomes the live next decision point.
