# Channel Abstraction

V1 implements web only. Future Telegram must reuse the same conversation engine.

## Normalized inbound message

Conceptually:

```text
channel
external_message_id? 
conversation_locator
sender_kind
text
received_at
```

Web adapter maps the per-tab anonymous conversation token to the internal conversation.

A future Telegram adapter will map Telegram chat/user/message identifiers into the same application commands.

## Normalized outbound message

Application service produces a customer-visible `Message` only after V1 operator send. Channel adapter renders/delivers it.

Do not put Telegram/Web branching into RAG, AI, or conversation domain services.
