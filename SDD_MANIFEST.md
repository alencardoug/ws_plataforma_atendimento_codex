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

## Current executable feature

`specs/001-v1-assisted-customer-service`

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
