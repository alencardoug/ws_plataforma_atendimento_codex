# Sequence Flows — V1

## 1. Anonymous create/send

```text
Customer tab -> Web API: POST /public/conversations
Web API -> DB: create WAITING conversation + token digest
DB --> Web API
Web API --> Customer tab: conversation_id + raw token (once)
Customer tab -> sessionStorage: store raw token
Customer tab -> Web API: POST message + token
Web API -> DB: validate token digest/binding + persist customer Message + audit
Web API --> Customer tab: message accepted
```

No LLM call is required in this sequence.

## 2. Claim

```text
Operator -> API: claim conversation
API -> DB transaction: lock/check active count
alt count < 4 and conversation WAITING
  DB: create active assignment; status=ACTIVE
  API: audit conversation.claimed
  API --> Operator: success
else capacity/no longer waiting
  API --> Operator: 409
end
```

## 3. N2 draft

```text
Operator -> API: generate draft(triggering customer message)
API: verify assigned + ACTIVE + effective_mode=N2
API -> RAG: retrieve
RAG -> pgvector: query ADMIN_QA + CLINICAL CHILD
pgvector --> RAG: hits
RAG -> DB: persist RetrievalRun/Hits + parent expansion provenance
RAG --> AI service: conversation context + grounded evidence
AI service -> provider: structured generation
provider --> AI service: ANSWER or ABSTAIN
AI service -> DB: persist AIGeneration + sources
API --> Operator: internal draft + evidence
```

Customer receives nothing.

## 4. Explicit operator send

```text
Operator -> API: send final text + optional generation + selected citations
API: verify assignment/authorization
API: validate citation exposure server-side
API -> DB transaction:
  create OPERATOR Message
  create safe MessageCitation snapshots
  audit accepted/edited + message.operator_sent
DB --> API
API --> Operator: final message
Customer -> API: poll/read conversation
API --> Customer: customer-safe final message + approved citations
```

## 5. Take over

```text
Operator -> API: Take over
API: verify assigned + effective N2
DB: effective_mode=N1; taken_over_at=now
DB: audit conversation.taken_over
API --> Operator: effective N1

subsequent draft request -> 409 MODE_NOT_ALLOWED
manual operator send -> allowed
```
