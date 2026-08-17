# Project State

Last updated: 2026-08-17

## Lifecycle and authority

- V1 (`specs/001-v1-assisted-customer-service`) is the completed executable
  baseline. Its original acceptance gates completed on 2026-08-10.
- The human explicitly authorized the **V2 specification cycle** on 2026-08-11.
  Its feature package is `specs/002-v2-commercial-product-experience/`.
- V2 implementation is authorized only in SDD order: it must first complete
  `specify -> clarify -> plan -> tasks -> analyze`, with acceptance coverage,
  before production code is written.
- Dynamic appointment availability is a separate future feature, recorded in
  `ROADMAP.md` and D-026. It is not V2 scope unless explicitly added later.

## V1 baseline

V1 provides anonymous per-tab web conversations, authenticated operator
service, manual queue/capacity, global N1/N2 modes, RAG ingestion/retrieval,
internal AI drafts, explicit operator send, clinical-only customer citation
exposure, and append-only audit events. The V1 hard safety boundaries remain in
force while V2 is designed: no direct AI send, no raw anonymous token at rest
or in URLs/logs, server-side authorization/exposure enforcement, and manual
service when AI/RAG fails.

The 2026-08-10 acceptance record covers PostgreSQL 17/pgvector migrations,
ingestion (57 clinical parents, 570 children, 86 Q&A records), N1/N2 API and
E2E paths, capacity, security negatives, real-provider smoke, and the normal
quality gates. Refer to `specs/001-v1-assisted-customer-service/acceptance.md`
and `analysis.md` §9 for details.

## V1 post-acceptance refinements (committed)

The post-acceptance refinements are committed at `c150e6c` (2026-08-11); the
working tree is clean. An earlier version of this section described them as
uncommitted — that was stale from the moment it was written, since it was
authored in the same commit that landed them. Corrected 2026-08-12 during the
independent closure review below.

They cover:

- preserved multiline rendering for customer and operator messages;
- renamed operator control `Assumir controle`;
- concise customer-ready draft prompt/provider behavior, without an artificial
  completion-token ceiling;
- retrieval-specific behavior: clinical rank-one result yields the complete
  parent document for explicit send; administrative Q&A is interpreted by the
  LLM; no-evidence replies stay general/clarifying and safe;
- manual evidence results now show full content and matching clinical child
  excerpt, but remain evidence-only in V1;
- V1 spec/plan/tasks/OpenAPI/acceptance/analysis updates and deterministic
  provider regression tests supporting those behaviors.

The refinements are recorded in V1 `analysis.md` §§11–15. Frontend lint,
TypeScript, Vitest, and production build passed; Python compilation and the
deterministic generation strategy tests passed; the Compose stack was healthy.

## Independent closure review — 2026-08-12

A read-only closure review (`PROMPT_REVIEW_V1_CLAUDE.md`) verified the above
refinements against the running code, then reran the previously-outstanding
gates with human authorization. Full detail in V1 `analysis.md` §16.

- Backend `ruff`, `mypy`, and `pytest` (13/13): pass.
- Frontend ESLint, TypeScript, Vitest (5/5), production build: pass.
- Credential-backed E2E against a rebuilt Compose stack with a real
  `OPENAI_API_KEY`: `smoke_core`, `smoke_n2`, `smoke_concurrent_capacity`,
  `smoke_ingestion_changed`, and `smoke_real_provider` all pass.
- `smoke_resilience` initially failed to exercise its intended assertion: the
  retrieval-specific refinement above (clinical rank-one → full parent
  document) never calls `configured_generation_provider()` for a triggering
  message whose top evidence is clinical, so the test's provider-failure
  monkeypatch had nothing to intercept. **Fixed 2026-08-13** (`analysis.md`
  §17): the test now also patches `full_parent_draft` to `None` so it reaches
  the provider call deterministically, independent of retrieval ranking.
  Reconfirmed passing, along with the rest of the smoke suite.
- The `dynamic_data_required=true` finding (administrative evidence with
  literal internal identifiers such as `scheduling.available_offers` reaching
  the LLM with only a prompt-level, not code-level, safeguard) is confirmed
  still present. The human decision on its correction is recorded in
  `DECISIONS.md` D-028 and `ROADMAP.md`: the correction is planned, not
  implemented in V1, and its execution enters V2 planning. This is authorized
  future scope, not an open V1 defect, so it does not block V1 closure.

**V1 closure verdict: GO** (`analysis.md` §17, 2026-08-13). Both items open at
the 2026-08-12 CONDITIONAL GO are resolved.

## V2 handoff

Read `CLAUDE_CODE_HANDOFF.md` after this file. The V2 draft specification
captures only decisions already made by the human:

- professional customer/operator experience;
- customer-safe display/copy of the conversation token;
- operator-selected evidence from manual search, with full clinical parent
  expansion for explicit send and Q&A evidence for LLM composition;
- operator-selected customer and operator message context for draft generation;
- durable traceability/audit of selections, expansions, generations, and final
  sends.

It also lists the product decisions that require clarification before a V2 plan
or code can be honestly produced.

## V2 implementation — DONE (2026-08-17)

All 11 phases of `specs/002-v2-commercial-product-experience/tasks.md`
(T000-T131) are complete, committed, and pushed to `main`:

- **Phase 1** — migrations (`conversations`/`ai_generations` new columns,
  `message_selections`, `content.qa_dynamic_bindings`,
  `content.knowledge_dynamic_fixture`).
- **Phase 2 (V2-2)** — 8-character ambiguity-free customer token; IP-keyed
  rate limiter with escalating lockout (default 30 failures/window, raised
  from an initial 5 per human instruction after Phase 2 landed).
- **Phase 3 (V2-4)** — operator-selected conversation-message context
  (`message_selections`), default trailing-customer-run selection,
  "desmarcar conversas".
- **Phase 4 (V2-7 manual)** — "Gerar rascunho" manual trigger; no
  "Regenerar" control (removed the V1 regenerate endpoint entirely).
- **Phase 5 (V2-3)** — "Buscar evidências" single-hit selection,
  deterministic clinical-full-parent / Q&A-LLM branches.
- **Phase 6 (V2-7 automatic)** — typing heartbeat + lazy 8-second
  automatic-draft debounce, no scheduler/WebSocket.
- **Phase 7 (V2-6)** — dynamic-evidence safety correction (D-028): the
  original V1 closure finding is now closed with deterministic,
  allowlist-only `{{variable}}` substitution and a unified audit-only
  fallback for every failure mode.
- **Phase 8 (V2-8)** — knowledge-base CRUD (Q&A + clinical parent/child),
  soft delete, idempotent re-embed, full audit coverage.
- **Phase 9 (V2-1)** — professional design-system redesign of both SPAs;
  the backend-authority audit this phase required found and fixed two
  real UI gaps where a control could be offered that the backend would
  reject.
- **Phase 10** — audit/observability convergence; found and fixed one
  real gap, a specified-but-unimplemented audit event
  (`anonymous_access.token_validation_rate_limited`).
- **Phase 11** — acceptance automation and final convergence; found and
  fixed one more real gap (write-time dynamic-binding allowlist
  validation, documented but unimplemented), added the 5 remaining E2E
  scenarios (T124-T128), and executed the full `acceptance.md` protocol.

`specs/002-v2-commercial-product-experience/acceptance.md`'s Execution
record (2026-08-17) covers all 11 `spec.md` §5 acceptance outcomes, all
passing. `analysis.md` §6 records the Phase 11 convergence review. All V1
safety invariants (explicit-send-only, append-only audit, no
chain-of-thought persistence, server-side citation/authorization
enforcement, manual fallback on AI/RAG failure) were re-verified intact
under every new V2 trigger path.

Three real implementation gaps were found across Phases 9-11 by
dedicated backend-authority/audit/data-model convergence checks rather
than by the phase-by-phase build gates (which all passed throughout) —
each is now closed with regression coverage. This is the expected shape
of a convergence pass: it catches drift between "what the spec/plan says
must exist" and "what got built," which passing build-time tests alone
cannot catch by construction.

## Production deployment — DONE (2026-08-17)

Decided (D-029) to prioritize deploying the completed V1+V2 system ahead of
starting V3. Live at:

- Frontend: `https://customer-care-prod.web.app` (Firebase Hosting, automatic
  TLS, `/api/**` rewrite to Cloud Run).
- Backend: Cloud Run service `customer-care-backend`, region `us-east1`
  (GCP Always Free tier is region-restricted; chosen as the eligible region
  closest to the majority-Brazil target audience), `min-instances=0`.
- Database: Neon serverless Postgres, region `us-east-1` (N. Virginia),
  Postgres 17 (matched to local dev), pgvector enabled, migrated and fully
  ingested (713 records, 656 real embeddings).
- Data remains synthetic/demo only — infrastructure change, not a
  Constitution Article VI change.

Full runbook, cost expectations, and the real gotchas hit during this first
deploy (extra GCP APIs needed beyond the obvious three, a persistently-403ing
`firebase projects:addfirebase` CLI call worked around via the Firebase
Console) are in `DEPLOYMENT.md`'s "Production deployment" section — read that
before attempting a second deploy or tearing this one down.

## Immediate next action for Claude Code

V1 remains closed (GO, 2026-08-13), V2 is DONE (2026-08-17), and the
production deployment above is live and verified end-to-end. There is no
open implementation work in any of the three. The human is currently running
`teste_humano.md`'s manual test/RAG-evaluation plan (originally written
against local Docker Compose; now also applicable against the production
URL above). `ROADMAP.md`/`DECISIONS.md` govern what comes next once that
finishes — most likely the V3 ("Measured N2") specification cycle, not yet
started. Dynamic appointment availability remains a separate, not-yet
-authorized future feature (D-026), distinct from V2's `dynamic_data_required`
safety correction (D-028) which V2 Phase 7 already closed.
