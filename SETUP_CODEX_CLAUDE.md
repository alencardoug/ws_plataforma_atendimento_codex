# Setup for Codex and Claude Code

## Repository use

Place this SDD package at the root of the implementation repository or merge it into the existing repository root without discarding the existing knowledge/preparatory PostgreSQL assets.

If Spec Kit is already initialized, preserve its command/skill integration and merge the constitution/spec artifacts deliberately. Do not blindly overwrite unrelated repository files.

## Codex

`AGENTS.md` is the coding-agent contract. Start with `PROMPT_START_V1.md`.

## Claude Code

`CLAUDE.md` delegates to `AGENTS.md` and provides the artifact read order. Start with `PROMPT_START_V1.md`.

## Spec Kit

Use the repository's installed Spec Kit integration. The conceptual lifecycle is:

`specify -> clarify -> plan -> tasks -> analyze -> implement -> converge`

For this V1, `specify/clarify/plan/tasks` have already been prepared. Therefore the first lifecycle operation should be **analyze**, not a fresh specify pass.

## Grill-Me

Do not run a grill for V1 merely as ritual. V1 has already undergone iterative product grilling in design discussion. For future features, grill only when important decisions are unresolved, then write resolved decisions into the spec/ADR and return to canonical SDD.
