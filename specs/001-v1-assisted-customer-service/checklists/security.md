# Security Checklist — V1

- [ ] Anonymous raw token never stored server-side.
- [ ] Anonymous token not placed in URL.
- [ ] Per-conversation token authorization enforced server-side.
- [ ] Operator password hash only.
- [ ] Operator routes require operator auth.
- [ ] Customer cannot fetch AI drafts/internal retrieval.
- [ ] AI generation cannot directly send.
- [ ] Customer citation exposure enforced server-side.
- [ ] Admin Q&A source non-exposure has negative test.
- [ ] Message bodies excluded from INFO logs.
- [ ] Secrets excluded from repository.
- [ ] Synthetic/demo data only.
- [ ] Prompt/model output cannot alter authorization/maturity state.
