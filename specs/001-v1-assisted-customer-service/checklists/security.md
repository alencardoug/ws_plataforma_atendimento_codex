# Security Checklist — V1

- [x] Anonymous raw token never stored server-side.
- [x] Anonymous token not placed in URL.
- [x] Per-conversation token authorization enforced server-side.
- [x] Operator password hash only.
- [x] Operator routes require operator auth.
- [x] Customer cannot fetch AI drafts/internal retrieval.
- [x] AI generation cannot directly send.
- [x] Customer citation exposure enforced server-side.
- [x] Admin Q&A source non-exposure has negative test.
- [x] Message bodies excluded from INFO logs.
- [x] Secrets excluded from repository.
- [x] Synthetic/demo data only.
- [x] Prompt/model output cannot alter authorization/maturity state.
