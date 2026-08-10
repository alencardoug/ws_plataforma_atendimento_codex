# Observability — V1

## Principle

Record durable operational facts now so later maturity metrics can be computed without redesigning the system. V1 does not need a management dashboard.

## Correlation identifiers

Where applicable:

- `request_id`
- `conversation_id`
- `operator_id`
- `message_id`
- `retrieval_run_id`
- `ai_generation_id`
- `knowledge_document_id`

## Structured logs

Log:

- endpoint/operation;
- status/outcome;
- duration;
- error class;
- correlation IDs;
- AI provider/model alias and token usage when available;
- retrieval hit counts and timings.

Do not log message text at INFO.

## Durable audit events

Minimum catalog:

- `conversation.created`
- `conversation.claimed`
- `conversation.released`
- `conversation.closed`
- `conversation.taken_over`
- `message.customer_received`
- `message.operator_sent`
- `rag.search_started`
- `rag.search_completed`
- `rag.search_failed`
- `ai.draft_generated`
- `ai.draft_regenerated`
- `ai.draft_abstained`
- `ai.draft_accepted`
- `ai.draft_edited`
- `knowledge.manual_search`
- `knowledge.ingestion_started`
- `knowledge.ingestion_completed`
- `knowledge.ingestion_failed`
- `auth.login_succeeded`
- `auth.login_failed`

See `docs/architecture/EVENT_CATALOG.md`.

## V1 metrics

Operational/debug metrics can include:

- request latency;
- RAG latency;
- generation latency;
- AI errors;
- retrieval errors;
- active/waiting conversation count;
- operator active conversation count;
- draft accepted/edited counts.

Human Correction Rate is a future formal KPI, but V1 must preserve the data needed to derive it.
