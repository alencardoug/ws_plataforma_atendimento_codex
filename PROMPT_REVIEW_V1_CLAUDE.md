# Prompt — Independent Claude Code Review After V1 Human Acceptance

Use this prompt in Claude Code from the repository root, preferably in Plan
mode for the first pass.

```text
Act as an independent, read-only reviewer of the completed V1 implementation.
Do not edit files, generate migrations, implement fixes, commit, push, or start
V2. Do not reinterpret roadmap items as executable scope.

Context: the human is finishing the manual acceptance of V1. The purpose of
this review is to determine whether V1 is genuinely complete, identify defects
or documentation drift, and produce evidence for a go/no-go decision before
the next feature cycle.

Read and obey AGENTS.md and CLAUDE.md. Then read, in authority order:

1. .specify/memory/constitution.md
2. specs/001-v1-assisted-customer-service/spec.md
3. specs/001-v1-assisted-customer-service/plan.md
4. specs/001-v1-assisted-customer-service/tasks.md
5. specs/001-v1-assisted-customer-service/acceptance.md
6. specs/001-v1-assisted-customer-service/data-model.md
7. specs/001-v1-assisted-customer-service/contracts/openapi.yaml
8. specs/001-v1-assisted-customer-service/analysis.md
9. PROJECT_STATE.md and SDD_MANIFEST.md
10. relevant root architecture, security, data, test, operations, and decision
    documents
11. implementation and tests needed to verify each claim
12. the current git diff, treating uncommitted changes as work under review

Perform an equivalent of Spec Kit analyze plus a spec-to-code convergence
review. Verify at least:

- every V1 functional/non-functional requirement has implementation and test
  evidence;
- acceptance claims match the current code and documented commands;
- anonymous-token scope, operator authorization, max-four capacity, explicit
  human outbound send, citation exposure, abstention, AI/RAG fallback, and
  append-only audit invariants are enforced server-side and negatively tested;
- OpenAPI, persistence model, frontend behavior, and implementation agree;
- no V2 behavior is active in the V1 runtime;
- README/quickstart/operations instructions match the actual Compose stack;
- completed tasks and checklists agree with PROJECT_STATE.md;
- no secrets, real patient data, message bodies at INFO, raw anonymous tokens,
  or chain-of-thought persistence are present.

Treat the following observed behavior as a known finding to classify, not as
permission to implement it: administrative evidence marked
dynamic_data_required=true is currently retrieved as literal answer text when
no resolver runs, which can expose internal implementation language such as
scheduling.available_offers. Determine its V1 impact and verify that the
planned next-cycle boundary in ROADMAP.md and decision D-026 are coherent.
Distinguish clearly between:

A. a V1 defect/safety correction required before closure;
B. documentation or acceptance-evidence drift;
C. an authorized requirement for the next feature specification;
D. optional improvement or future scope.

Do not silently resolve contradictions. Report each finding with:

- severity: blocker, high, medium, or low;
- classification: A, B, C, or D;
- exact file and line evidence;
- violated requirement/invariant, if any;
- smallest recommended disposition;
- whether V1 closure must wait.

Also list checks that passed, residual risks, and questions that require a
human decision. End with exactly one recommendation:

- GO — close V1;
- CONDITIONAL GO — close only after listed documentation/evidence corrections;
- NO-GO — listed V1 defects must be fixed and retested.

Output the report in this chat only. Do not modify the repository. If test
execution or any state-changing command would materially improve confidence,
list the exact proposed commands in a separate section and wait for explicit
approval before running them.
```

After reviewing the first-pass report, a human may authorize a second pass to
run the agreed gates. Keep file edits disabled during that verification pass;
bring approved findings back into the canonical artifacts through the normal
SDD authority order.
