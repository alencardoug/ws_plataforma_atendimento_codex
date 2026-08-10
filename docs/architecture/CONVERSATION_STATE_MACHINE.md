# Conversation State Machine — V1

Conversation lifecycle status and AI maturity mode are separate dimensions.

## Lifecycle status

```text
CREATE
  |
  v
WAITING -----------------------> CLOSED
  |
  | operator claim (capacity available)
  v
ACTIVE ------------------------> CLOSED
  |
  | operator release
  v
WAITING
```

Rules:

- customer may send messages while WAITING or ACTIVE unless CLOSED;
- WAITING means not actively assigned, not that the customer is blocked;
- ACTIVE counts against operator capacity;
- CLOSED is terminal in V1;
- releasing an active conversation returns it to WAITING and ends current assignment record.

## Maturity/effective mode

Global N1:

```text
conversation initial=N1, effective=N1
(no upward transition)
```

Global N2:

```text
initial=N2, effective=N2
          |
          | operator Take over
          v
       effective=N1
          |
          | no restore in V1
          v
        close
```

Lifecycle and mode combine independently, e.g. an ACTIVE conversation may be effective N1 or N2.

## Customer messages and assignment

A customer message does not claim/assign a conversation and does not invoke durable async AI processing. It updates `last_message_at` and queue visibility.
