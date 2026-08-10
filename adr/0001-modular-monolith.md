# ADR 0001 — Modular Monolith for V1

Status: Accepted

## Context

V1 must exist in 1–2 weeks, remain inspectable, and demonstrate multiple domain capabilities without distributed-system overhead.

## Decision

Use one backend deployment organized into explicit modules plus one SPA frontend and PostgreSQL.

## Consequences

- simpler local development and transactions;
- clear module boundaries preserve future extraction options;
- no microservices/event broker in V1.
