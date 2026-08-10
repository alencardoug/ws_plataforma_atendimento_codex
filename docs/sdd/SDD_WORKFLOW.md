# SDD Workflow

## New feature

1. product discovery/grill if decision space is materially ambiguous;
2. `spec.md`: behavior, actors, stories, acceptance, scope boundaries;
3. clarify unresolved decisions;
4. `plan.md`: technical architecture and implementation strategy;
5. `tasks.md`: dependency-ordered executable tasks;
6. analyze cross-artifact consistency;
7. implement;
8. test;
9. converge code against spec;
10. update state/roadmap.

## Change to active feature

A product behavior change requires spec first. A purely technical implementation detail may update plan/ADR without changing behavior.

## Future roadmap rule

A roadmap item is never an implementation instruction. It becomes executable only after a new feature directory is created and clarified.
