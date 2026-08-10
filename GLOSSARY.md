# Glossary

- **N1**: manual service. AI may be absent or operator-invoked search-only.
- **N2**: copilot. AI generates internal grounded drafts; operator sends final message.
- **N3**: future category-governed autonomy with HITL for disabled/review categories.
- **N4**: future supervised autonomy/HOTL with veto window and fail-safe downgrade.
- **HITL**: human-in-the-loop; workflow blocks pending human action.
- **HOTL**: human-on-the-loop; system operates autonomously inside policy while human supervises/intervenes.
- **Take over**: V1 operator action reducing a conversation from effective N2 to N1.
- **AI draft**: internal generation artifact; never a customer message by itself.
- **Final message**: customer-visible message created only by explicit operator send in V1.
- **Administrative Q&A**: flat knowledge record with no parent-child hierarchy.
- **Clinical parent-child**: child chunks are retrieved; parent supplies broader generation/source context.
- **Abstention**: AI explicitly indicates evidence is insufficient to answer safely/groundedly.
- **Audit event**: immutable record of an operational fact; not an event-sourcing command log.
- **Anonymous conversation token**: opaque per-tab credential that grants access to one V1 customer conversation.
