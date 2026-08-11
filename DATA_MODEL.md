# Repository Data Model

The executable V1 schema is specified in `specs/001-v1-assisted-customer-service/data-model.md`.

Core entities:

- `OperatorUser`
- `Conversation`
- `ConversationAssignment`
- `Message`
- `AIGeneration`
- `RetrievalRun`
- `RetrievalHit`
- `KnowledgeDocument`
- `KnowledgeChunk`
- `MessageCitation`
- `AuditEvent`

## Key invariants

- customer identity is not persisted as a person/account in V1;
- anonymous access token is stored only as a hash/digest;
- one active assignment per conversation;
- max 4 active assignments per operator enforced transactionally/application-side;
- AI generation is not a customer message;
- a customer-visible operator message may reference an AI generation as provenance;
- customer-visible citation must point only to knowledge marked exposable;
- audit events are immutable through application APIs;
- clinical `content.chunks` reference one parent `content.documents` row;
- administrative Q&A chunks have no parent requirement;
- embedding metadata stores model/version and embedding status.

V1 adopts the existing `content.documents`, `content.chunks`, and
`content.qa_entries` tables in place. No parallel `knowledge_*` corpus is
created.
