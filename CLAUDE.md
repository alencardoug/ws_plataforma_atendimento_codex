# CLAUDE.md — Claude Code Entry Point

Read and obey `AGENTS.md` first.

## Current lifecycle state

- V1 implementation and automated acceptance are complete.
- Human V1 acceptance and independent closure review are the current work.
- `specs/001-v1-assisted-customer-service` remains the only executable feature.
- `specs/002-dynamic-appointment-availability` is planned but does not exist as
  executable scope yet. Do not implement it from `ROADMAP.md` or `DECISIONS.md`.

Read in this order:

1. `.specify/memory/constitution.md`
2. `PROJECT_STATE.md`
3. `specs/001-v1-assisted-customer-service/spec.md`
4. `specs/001-v1-assisted-customer-service/plan.md`
5. `specs/001-v1-assisted-customer-service/tasks.md`
6. `specs/001-v1-assisted-customer-service/data-model.md`
7. `specs/001-v1-assisted-customer-service/contracts/openapi.yaml`
8. `specs/001-v1-assisted-customer-service/acceptance.md`
9. `specs/001-v1-assisted-customer-service/analysis.md` and checklists
10. `SDD_MANIFEST.md`, `ROADMAP.md`, and `DECISIONS.md`
11. root architecture/security/data/test/operations documents
12. ADRs as referenced by the plan
13. the current Git diff when reviewing uncommitted work

## Operating modes

### Independent V1 closure review

Use `PROMPT_REVIEW_V1_CLAUDE.md`. The first pass must be independent and
read-only, preferably in Claude Code Plan mode:

- analyze artifacts, implementation, tests, acceptance evidence, and current
  uncommitted changes;
- report findings in chat with exact evidence and a GO, CONDITIONAL GO, or
  NO-GO recommendation;
- do not edit files, run state-changing commands, implement fixes, commit,
  push, or start the next feature;
- propose any useful verification commands and wait for explicit human
  approval before running them.

Do not update canonical artifacts while determining the review verdict. A
human must first classify and approve each proposed correction.

### Approved V1 correction

Only perform a correction after explicit human authorization. Follow the
authority order in `AGENTS.md`: repair the highest-authority artifact that must
change, propagate the decision through plan/tasks when required, analyze again,
then implement and rerun the affected gates. Do not broaden a defect fix into
future scheduling behavior.

### Next feature cycle

The planned next cycle is read-only dynamic appointment availability, recorded
in `ROADMAP.md` and decision D-026. When a human explicitly authorizes that
cycle, create `specs/002-dynamic-appointment-availability/` and start at
`specify -> clarify -> plan -> tasks -> analyze`. Do not copy the V1 artifacts
as if they were an approved feature specification, and do not write production
code before the new analysis and acceptance coverage are complete.

## General Claude Code behavior

Use installed Spec Kit commands/skills when available. For V1 closure, perform
analyze/convergence rather than regenerating product scope. For a newly
authorized feature, begin a fresh SDD lifecycle.

If a `grill-me` style skill is available, do **not** run it for V1 unless a genuinely unresolved design decision blocks implementation. The V1 product decisions are frozen. Use grilling for future features before their specs are finalized.

## Stop conditions

Stop the affected implementation and repair design artifacts first if:

- direct AI-to-customer send appears necessary;
- a V2+ capability becomes a dependency;
- a data model cannot preserve V1 security invariants;
- the OpenAPI contract conflicts with the spec;
- implementing six independent customer tabs would require shared anonymous identity;
- clinical/admin citation exposure cannot be enforced server-side;
- unresolved `dynamic_data_required` evidence would expose internal table,
  resolver, placeholder, or implementation text;
- real patient data becomes necessary.
