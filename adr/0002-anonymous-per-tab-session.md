# ADR 0002 — Anonymous Per-Tab Customer Session

Status: Accepted

## Context

V1 customers must be anonymous. Acceptance must simulate six independent customers in tabs of one browser.

## Decision

Issue a high-entropy token per new conversation. Store the raw token only in the tab's `sessionStorage`; store only its digest server-side. Token scope is exactly one conversation.

## Consequences

- independent tabs work;
- no V1 customer account/session recovery;
- closing the tab loses access by design;
- public APIs must validate token + conversation binding.
