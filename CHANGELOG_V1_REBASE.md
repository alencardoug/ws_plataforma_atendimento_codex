# V1 Specification Rebase — 2026-08-10

This package supersedes the previous V1 baseline.

Material changes:

1. Customer authentication removed from V1; customer is anonymous.
2. Added per-tab anonymous conversation token design to support six simulated customers in one browser.
3. Explicit V1 queue acceptance: 6 waiting -> operator claims 4 -> 2 remain waiting; fifth claim rejected.
4. Added operator `Take over` as V1 functionality, reducing one N2 conversation to N1 until close.
5. Knowledge ingestion/vectorization moved into V1 because the corpus is not yet searchable.
6. Split knowledge strategy:
   - administrative flat Q&A;
   - clinical child retrieval + parent context.
7. Added server-side citation exposure rule:
   - clinical approved source projection may be customer-visible;
   - administrative source details remain internal.
8. Kept no-streaming V1 and specified polling/refetch as sufficient.
9. Preserved in-conversation history/persistence but no customer cross-session memory.
10. Added future opt-in CPF + password continuity design as deferred scope with safe password-verification semantics and data minimization.
11. Strengthened audit/event catalog for future Human Correction Rate/autonomy metrics.
12. Rebuilt spec/plan/tasks/OpenAPI/data model/acceptance around the clarified scope.
