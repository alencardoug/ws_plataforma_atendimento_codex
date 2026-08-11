# Cross-Artifact Analysis — External Review

**Reviewer:** Claude Code (Sonnet 5), acting as external reviewer at project owner's request. This agent did **not** author `spec.md` / `plan.md` / `tasks.md` / `data-model.md` / `openapi.yaml` (Codex did). This document is independent verification, not a rewrite of authorial intent.

**Date:** 2026-08-10
**Status:** Advisory. Does not modify any authoritative artifact. Satisfies `tasks.md` Phase 0 gates T000–T001 as an independent pass; Codex (or any implementing agent) should read this before starting Phase 1 (T010+).
**Open item:** Section 6 requires a decision from the project owner (@alencardoug) that no agent should make unilaterally.

---

## 1. Verdict on the spec package itself

Read and cross-checked: `.specify/memory/constitution.md`, `spec.md`, `plan.md`, `tasks.md`, `data-model.md`, `contracts/openapi.yaml`, `acceptance.md`, `research.md`, `quickstart.md`, `checklists/*.md`, plus root `AGENTS.md`, `CLAUDE.md`, `ARCHITECTURE.md`, `SECURITY.md`, `THREAT_MODEL.md`, `TEST_PLAN.md`, `DATA_MODEL.md`, `DECISIONS.md`, `REQUIREMENTS.md`, `SDD_MANIFEST.md`, `CHANGELOG_V1_REBASE.md`.

**No internal contradiction found.** The constitution's 12 articles each have a direct, consistent counterpart in spec/plan/tasks/data-model (e.g. Article IX "not event sourcing" is echoed almost verbatim in `ARCHITECTURE.md` §"Event architecture"; Article XI "autonomy only decreases" matches `DECISIONS.md` D-022). FR-001..104 in `spec.md` all trace to a task range in `checklists/traceability.md`. `openapi.yaml` exposes no direct AI-send endpoint, matching Article III / FR-033 / SECURITY.md. This is a well-formed, internally coherent SDD package — the risk is not in the spec's authorship quality.

`checklists/requirements.md` still lists `analyze` as unchecked (last line). **This document is that analyze pass.** Once section 6 below is resolved, that box can be checked.

---

## 2. Verified real-repository state (ground truth, not inference)

Collected by direct inspection (`psql`, `find`, reading source), not assumption:

```text
PostgreSQL version running:  16.14  (docker-compose.yml pins pgvector/pgvector:pg16)
Schemas present:              billing, content, governance, identity, public, scheduling
Tables total:                 19  (only content.* — 4 tables — is in V1 scope)

content.documents:            57 rows   (parent = metadata only; body lives in
                                          documents/clinical/**/*.md via patient_markdown_path,
                                          NOT a DB column)
content.chunks:                570 rows  (child; content_markdown inline; embedding vector(1536)
                                          column + HNSW index + tsvector already provisioned)
content.chunks embedded:       0 / 570   (embedding column is NULL everywhere)
content.qa_entries:            86 rows   (flat; same embedding/tsvector provisioning; 0 embedded)
content.document_sources:      0 rows   (source linkage table exists, never populated)

app/ directory:                single file app/main.py (249 lines), pip requirements.txt
backend/ directory:            does not exist
frontend/ directory:           does not exist
alembic/ (any):                does not exist anywhere in repo
.env.example:                  POSTGRES_*, DATABASE_URL, CPF_ENCRYPTION_KEY, APP_TIMEZONE only —
                                none of the 8 V1-required vars from spec.md §8 are present
app/requirements.txt:          fastapi, uvicorn, sqlalchemy, psycopg, pydantic, cryptography,
                                email-validator — no pytest, no alembic, no argon2/passlib,
                                no jose/pyjwt, no openai SDK
```

`content.documents` schema (`db/init/001_schema.sql`): `document_id, title, document_type, cancer_type, care_phase, procedure_slug, audience[], language, responsible_physician, version, status, created_at, last_reviewed_at, next_review_at, patient_markdown_path, dynamic_data_required, dynamic_resolver, metadata` — **no body-text column, no embedding column on the parent itself.**

`app/main.py` currently implements: `/health`, `/v1/specialties`, `/v1/availability`, `/v1/appointments/hold`, `/v1/appointments/{id}/simulate-payment`, `/v1/policies/{code}`, `/v1/content/search`. **None of these appear in `contracts/openapi.yaml`.** The V1 feature's entire API surface (`/public/conversations`, `/auth/operator/login`, `/operator/conversations/*`, `/operator/conversations/{id}/drafts`, `/operator/knowledge/search`) does not exist in the current codebase.

---

## 3. Concrete gaps between spec and repository, ranked by severity

| # | Gap | Evidence | Severity |
|---|---|---|---|
| 1 | ~~Constitution missing~~ | Resolved 2026-08-10 — `.specify/memory/constitution.md` now present and consistent (§1) | ✅ closed |
| 2 | PostgreSQL 17 required, 16.14 running | `ARCHITECTURE.md:18`, `acceptance.md` item A, vs. `docker-compose.yml` `image: pgvector/pgvector:pg16` | 🔴 blocks Phase 1 gate (T012) |
| 3 | Alembic required, absent; raw `db/init/*.sql` (run once, on volume creation only) is the only migration mechanism today | `AGENTS.md` "Data rules", `plan.md` §3, `tasks.md` T027 vs. no `alembic/` dir, not in `requirements.txt` | 🔴 blocks Phase 2 gate (T020–T028) |
| 4 | Modular backend (`backend/app/{auth,anonymous_access,conversations,autonomy,operator_workspace,knowledge,rag,ai,audit,shared,infrastructure}`) + Poetry required; only a single-file `app/main.py` + pip exists | `plan.md` §2, `ARCHITECTURE.md` "Target stack" | 🔴 full backend rewrite, not incremental |
| 5 | React/TS/Vite frontend required; `frontend/` does not exist | `plan.md` §12, `ARCHITECTURE.md` | 🔴 greenfield |
| 6 | `.env.example` missing all 8 V1-required vars (`GLOBAL_MATURITY_MODE`, `N1_ASSISTIVE_SEARCH_ENABLED`, `OPERATOR_MAX_ACTIVE_CONVERSATIONS`, `OPENAI_API_KEY`, `AI_GENERATION_MODEL`, `AI_EMBEDDING_MODEL`, `ANONYMOUS_TOKEN_PEPPER`, `OPERATOR_AUTH_SECRET`) | `spec.md` §8 vs. current `.env.example` | 🟡 mechanical, low risk |
| 7 | Parent-child model mismatch: spec's `knowledge_chunks` treats `PARENT` as a chunk row with real body text (`chunk_role=PARENT`); current `content.documents` has no body column at all — body only exists as a `.md` file on disk | `data-model.md` §6 vs. `content.documents` schema (§2 above) | 🟡 needs an explicit ingestion step, not just a mapping (see §7 below) |
| 8 | `customer_citation_allowed` does not exist on any current table (`documents`, `chunks`, `qa_entries`) | `data-model.md` §5 vs. `db/init/001_schema.sql` | 🟡 new field, must be assigned during ingestion, not migrated |
| 9 | No test framework installed at all (`pytest`, frontend test runner) | `plan.md` §14, `TEST_PLAN.md` vs. `requirements.txt` | 🟡 Phase 1 scaffolding gap, expected, not a contradiction |
| 10 | Legacy `scheduling.*` / `identity.*` / `billing.*` / `governance.*` schemas and all of `app/main.py`'s current endpoints have no mention anywhere in the V1 feature package, and V1 explicitly excludes "autonomous appointment scheduling," "real patient data," and any "customer person/account" persistence | `spec.md` §10, `CHANGELOG_V1_REBASE.md` ("supersedes the previous V1 baseline") vs. 15 live tables and a running API surface | 🟠 **not a contradiction — an undecided scope boundary.** See §6. |

---

## 4. What's already reusable as-is (do not rebuild)

- `content.chunks`: 570 rows, already has `vector(1536)` column, HNSW index (`chunks_embedding_hnsw_idx`), and a generated `tsvector` column. Dimension 1536 is compatible with common OpenAI embedding models (e.g. `text-embedding-3-small`) — no schema change needed here once `AI_EMBEDDING_MODEL` is pinned to a 1536-dim model.
- `content.qa_entries`: 86 rows of flat administrative Q&A, **directly the `ADMIN_QA` ingestion source** `US10` calls for. This includes 15 entries added in a prior session specifically to close retrieval gaps found in manual testing (categories `risco_hereditario`, `sus`, `apoio_emocional`, `prognostico`), each carrying `metadata.escalation_recommended` for the sensitive categories — this maps cleanly onto the spec's abstention/escalation spirit (US12) even though it predates this spec package.
- `documents/clinical/mama/**` and `documents/clinical/colorretal/**`: 57 source markdown files with clean, consistent front-matter (`document_id`, `title`, `version`, `responsible_physician`, dates) — good ingestion input for synthesizing `PARENT` chunk rows (§7).
- `documents/GOVERNANCE.md`: already encodes, in prose, most of the citation/abstention/safety posture the new spec formalizes in schema (`customer_citation_allowed`, abstention reason classes). Worth a straight read for whoever writes the ingestion/citation-policy code — the intent already exists, just not as structured data.

---

## 5. Recommended resolution order before Phase 1 (T010+)

1. **Project owner resolves §6** (this cannot be automated).
2. Bump `docker-compose.yml` to a `pgvector/pgvector:pg17` (or equivalent) image; confirm `pgvector` extension version compatibility.
3. Add `alembic`, `pytest`, `httpx`/`pytest-asyncio`, `argon2-cffi` (or chosen hash lib), `pyjwt`/equivalent, and `openai` to a new `backend/` dependency set (Poetry, per `plan.md`).
4. Add the 8 missing variables to `.env.example` (mechanical, can be done immediately, no decision required).
5. Write the ingestion adapter design explicitly into `plan.md` §9 or a new `docs/architecture/KNOWLEDGE_INGESTION.md` (referenced but not found in repo — confirm it should be created): the `PARENT` chunk role must be synthesized from each `documents/clinical/**/*.md` body (stripped of front-matter), not copied from a DB column, because no such column exists today.
6. Only then start `tasks.md` Phase 1.

---

## 6. Open decision requiring the project owner — not delegable

The current database (schemas `scheduling`, `identity`, `billing`, `governance`) and `app/main.py` implement a full appointment-scheduling/payment-simulation demo that predates this V1 feature. **No document in this package says what happens to it.** Three honest options, stated neutrally:

- **A. Retire it.** Drop those schemas/endpoints; `content.*` becomes the only surviving asset, feeding the new ingestion pipeline. Cleanest match to the spec as written.
- **B. Let it coexist, dormant.** Leave schemas/tables in place (they don't collide with new table names), but no V1 code path touches them. Lowest immediate effort, but leaves permanently-dead code/schema in the repo with no spec coverage — a future maintainer (or agent) will hit the same question again.
- **C. Fold relevant pieces in later.** Explicitly defer scheduling/appointment integration to a labeled future feature (V2+), and say so in `ROADMAP.md`/`DECISIONS.md` now, so it stops looking like an accidental omission.

Whichever is chosen, it should be written into `DECISIONS.md` (a new `D-0XX`) and `spec.md` §10 (out-of-scope list) or §9 (data requirements), not left implicit — per Constitution Article I.

---

## 7. Ingestion mapping notes for T003 / T080 / T081

For whoever implements ingestion, concrete old→new field mapping observed directly from schema + files:

**Administrative Q&A** (`content.qa_entries` → `knowledge_documents`/`knowledge_chunks` role=`QNA`): direct 1:1. `qa_id`→`external_id`, `question`→`question`, `answer_markdown`→`content`, `category`+`metadata`→`metadata_json`. `customer_citation_allowed` should default `false` per `data-model.md` §5, consistent with `GOVERNANCE.md`.

**Clinical parent-child** (`content.documents` + `content.chunks` → `knowledge_documents` + `knowledge_chunks` roles `PARENT`/`CHILD`):
- One `knowledge_documents` row per `content.documents` row (`document_id`→`external_id`, `knowledge_type=CLINICAL`).
- One synthesized `knowledge_chunks` row per document with `chunk_role=PARENT`: `content` must be read from the actual file at `patient_markdown_path` (body only, front-matter stripped) — **this does not exist as a DB value today.**
- One `knowledge_chunks` row per existing `content.chunks` row with `chunk_role=CHILD`, `parent_chunk_id`→the synthesized PARENT row above, `content`←`content_markdown`, embedding carried over only if already computed (currently none are).
- `customer_citation_allowed` defaults `true` for approved clinical parents per `data-model.md` §5.

This confirms `plan.md` §9's instruction ("write an adapter... rather than rewriting source data") is achievable, but the PARENT-synthesis-from-file step should be made explicit in the plan since it's currently only inferable, not stated.

---

## 8. Repository-aware follow-up — Codex, 2026-08-10

This section is a later review and supersedes recommendations in §§3–7 where
explicitly stated. The original Claude Code review is retained above as an
independent historical record.

### 8.1 Inspection scope and evidence boundary

Read/reviewed: agent instructions, constitution, every active feature artifact,
root architecture/security/data/test/operations documents, ADRs, OpenAPI,
existing FastAPI source, Docker configuration, all DDL/bootstrap SQL, corpus
generators, JSONL catalogs, prompts, and the structure/content contract of the
generated clinical Markdown corpus.

The Docker service was stopped during this follow-up, so no new live-database
claims are made here. Live PostgreSQL 16.14/table/NULL-embedding counts in §2
remain evidence from Claude's earlier direct inspection. Version-controlled
assets were independently reconciled with these results:

```text
clinical catalog parents:       57 unique IDs
clinical Markdown files:        57; 0 missing; 0 front-matter ID mismatches
SQL clinical parent inserts:    57
SQL clinical child inserts:     570; 0 orphan/duplicate child IDs
administrative JSONL Q&A:       86 unique IDs
```

### 8.2 Corrected parent-child finding

The existing hierarchy is already structurally valid:

```text
content.documents.document_id (clinical parent)
                 ^
                 |
content.chunks.parent_document_id (clinical child, 570 rows)
```

The recommendation in §7 to manufacture one additional `PARENT` chunk per
document is rejected. It would duplicate the parent identity and force a second
knowledge corpus solely to match a conceptual table sketch. V1 instead adopts
`content.documents`, `content.chunks`, and flat `content.qa_entries` in place.
Ingestion loads/validates each Markdown parent body and persists its canonical
snapshot/hash on `content.documents`; only child and Q&A records are embedded.
`data-model.md`, `plan.md`, ingestion architecture, and T022/T080/T081/T091 now
state this mapping.

### 8.3 Repository-fit corrections

- Greenfield `backend/` + Poetry was unnecessary churn. The plan now keeps the
  existing `app/` backend root and pip workflow while requiring the same logical
  modules and dependency boundaries.
- Legacy `db/init/*.sql` may already be applied and cannot serve as editable
  Alembic history. The plan now requires forward-only Alembic adoption with
  explicit empty-DB and legacy-baseline preflight test paths.
- V1 conversation/audit tables use a separate service schema; the populated
  `content.*` knowledge tables are evolved in place.
- PostgreSQL 16 -> 17 requires a documented data-volume migration/recreation
  path; changing only the Docker image is not sufficient.
- Legacy scheduling/payment/CPF source and schemas may remain as historical
  assets, but their endpoints are excluded from the V1 runtime because the
  active spec explicitly excludes scheduling execution and persisted customer
  identity.
- The OpenAPI send request now accepts retrieval-hit IDs as citation candidates,
  removing an ambiguity between text knowledge IDs and UUID API identifiers.
- FR and NFR task/test traceability is now explicit.

### 8.4 Remaining implementation gaps (not documentation contradictions)

No V1 implementation has been completed. PostgreSQL 17 Compose, Alembic,
modular backend, frontend, authentication, conversations, audit, ingestion,
embeddings/retrieval, AI drafts, security enforcement, and all automated gates
remain tasks. `.env.example` still lacks V1 settings and is intentionally left
for T013 together with typed settings T014 so names cannot drift.

### 8.5 Analyze verdict

After the repairs above, the authoritative V1 artifacts are mutually
consistent and fit the repository's actual reusable assets. Acceptance coverage
is complete at task/test-planning level. Phase 0 T000–T003 is complete; this
does not imply that any implementation or DONE checklist item has passed.

## 9. Post-implementation convergence — Codex, 2026-08-10

The completed implementation was compared again with the constitution, spec,
plan, tasks, data model, OpenAPI, event catalog, security rules, and actual
PostgreSQL schema. The earlier §8.4 gap list is now historical: PostgreSQL 17,
Alembic, modular backend, React frontend, authentication, conversations,
audit, ingestion, pgvector retrieval, N2 drafts, citations, and automated gates
are implemented.

Convergence findings and repairs made during the final pass:

- retained the canonical `content.documents -> content.chunks` hierarchy and
  flat `content.qa_entries`, with no duplicate knowledge corpus;
- fixed changed-content ingestion so canonical Q&A/child fields and embeddings
  are updated together;
- added the missing `knowledge.manual_search` audit event;
- added Compose overrides needed to run deterministic N1/N2 acceptance without
  altering secret-bearing `.env` values;
- completed the N1 evidence-only UI and real Chrome E2E scenarios;
- compared all 17 contracted operation paths with the generated FastAPI
  OpenAPI surface; only `/health` and `/ready` remain additional operational
  probes outside the feature contract.

No material V1 spec/code divergence remains. No V2 behavior was introduced.

## 10. Human-acceptance refinement — operator provisioning

Review on 2026-08-11 found no tracked implementation of
`LOGIN_OPERATOR_USERNAME` or `LOGIN_OPERATOR_PASSWORD`: Pydantic settings ignore
those extra local `.env` keys and FastAPI startup does not invoke operator seed
logic. Compose previously used `env_file: .env`, which unnecessarily forwarded
the ignored values to the backend process but still did not provision an
account. The correction replaces that pass-through with an explicit allowlist
of supported backend settings. The persisted local demonstration database did
contain multiple active synthetic operators created by prior explicit
seed/smoke invocations; that durable state, rather than environment-driven
auto-provisioning, explains why more than one credential could log in.

The repaired V1 contract makes the existing intended boundary explicit:

- the offline seed CLI is the only operator provisioning path;
- startup never provisions credentials;
- Compose does not forward unsupported local `.env` entries to the backend;
- the plaintext seed password is passed to the one-shot command, not retained
  as a backend runtime setting;
- normalized-email upsert keeps repeated provisioning idempotent for that
  identity;
- multiple operators remain valid domain data, so historical accounts are not
  destructively removed as part of this correction.

This is a V1 security/operations clarification covered by FR-017 and
T201-T203. It does not introduce a second auth route, restrict the domain to a
single operator, or activate future scheduling behavior.

Post-repair convergence evidence:

- Compose configuration resolves successfully and its backend environment
  allowlist excludes both unsupported `LOGIN_OPERATOR_*` keys even while they
  remain in the local interpolation-only `.env` file;
- unit tests prove normalized-email seed update, ignored unsupported settings,
  and absence of provisioning from the application factory;
- backend Ruff, mypy, and pytest pass (7 tests);
- frontend ESLint, TypeScript, Vitest (3 tests), and production build pass;
- the recreated Compose stack reports backend health/readiness and serves the
  operator frontend.

No material spec/plan/tasks/code divergence remains for this refinement. The
local database's historical synthetic operators remain active pending an
explicit human choice of which account(s) to retain; no destructive cleanup was
required to establish the single provisioning path.

## 11. Post-acceptance refinement — multiline message rendering

Review on 2026-08-11 found that the operator send flow already persisted and
returned newline characters, but normal browser whitespace handling collapsed
them visually. FR-036 now requires intentional line breaks to be preserved in
both web histories. The OpenAPI text fields, plan, task T204, and acceptance
protocol section K use the same plain-text-only constraint.

The frontend shares `MessageBody` between the customer and operator histories;
its `white-space: pre-wrap` rendering preserves newlines without interpreting
message content as HTML. The component regression test verifies the literal
newline and shared presentation class, while the existing Chrome E2E flow now
also asserts newline content and computed rendering in both interfaces.

Post-repair verification: frontend ESLint, TypeScript, Vitest (4 tests), and
production build pass; the local frontend container was rebuilt and backend
readiness is healthy. The credential-dependent Chrome E2E command could not be
executed in this shell because `E2E_OPERATOR_EMAIL` and
`E2E_OPERATOR_PASSWORD` were unavailable.

## 12. Post-acceptance refinement — concise customer-ready AI drafts

Review on 2026-08-11 found two independent causes of verbose drafts: the
OpenAI adapter stored a version identifier without passing the corresponding
versioned prompt content to the provider, and the deterministic provider echoed
the first retrieval evidence/chunk as `draft_text`. FR-056 now defines the
customer-ready draft boundary, and the plan, OpenAPI, acceptance protocol, and
T205 cover the same constraint.

The generation provider now receives the loaded prompt content and rejects empty
`ANSWER` output. The prompt requires only a concise Brazilian-Portuguese
response in `draft_text`; evidence, hit IDs, and retrieval metadata remain
separate operator-only fields. A generic greeting may receive a natural greeting
without evidence because it makes no organization-specific claim. The
deterministic provider now models this contract instead of copying source content.

Post-repair verification: Python syntax compilation passed; three deterministic
provider tests passed in the rebuilt backend container, covering a greeting
without evidence, absence of copied chunks, and use of the versioned OpenAI
prompt. Ruff, mypy, and pytest are not installed in either available shell or
the runtime container, so the full Python quality gate could not be executed
there.

## 13. Correction — generation completion budget

The initial concise-draft refinement temporarily set
`max_completion_tokens=300`. With a RAG request, `gpt-5-mini` consumed that
entire budget as reasoning tokens and returned an empty completion with
`finish_reason=length`; the empty JSON then failed the required `status`
validation and surfaced as `AI_PROVIDER_UNAVAILABLE`. The artificial completion
limit was removed. Concision is governed by the versioned prompt, not by a
token ceiling.

The prompt was further refined to require a valid JSON object and make
`draft_text` exclusively the final concise customer response. Replaying the
same failed conversation history and eight retrieved evidence records against
the rebuilt backend returned `ANSWER` with a 376-character draft, four used
retrieval hits, and no chunk marker in the draft. Backend readiness remained
healthy.

## 14. Post-acceptance refinement — retrieval-specific draft behavior

The generation path previously treated all retrieved evidence as one generic
LLM context, despite clinical evidence already carrying the expanded parent
document. FR-057 through FR-059 now make the three requested paths explicit:
the highest-ranked clinical child result produces the full parent document for
explicit send, an administrative Q&A result is interpreted by the LLM in the
context of the latest customer request, and no evidence permits only a brief
general/clarifying response without unsupported clinical or organizational
claims.

The backend records the full parent draft as `clinical-parent-document` without
calling the LLM, preserving the selected retrieval hit as provenance. For the
Q&A and no-evidence paths, the LLM receives only Q&A evidence or no evidence,
respectively. The operator UI identifies the first path with `Usar documento
completo`, which inserts the entire parent text into the normal explicit-send
box.

Post-repair verification: Python compilation, frontend ESLint/TypeScript/Vitest
(4 tests), production frontend build, and six deterministic generation strategy
tests pass. The rebuilt backend/frontend stack is healthy. The latest retrieval
set was inspected read-only and has clinical evidence at rank 1, so it follows
the full-parent path as intended. Full Python Ruff/mypy/pytest gates remain
unavailable in the supplied environments.

## 15. Post-acceptance refinement — manual evidence inspection

The manual-search request already sent the value from the `Busca manual` field
to `/operator/knowledge/search`, but the operator UI rendered only each result
title. That hid the returned Q&A answer or expanded clinical parent and made it
appear that the field was not used. FR-073, the plan, acceptance protocol, and
T207 now require the evidence content to be inspectable.

The V1 UI now renders each manual result's title, full content, and matching
clinical-child excerpt when present. This remains an evidence-only V1 workflow:
it does not select evidence or alter the separate N2 draft-retrieval query. The
operator-selected evidence workflow is recorded in the V2 roadmap.

Post-repair verification: frontend ESLint, TypeScript, Vitest (5 tests), and
production build pass; the frontend container was rebuilt. The complete
credential-dependent E2E suite remains unavailable in this shell.
