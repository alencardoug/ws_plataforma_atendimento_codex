# Prompt — Start V1 with Codex or Claude Code

You are implementing the currently authorized SDD feature in this repository.

Do not write code immediately.

1. Read `AGENTS.md` (and `CLAUDE.md` if you are Claude Code).
2. Read `.specify/memory/constitution.md`.
3. Read every artifact under `specs/001-v1-assisted-customer-service/`.
4. Read root `ARCHITECTURE.md`, `SECURITY.md`, `THREAT_MODEL.md`, `TEST_PLAN.md`, `DATA_MODEL.md`, `OBSERVABILITY.md`, `DECISIONS.md`.
5. Run Spec Kit analyze or perform an equivalent rigorous cross-artifact analysis.
6. Report contradictions, underspecified requirements, missing task coverage, impossible acceptance criteria, or scope leakage.
7. Fix documentation first if needed, preserving the authority order in `AGENTS.md`.
8. Only when the feature artifacts converge, implement `tasks.md` in dependency order.
9. Keep V2+ out of the code except explicit extension boundaries.
10. Before declaring done, execute all tests and the acceptance flow in `acceptance.md`, then perform a spec-to-code convergence review.

Critical invariant: in V1, AI generation is never a customer-visible message until an authenticated operator explicitly sends a final message.
