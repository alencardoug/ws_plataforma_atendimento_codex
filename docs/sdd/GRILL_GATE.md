# Optional Grill Gate

Use an aggressive interview/grill only when a future feature has decisions whose answers materially change architecture, security, user flow, scope, or acceptance.

Do not grill:

- resolved V1 decisions;
- implementation syntax;
- trivial UI copy;
- choices already fixed by constitution/ADR without new evidence.

A grill is complete when the remaining uncertainty is small enough to write deterministic acceptance criteria.

After grilling:

1. write decisions into `spec.md`;
2. write architecture choices into ADR/plan;
3. discard the grill transcript as an implementation authority;
4. continue canonical SDD.
