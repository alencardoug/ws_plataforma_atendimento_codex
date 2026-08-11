# SDD Manifest

## Canonical sources by authority

1. current human instruction;
2. `.specify/memory/constitution.md`;
3. current feature `spec.md`;
4. current feature `plan.md`;
5. current feature `tasks.md`;
6. root architecture/security/data/test documents;
7. ADRs;
8. roadmap/explanatory docs.

## Current executable baseline

`specs/001-v1-assisted-customer-service`

## Authorized next specification

`specs/002-v2-commercial-product-experience`

V2 is authorized to proceed in SDD order. No V2 production code is executable
scope until its own `spec.md`, plan, tasks, acceptance coverage, and
cross-artifact analysis are complete.

## Required pre-code review

An agent must verify:

- every FR has at least one acceptance scenario/test mapping;
- tasks cover all P1 stories before P2/P3 optional polish;
- no V2+ capability appears as a required V1 task;
- OpenAPI does not expose direct AI-send;
- data model separates AIGeneration from customer-visible Message;
- citation exposure rule is encoded server-side;
- queue capacity rule is testable transactionally;
- ingestion supports both knowledge families.

For V2, perform the same review against its own specification and additionally
verify the token-display, selected-evidence, selected-context, explicit-send,
audit, citation, and manual-fallback boundaries before implementation.
