# Data Model: Two-Phase Clinical Evidence Selection

No data model impact. Confirmed by direct inspection (spec.md §1, §4):

- `Evidence` (`rag/service.py:15-25`) is unchanged — both `content` (full
  parent, for `CLINICAL` items) and `matched_child_excerpt` are already
  present on every existing evidence item this feature reads.
- `RetrievalHit`, `select_evidence()`, `load_evidence()`,
  `full_parent_draft()`, `dynamic_pattern_result()` are unchanged.
- No new column, table, index, constraint, or Alembic migration.
- No response-schema change to `GET .../drafts`, `POST
  /operator/knowledge/search`, or `POST .../evidence/{id}/select` —
  `contracts/openapi.yaml` is unchanged by this feature.

This feature adds only client-side, in-memory React state
(`revealedEvidenceIds`, plan.md §5) — never persisted, never sent to the
backend, cleared on conversation switch/close exactly like the existing
`draft`/`searchEvidence` state it lives alongside.
