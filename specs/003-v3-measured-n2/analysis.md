# V3 Cross-Artifact Analysis

Spec Kit `analyze`-equivalent review, run 2026-08-18 immediately after
drafting `plan.md`, `tasks.md`, `data-model.md`, `contracts/openapi.yaml`,
`acceptance.md`, and `checklists/*`, before any V3 production code exists.
Per `spec.md` §8: these artifacts must agree before implementation starts.
This review is that agreement check.

## 1. Method

Read `spec.md` (confirmed outcomes V3-1..V3-12, §3-§7) against `plan.md` in
full, then `plan.md` against `tasks.md`, `data-model.md`, and
`contracts/openapi.yaml`, then `acceptance.md`/`checklists/*` against all of
the above. Concretely, not just by re-reading prose:

- extracted every internal `§N`/`§N.M` cross-reference in `plan.md` and
  checked it against the section that number actually is;
- extracted every `T0NN`/`T1NN` task-ID reference in `acceptance.md` and
  `checklists/*` and checked it against `tasks.md`'s real task IDs;
- parsed `contracts/openapi.yaml` with a YAML parser and confirmed its
  relative `$ref`s into V2's `contracts/openapi.yaml` resolve to schemas
  that actually exist there (`GenerateDraftRequest`, `AIGeneration`,
  `OperatorConversationDetail`).

This is exactly the class of drift V2's own `analysis.md` found (mostly
stale `§N` cross-references from editing sections out of order) — cheap to
catch here, expensive to catch during implementation.

## 2. Findings and repairs

All findings below were repaired in place before this document was written;
none are outstanding.

1. **`plan.md` §2 (Module boundaries) cited "§14" for where new
   `audit_events.event_type` values are documented; they are actually in
   §19 ("Audit and traceability").** §14 is "V3-11 — Confirm before
   closing a conversation," unrelated. Root cause: section numbers shifted
   while the document was extended past its first draft length. Fixed to
   §19.
2. **`checklists/traceability.md`'s V3-1 row cited placeholder task IDs
   `T151`/`T160`** for the pre-existing V1/V2 code V3-1's approve/edit tags
   reuse, without checking they corresponded to anything real. The actual
   originating task is V1's `tasks.md` **T141** (`ai.draft_accepted`/
   `ai.draft_edited`). Fixed to cite T141 explicitly.

## 3. Checks that passed without repair

- Every `spec.md` V3-1..V3-12 outcome has a corresponding `plan.md` section
  (§4-§15), `tasks.md` phase, and `acceptance.md` section
  (`checklists/traceability.md` §1 table) — verified as a direct mapping,
  not just asserted.
- Every `spec.md` §5 acceptance outcome (1-13) maps to an `acceptance.md`
  section (`checklists/traceability.md` §2 table), including outcome 9a
  (the transformar-em-Q&A addition) which V2's equivalent numbering scheme
  did not need to accommodate.
- `contracts/openapi.yaml` parses as valid OpenAPI-shaped YAML (validated
  with a YAML parser); its `allOf`/relative-`$ref` overrides into V2's file
  resolve to schemas (`GenerateDraftRequest`, `AIGeneration`,
  `OperatorConversationDetail`) that exist there under the exact names
  used.
- Every `T0NN` task ID referenced from `acceptance.md`/`checklists/*`/
  `plan.md` exists in `tasks.md`, with the single legitimate exception of
  `T141`, which correctly refers to V1's `tasks.md`, not V3's.
- `data-model.md`'s new/changed tables and columns match `plan.md` §3
  one-to-one (`content.categories`, the `qa_entries`/`documents` FK
  additions, `ai_generations`'s six new columns,
  `content.evaluation_cases`, `conversation_satisfaction_responses`).
- The `plan.md` §3.1 correction (folding `content.documents.cancer_type`
  into the same category registry as `content.qa_entries.category`,
  resolved 2026-08-18 after the human's review pushback) is reflected
  consistently in `data-model.md` §1-3, `tasks.md` T010-T012/T017/T022/
  T024, `contracts/openapi.yaml`'s `Category`/`AIGeneration` schemas, and
  `acceptance.md` §A/§D/§E — not left stale in only the section where it
  was first corrected.
- `tasks.md`'s migration phase (Phase 1) precedes every feature phase that
  depends on its schema (category registry, `ai_generations` columns,
  evaluation cases, satisfaction responses), and the Dependency summary
  correctly gates Phase 11 (documented metrics) behind Phase 10
  (satisfaction survey), since V3-4's metrics explicitly include V3-12's
  CSAT numbers — a dependency V2's own phase ordering didn't need to
  express.
- No V3 artifact introduces a scheduler, background worker, or new service
  — the countdown (V3-9) is designed against the existing poll, exactly
  like V2-7's typing indicator (`plan.md` §12/§23), consistent with
  Constitution Article VIII.
- No V3 artifact reintroduces N3/N4 autonomy, the V5 specialist-escalation
  workflow, or appointment-booking/scheduling behavior — `spec.md` §6's
  exclusion list is repeated at the exact points where scope-creep would be
  easiest (V3-1's redefined `escalate` tag, explicitly not a routing
  workflow; `plan.md` §4).
- The V1/V2 safety invariants `spec.md` §3 requires V3 to preserve
  (explicit-send-only, server-side citation/authorization, append-only
  audit, no chain-of-thought persistence) are each re-affirmed at the
  specific point in `plan.md`/`data-model.md` where a V3 change touches
  that invariant's mechanism (e.g. `plan.md` §5's `STALE_GENERATION` check
  for quick-approve, §18 for the introspection-endpoint allowlist
  guarantee), not merely restated once and left unconnected to the new
  design.
- V3-2's key finding (quick-approve needs no backend endpoint because
  `send_operator_message` already computes `ai.draft_accepted`/
  `ai.draft_edited`) is applied consistently everywhere it matters:
  `plan.md` §1 and §5, `tasks.md` Phase 4 (no new-endpoint task, only the
  `STALE_GENERATION` guard and a frontend button), `contracts/openapi.yaml`
  (an override on the existing `/messages` path, not a new path), and
  `acceptance.md` §C.2 (an explicit scenario proving no dedicated endpoint
  exists).

## 4. Residual risks / deferred decisions (not contradictions, but open)

- **Category-slug collision between the administrative and clinical
  taxonomies** (`data-model.md` §8) is asserted unlikely but not
  structurally prevented — `tasks.md` T011 must actually check current
  seed data for a collision before the migration is treated as safe to run
  as-is. Flagged here so it isn't silently skipped during Phase 1.
- **`content.documents.care_phase`** (the ~16-value treatment-phase
  taxonomy) is deliberately excluded from `category` for V3 (resolved
  2026-08-18). This is an acceptable, explicit deferral — not a
  contradiction — but a future V that wants phase-level breakdowns will
  need its own clarification cycle, not an assumption that `category`
  already covers it.
- **V3-5's evaluation-case re-run mechanism** is out of scope for V3 by
  explicit resolution (`spec.md` §7) — `content.evaluation_cases.
  actual_status` stays empty until a human reviewer manually fills it in.
  This means V3-5's acceptance outcome 5 is satisfiable by construction
  (nothing runs automatically), but the dataset's practical value is
  bounded by how much manual review capacity exists; not a design defect,
  a scope choice already made.
- **`checklists/traceability.md`'s "Executable evidence" table** is
  currently placeholders (`(planned, T0NN)`) because no V3 code exists yet
  — mirrors V2's own analysis.md's identical residual risk at the same
  stage. Must be filled in with real file paths during `tasks.md` Phase 13
  (T130-T134), not left as placeholders once tests exist.
- **`ai_generations.category_slug`'s snapshot-at-creation-time behavior**
  (`data-model.md` §8) means a later `cancer_type`/`category` rename does
  not retroactively update historical generations' categories. This is the
  same behavior V1's `message_citations.display_title` already has and is
  intentional, but should be called out to whoever authors V3-4's queries
  so a "why doesn't this old generation show the renamed category" question
  isn't mistaken for a bug during implementation.

## 5. Verdict (pre-implementation)

No unresolved contradiction between `spec.md`, `plan.md`, `tasks.md`,
`data-model.md`, `contracts/openapi.yaml`, `acceptance.md`, and
`checklists/*` as of this review; the two findings in §2 were repaired in
place. `checklists/requirements.md`'s final item ("Cross-artifact analysis
reports no material contradiction") is satisfied by this document. V3 is
ready to move from artifact authoring into `tasks.md` Phase 0 (SDD gates)
and implementation, per `AGENTS.md`'s required SDD flow.

## 6. Phase 13 post-implementation convergence review (2026-08-18)

Re-run after Phases 1-12 implementation, per `tasks.md` T134: checking
every artifact against the real implementation, not only against each
other, matching V2's own Phase 11 convergence method (`specs/002-v2-
commercial-product-experience/analysis.md` §6). `contracts/openapi.yaml`'s
paths were diffed against the live app's actual registered routes
(`curl .../openapi.json`); the highest-risk schema (`AIGeneration`, the
only one V3 extends with new fields) was spot-checked field-by-field
against `generation_dict()`'s real return dict. `data-model.md` §8's
integrity claims were each checked against the actual model/migration
(FK/unique constraints) or the actual query code. `checklists/security.md`'s
10 plan-time items were each re-verified against a specific test or a
targeted code-review pass, not taken on the plan draft's wording.

### Findings and repairs

1. **A real, previously-latent security defect, found while proving
   `v3.spec.ts` passes together with the rest of the `e2e/*.spec.ts` suite
   (not a V3-introduced regression, but a V2-era mechanism V3's own new
   test file was the first thing to actually exercise this way):** the
   V2-2 per-source token-validation rate limiter's client key
   (`request.client.host` in `token_bound_conversation`) is the immediate
   TCP peer — behind this project's one same-origin reverse-proxy hop
   (local docker-compose nginx; Firebase Hosting → Cloud Run in
   production, D-029), that collapses every real customer onto one shared
   value, making the "per-source" lockout global instead of per-customer.
   This is a direct violation of `plan.md` §13.1's own explicit acceptance
   requirement ("does not block legitimate customers") — worse, it is a
   denial-of-service amplification: one attacker's lockout would deny
   every legitimate customer, system-wide, not just themselves. Authorized
   by the human as an immediate approved V2 correction (2026-08-18).
   Fixed via `customer_care/shared/http.py`'s new `client_ip()` (trusts
   `X-Forwarded-For`'s first entry — safe here because the one trusted
   proxy hop always *sets*, never appends/passes through, that header from
   its own view of the connecting peer) plus `frontend/nginx.conf`
   configuring nginx to do exactly that. No `spec.md`/`plan.md` text
   changed — §13.1's own requirement was already correct; only the
   implementation was wrong. Recorded as `DECISIONS.md` D-030.
   Regression-covered by `test_client_ip.py` (4 unit tests); reconfirmed
   via `smoke_v2_token_rate_limit.py` and `v2.spec.ts`'s T128 continuing
   to pass.
2. **`contracts/openapi.yaml`'s `AIGeneration` schema documented
   `marked_incorrect_by_operator_id`/`escalated_by_operator_id` as V3
   additions, but `ai/router.py`'s `generation_dict()` never actually
   returned either field** — only the two `_at` timestamps. Exactly the
   class of drift a dedicated convergence pass exists to catch (same
   pattern as V2's Phase 11 finding #1: a correctly-specified requirement
   silently dropped between specification and implementation, uncaught by
   phase gates because they test what was built, not what the contract
   promised). Not a security gap (the underlying columns were always
   written correctly by `mark_incorrect`/`escalate`; only the read-back
   response was incomplete), but a real API-contract violation any future
   operator-UI feature reading "who marked this incorrect" would have hit.
   Fixed by adding both fields to `generation_dict()`'s return dict;
   re-verified via `smoke_core.py` → `smoke_v3_taxonomy_hcr.py` and the
   full frontend build/lint/type/test gates (additive fields, no consumer
   broke).

`data-model.md` §8's remaining integrity claims had no drift:
`content.categories.slug` uniqueness, `category_slug`'s snapshot-at-
creation-time behavior (confirmed against `derive_category_slug()`'s real
code), and `conversation_satisfaction_responses.conversation_id`'s
`UNIQUE` constraint (confirmed against the actual SQLAlchemy model
column, `unique=True`) all matched exactly. `checklists/security.md`'s
other 9 items had no drift — each is now backed by an explicit
test/code-review reference (the checklist itself records which).

### Verdict

No unresolved contradiction between any V3 artifact and the implementation
as of this review, after repairing the two findings above (one a genuine
security correction to a V2 mechanism, one a contract-completeness gap).
`spec.md` §5's 13 acceptance outcomes are covered by `acceptance.md`'s
executable scenarios (sections A-P); see `acceptance.md`'s Execution
record for the pass/fail evidence, and `checklists/traceability.md` for
the outcome → task → acceptance-area → test-file mapping. V3 is DONE.
