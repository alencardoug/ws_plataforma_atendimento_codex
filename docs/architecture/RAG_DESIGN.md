# RAG Design — V1

## Purpose

Produce operator-visible evidence and, in N2, a grounded AI draft. RAG has no authority to send customer messages.

## Query context

Inputs:

- latest customer question/message;
- active conversation history, bounded to a practical token budget;
- current effective mode;
- retrieval configuration.

No cross-session customer memory exists in V1.

## Retrieval families

### Administrative Q&A

Search over flat Q&A vector records.

Hit returns:

- answer grounding text;
- question/source label;
- score/distance;
- internal source metadata;
- `customer_citation_allowed=false`.

### Clinical parent-child

Search over child embeddings.

For selected children:

1. resolve parent;
2. group/dedupe by parent;
3. include child match metadata for traceability;
4. send parent context to generation;
5. expose approved parent citation projection to operator/customer when final message includes allowed citations.

## Mixed retrieval

V1 may query both families in one retrieval run and rank/limit results. Do not implement a complex learned router unless tests show it is needed. Preserve `knowledge_type` metadata so results remain explainable.

## Grounding contract

Generation receives clearly delimited evidence objects with stable source IDs. Prompt instructs model to:

- answer only from supplied evidence and conversation context;
- distinguish missing information from supported information;
- abstain if evidence is insufficient or conflicting;
- avoid inventing hospital-specific facts;
- produce concise customer-service language;
- avoid diagnosis/treatment decisions;
- keep clinical guidance within approved informational framing.

## Abstention

Abstention is a structured generation outcome, not only prose.

Suggested result fields:

- `status = ANSWER | ABSTAIN`
- `draft_text`
- `reason_code`
- `used_source_ids[]`

V1 reason codes may include:

- `INSUFFICIENT_EVIDENCE`
- `CONFLICTING_EVIDENCE`
- `OUT_OF_SCOPE`
- `RETRIEVAL_FAILURE`

For abstention, the draft should help the operator respond manually. No automatic specialist escalation exists in V1.

## Citations

Operator sees all retrieval evidence.

Customer-visible citation projection is derived from `used_source_ids` and server-side exposure policy. AI text cannot elevate a non-exposable source into a customer citation.

## Retrieval persistence

Each run stores:

- query text or controlled reference to triggering message;
- timestamps/latency;
- configuration/top-k;
- hit IDs/scores/rank;
- parent expansion relationships;
- outcome/error.

This enables later evaluation without storing chain-of-thought.
