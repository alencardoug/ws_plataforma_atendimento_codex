# Data Model: Customer-Facing Draft Status

No data model impact (spec.md §5, confirmed). `preparing_response` is
computed fresh on every `GET /public/conversations/{id}` from existing
columns (`conversations.status`, `effective_mode`,
`last_customer_activity_at`, `auto_draft_covers_through_message_id`) via
the existing `automatic_draft_status()` function — no new column, table,
index, or migration.

`ConversationOut.preparing_response: bool = False`
(`shared/schemas.py`) is the only schema change — a response field, not a
persisted one.
