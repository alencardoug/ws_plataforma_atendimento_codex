# Citation Exposure Policy

## Operator

Operator may inspect all retrieved evidence necessary to validate a draft.

## Customer

Customer receives only citations attached to the final operator message and only when the referenced knowledge record has `customer_citation_allowed=true`.

Defaults:

- administrative Q&A: false;
- clinical parent/source reference: true.

The customer citation projection should prefer safe fields such as:

- title;
- section/path;
- source label;
- approved public URL if explicitly available/approved.

Do not expose internal database IDs, storage paths, ranking scores, hidden notes, or internal-only document URLs.
