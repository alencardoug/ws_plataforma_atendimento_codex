# API Specification Index

Canonical machine-readable V1 contract:

`specs/001-v1-assisted-customer-service/contracts/openapi.yaml`

## API surfaces

### Public anonymous customer

- create conversation/session;
- read own conversation;
- send customer message;
- close own conversation.

Anonymous calls use a per-conversation opaque token, not an account login.

### Operator authentication

- login;
- current operator identity.

### Operator workspace

- list waiting/active conversations;
- claim waiting conversation;
- release/close where allowed;
- read conversation and messages;
- send manual/final answer;
- generate/regenerate AI draft in effective N2;
- manual knowledge search;
- take over N2 -> N1;
- read RAG evidence and AI draft provenance.

### Runtime read-only

- current global maturity mode;
- N1 assistive-search enabled flag;
- operator active-conversation capacity.

### No V1 endpoint

There is no endpoint that asks the AI service to send a customer-visible message directly.
