# Future Session Continuity — Deferred

Not V1.

## Product intent

A future customer may choose to persist only essential continuity data. The UI asks whether the person wants to save data. If yes, a saved profile can be protected by CPF + password and reused to resume relevant service state.

Examples of potentially useful persisted fields, subject to later privacy/product review:

- full name when needed for service continuity;
- confirmed appointment date/time;
- appointment location;
- appointment type;
- whether documents/preparation are required;
- minimal preparation/reminder state;
- email;
- phone;
- reschedule/cancel reference needed by the application.

Do not persist entire conversation history merely because storage is available. Persist the minimum needed for continuity.

## Authentication semantics

The product may behave as "CPF + password must match to resume". Technical implementation must use a password verifier, not plaintext equality.

If verification succeeds: resume authorized saved state.

If verification fails: do not reveal whether the CPF exists and do not attach a new memory to an existing identity. The person may continue as a new anonymous session.

## Why deferred

This introduces persistent personal identity, account-security concerns, recovery semantics, privacy obligations, and data-retention design. It must receive a separate spec and threat model before implementation.
