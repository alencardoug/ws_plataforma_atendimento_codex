# V2 Cross-Artifact Analysis

Spec Kit `analyze`-equivalent review, run 2026-08-14 immediately after
drafting `plan.md`, `tasks.md`, `data-model.md`, `contracts/openapi.yaml`,
and `acceptance.md`, before any V2 production code exists. Per `spec.md` §8:
"No V2 production code should be added before those artifacts agree." This
review is that agreement check.

## 1. Method

Read `spec.md` (confirmed outcomes V2-1..V2-8, §3-§7) against `plan.md` in
full, then `plan.md` against `tasks.md`, `data-model.md`, and
`contracts/openapi.yaml`, then validated the OpenAPI document parses and has
no dangling `$ref`s. Checked every internal `§N`/`§N.M` cross-reference in
`plan.md` and `data-model.md` against the actual section each document
defines, since these are exactly the kind of drift that accumulates silently
across a long single-session authoring pass and is cheap to catch here versus
expensive to catch during implementation.

## 2. Findings and repairs

All findings below were repaired in place before this document was written;
none are outstanding.

1. **`plan.md` §5 cited §9.4 ("Scope") for dynamic-pattern resolution
   mechanics, which actually live in §9.2 ("Resolution").** A developer
   implementing "Buscar evidências"'s Q&A-with-binding branch would have
   landed on the wrong subsection. Fixed to §9.2.
2. **`plan.md` §3.4 cited §9.4 for "the server-side table allowlist,"
   which is also defined in §9.2, not §9.4.** Same class of error, same
   fix.
3. **`plan.md` §7.2 cited §9.1 ("Authoring") for the typing-heartbeat rate
   limiter, which is actually defined in §13.1 ("Token brute-force
   mitigation").** §9.1 is about dynamic-pattern authoring and has nothing
   to do with rate limiting. Fixed to §13.1.
4. **`plan.md` §11.1 cited "§12.1 of V1's plan" for the customer SPA,
   but V1's `plan.md` §12 uses unnumbered `### Customer`/`### Operator`
   subheadings, not a numbered §12.1.** Fixed to name the subsection instead
   of a nonexistent number.
5. **`data-model.md` used several bare `§N` references that matched
   neither its own six sections nor `plan.md`'s numbering** (e.g. `(§6)`,
   `(§7)`, `(§8)` where no such section existed in either document, or
   pointed at the wrong one). Root cause: the numbers were carried over
   mentally from `plan.md` while writing a differently-numbered document.
   Fixed every instance to either an explicit `plan.md` §N or a correct
   self-reference to `data-model.md`'s own section.
6. **`spec.md` V2-2 described the token as "6–8 characters," while
   `plan.md` §3.1 and `contracts/openapi.yaml`'s `CreateConversationResponse`
   both committed to exactly 8.** Not a contradiction in intent (plan.md
   is where spec.md's range gets resolved to a concrete decision), but left
   as a range in `spec.md` it reads as unresolved. Fixed `spec.md` to state
   8 characters directly, pointing at `plan.md` §3.1 for the exact alphabet.
7. **V1's `ai_generations.triggering_message_id` was `NOT NULL`; V2's
   `MANUAL_EVIDENCE` trigger (from "Buscar evidências") has no single
   triggering customer message.** `contracts/openapi.yaml`'s `AIGeneration`
   schema already correctly made the field nullable and not required, but
   neither `plan.md` §3.3 nor `data-model.md` §3 documented this column
   change — a reader of only the data-model/plan would not have known the
   column's nullability changes from V1. Added the change explicitly to
   both, including what the field holds for `AUTOMATIC`/`MANUAL_DRAFT`
   (most recent selected message, for display) versus `MANUAL_EVIDENCE`
   (null; `message_selections` is empty for this trigger too).
8. **`SelectEvidenceRequest` required a redundant `retrieval_run_id`.**
   `retrieval_hit_id` is already a UUID primary key on `retrieval_hits`, so
   its run is derivable server-side via the existing FK — requiring the
   client to also track and pass the run ID added no safety and only
   friction. Simplified the request schema to drop the field;
   `conversation_id` remains as the only (optional) body property.
9. **`components.parameters.GenerationId` in `contracts/openapi.yaml` became
   orphaned** once `/operator/drafts/{generation_id}/regenerate` was removed
   per the clarified "no separate Regenerar action" decision (`spec.md` §7,
   `plan.md` §7.1) — no remaining path referenced it. Removed.

## 3. Checks that passed without repair

- Every `spec.md` V2-1..V2-8 outcome has a corresponding `plan.md` section,
  `tasks.md` phase, and `acceptance.md` section (`checklists/traceability.md`
  §1 table).
- Every `spec.md` §5 acceptance outcome (1-11) maps to an `acceptance.md`
  section (`checklists/traceability.md` §2 table).
- `contracts/openapi.yaml` parses as valid OpenAPI 3.1 YAML with zero
  dangling `$ref`s (validated with a YAML parser plus a `$ref`-resolution
  script, not just visual inspection).
- The removed `/operator/drafts/{generation_id}/regenerate` route is
  confirmed absent from the parsed document, not just deleted from the
  source text by omission.
- `data-model.md`'s new/changed tables and columns match `plan.md` §3
  one-to-one (`qa_dynamic_bindings`, `message_selections`,
  `conversations`'/`ai_generations`' new columns) after the fixes in §2.
- `tasks.md`'s migration phase (Phase 1) precedes every feature phase that
  depends on its schema, and no phase is marked parallelizable across an
  unresolved schema/contract change, consistent with `spec.md` §8's
  "migrations before dependent code" requirement.
- No V2 artifact introduces a scheduler, WebSocket/SSE channel, or new
  service — the 8-second automatic trigger and typing indicator are both
  designed against the existing polling mechanism (`plan.md` §7.2, §18),
  consistent with V1's precedent and `AGENTS.md`'s "no infrastructure
  without proven need" rule.
- No V2 artifact reintroduces or expands appointment-booking/scheduling
  behavior beyond V2-6's narrowly-scoped correction — `spec.md` §6's
  exclusion list and `plan.md`/`tasks.md` both repeat the boundary
  explicitly at the points where it would be easiest to scope-creep (the
  dynamic-pattern resolver and the knowledge CRUD screen).
- The V1 safety invariants `spec.md` §3 requires V2 to preserve (server-side
  citation/authorization, explicit-send-only, append-only audit, no
  chain-of-thought persistence, AI/RAG-failure fallback) are each
  re-affirmed at the specific point in `plan.md`/`data-model.md` where a V2
  change touches that invariant's mechanism (e.g. `plan.md` §13.2 for
  selection/binding server-side re-validation), not merely restated once
  and left unconnected to the new design.

## 4. Residual risks / deferred decisions (not contradictions, but open)

- **Multi-row dynamic-pattern template syntax** (`plan.md` §9.2) is
  deliberately left unpinned at the spec/plan level; `tasks.md` T073 assigns
  pinning the exact join/repeat syntax to implementation time. This is an
  acceptable deferral (it's a rendering detail, not a behavior or security
  question), but `tasks.md` T073 must actually resolve it before Phase 7 is
  considered done — flagged here so it isn't silently skipped.
- **Rate-limit thresholds** (`plan.md` §13.1: originally a "5 per IP per
  minute" example) were explicitly marked as a starting default, not a final
  decision; `tasks.md` T024 made them configuration, not a hardcoded
  constant, which is what allowed this to be revised without a code change.
  **Resolved 2026-08-14**, same day, after Phase 2 implementation: the
  human found 5 too easily hit during normal use/testing and raised it to
  30, which `plan.md` §13.1 now documents with the entropy-based rationale
  for why this doesn't meaningfully weaken the mitigation.
- **`checklists/traceability.md`'s "Executable evidence" table** is
  currently placeholders (`*(new test module, per T0xx)*`) because no V2
  code exists yet — this must be filled in with real file paths during
  `tasks.md` Phase 11, not left as placeholders once tests exist.

## 5. Verdict (pre-implementation)

No unresolved contradiction between `spec.md`, `plan.md`, `tasks.md`,
`data-model.md`, `contracts/openapi.yaml`, and `acceptance.md` as of this
review. `checklists/requirements.md`'s final item ("Cross-artifact analysis
reports no material contradiction") is satisfied by this document. V2 is
ready to move from artifact authoring into `tasks.md` Phase 0 (SDD gates)
and implementation, per `AGENTS.md`'s required SDD flow.

## 6. Phase 11 post-implementation convergence review (2026-08-17)

Re-run after Phases 1-10 implementation, per `tasks.md` T130: this time
checking the artifacts *against the implementation*, not only against each
other. Method: for `contracts/openapi.yaml`, diffed the contract's
paths+methods against the live app's actual registered FastAPI routes, then
spot-checked the highest-risk response/request schemas field-by-field
against their real dict-builder functions. For `data-model.md`, read every
integrity claim in its §6 against the code path it describes. For
`checklists/security.md`, verified each item against a specific test or a
targeted code-review pass rather than taking the pre-implementation draft's
wording on faith.

### Findings and repairs

1. **`anonymous_access.token_validation_rate_limited` was specified in
   `plan.md` §14 as a required V2 audit event but was never implemented.**
   `token_bound_conversation` called `enforce_not_locked_out` and let its
   `429` propagate without ever recording the event. This is exactly the
   class of drift `tasks.md` T111 exists to catch. Fixed in Phase 10:
   the dependency now records the event (payload-free, `conversation_id`
   deliberately left null) before re-raising. New E2E-adjacent coverage:
   `app/tests/smoke_v2_token_rate_limit.py`.
2. **`data-model.md` §6 documented write-time allowlist validation for
   `qa_dynamic_bindings.source_table` in the V2-8 CRUD screen as a required
   check ("both checks are required"), but `knowledge/router.py` never
   implemented it** — only the resolution-time check in
   `knowledge/dynamic_binding.py` existed. Not a security gap (resolution
   time is and remains the actual enforcement boundary, per the same
   paragraph), but a documented UX guarantee (catch an operator's typo at
   creation time, not three steps later as a generic `ABSTAIN`) that was
   silently missing. Fixed in Phase 11: `knowledge/router.py` gained
   `validate_binding()`, reusing `dynamic_binding.py`'s
   `ALLOWLISTED_TABLES` so the two checks cannot drift apart from each
   other in the future. Covered by two new assertions in
   `smoke_v2_knowledge_crud.py`.

Both findings share a pattern worth naming: they are cases where a
pre-implementation artifact correctly specified a requirement, and the
requirement was simply dropped somewhere between specification and
implementation, with no test catching the gap because no test asserted the
*absence* of the behavior either. Neither was caught by the phase-by-phase
implementation gates (which all passed) because those gates test what was
built, not what the spec said should exist. This is precisely what a
dedicated post-implementation convergence pass (T111, T121, T130) is for,
and both are now closed with regression coverage rather than just a doc
fix.

`contracts/openapi.yaml` and the remaining ten `checklists/security.md`
items had no drift: every registered route matches the contract, every
spot-checked schema matches its response builder exactly, and the other ten
security properties were already true and are now backed by an explicit
test/code-review reference each (see the checklist itself).

### Verdict

No unresolved contradiction between any V2 artifact and the implementation
as of this review, after repairing the two findings above. `spec.md` §5's
11 acceptance outcomes are covered by `acceptance.md`'s executable
scenarios and by `tasks.md` T124-T128's new E2E coverage; see
`acceptance.md`'s Execution record for the pass/fail evidence. V2 is ready
for `tasks.md` T131 (`PROJECT_STATE.md` DONE) once that execution record is
complete.
