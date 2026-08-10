# RBAC / Access Matrix — V1

| Capability | Anonymous customer | Operator |
|---|---:|---:|
| Create anonymous conversation | yes | no |
| Read own token-bound conversation | yes | yes (assigned/authorized workspace) |
| Send customer message | yes | no |
| See internal AI draft | no | yes |
| See all retrieval evidence | no | yes |
| See approved clinical citation projection attached to final message | yes | yes |
| Claim waiting conversation | no | yes |
| Send final operator message | no | yes |
| Generate/regenerate N2 draft | no | yes |
| Manual knowledge search | no | yes if enabled/allowed |
| Take over N2 -> N1 | no | yes |
| Read audit events | no | not required by V1 UI; backend/admin diagnostics only |
| Change global maturity mode | no | no V1 UI |
| Ingest knowledge | no | offline administrative command only |
