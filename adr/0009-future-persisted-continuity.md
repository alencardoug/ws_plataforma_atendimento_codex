# ADR 0009 — Future Persisted Customer Continuity

Status: Deferred

## Decision intent

A future opt-in feature may persist minimal service-continuity state and resume it after CPF + safely verified password authentication.

Wrong credentials never access/overwrite existing saved state; fallback is a separate anonymous session.

## Consequences

Requires a future dedicated spec, privacy/security threat model, retention design, and recovery semantics. Not V1.
