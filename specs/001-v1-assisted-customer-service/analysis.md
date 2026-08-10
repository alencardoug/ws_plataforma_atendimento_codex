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
