# CLAUDE.md — Claude Code Entry Point

Read and obey `AGENTS.md` first.

Then read in this order:

1. `.specify/memory/constitution.md`
2. `PROJECT_STATE.md`
3. `specs/001-v1-assisted-customer-service/spec.md`
4. `specs/001-v1-assisted-customer-service/plan.md`
5. `specs/001-v1-assisted-customer-service/tasks.md`
6. `specs/001-v1-assisted-customer-service/data-model.md`
7. `specs/001-v1-assisted-customer-service/contracts/openapi.yaml`
8. `specs/001-v1-assisted-customer-service/acceptance.md`
9. root architecture/security/test documents
10. ADRs as referenced by the plan

## Claude Code behavior

Use installed Spec Kit commands/skills when available. Do not regenerate the product scope from scratch: the feature has already been clarified. First perform consistency analysis.

If a `grill-me` style skill is available, do **not** run it for V1 unless a genuinely unresolved design decision blocks implementation. The V1 product decisions are frozen. Use grilling for future features before their specs are finalized.

## Stop conditions

Stop the affected implementation and repair design artifacts first if:

- direct AI-to-customer send appears necessary;
- a V2+ capability becomes a dependency;
- a data model cannot preserve V1 security invariants;
- the OpenAPI contract conflicts with the spec;
- implementing six independent customer tabs would require shared anonymous identity;
- clinical/admin citation exposure cannot be enforced server-side;
- real patient data becomes necessary.
