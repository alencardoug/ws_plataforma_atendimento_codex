"""V2-6 dynamic-evidence safety correction.

Resolves a Q&A entry's `{{variable_name}}` pattern by querying a structured
table, using only a server-side allowlist for table/column identifiers —
never a raw string from the database or a request. See plan.md §9.

The allowlist below is intentionally empty of any production data source.
`DynamicFixtureRow` exists solely to let this mechanism be exercised against
a real table in tests; no production Q&A entry is bound to it. A real
dynamic-data source is added here only when a specific future feature (e.g.
dynamic appointment availability) is separately authorized (spec.md §6).
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from customer_care.infrastructure.models import Base, DynamicFixtureRow, QADynamicBinding, QAEntry

# table name -> (SQLAlchemy model, column used for stable ordering)
ALLOWLISTED_TABLES: dict[str, tuple[type[Base], str]] = {
    "knowledge_dynamic_fixture": (DynamicFixtureRow, "ordinal"),
}


class DynamicResolutionError(Exception):
    """Carries an audit-only diagnostic cause. Never expose `.cause` to a customer."""

    def __init__(self, cause: str):
        self.cause = cause
        super().__init__(cause)


@dataclass(frozen=True)
class DynamicResolution:
    pattern_text: str
    # Populated only by scheduling/availability.py's NAMED_RESOLVERS entry
    # (plan.md §7) — always None for this module's own generic
    # qa_dynamic_bindings path.
    specialty_slug: str | None = None
    slot_count: int | None = None


def resolve_dynamic_pattern(session: Session, qa: QAEntry) -> DynamicResolution:
    binding = session.get(QADynamicBinding, qa.qa_id)
    if not binding:
        raise DynamicResolutionError(f"no dynamic binding configured for qa_id={qa.qa_id}")
    allowlisted = ALLOWLISTED_TABLES.get(binding.source_table)
    if not allowlisted:
        raise DynamicResolutionError(f"source_table '{binding.source_table}' is not in the allowlist")
    model, order_column = allowlisted
    output_columns: list[dict[str, str]] = binding.output_columns
    for spec in output_columns:
        if not hasattr(model, spec["column"]):
            raise DynamicResolutionError(f"column '{spec['column']}' not found in table '{binding.source_table}'")
    for key in binding.filter:
        if not hasattr(model, key):
            raise DynamicResolutionError(f"filter column '{key}' not found in table '{binding.source_table}'")
    query = select(model)
    for key, value in binding.filter.items():
        query = query.where(getattr(model, key) == value)
    query = query.order_by(getattr(model, order_column)).limit(binding.row_limit)
    try:
        rows = session.scalars(query).all()
    except Exception as exc:
        raise DynamicResolutionError(f"query failed: {type(exc).__name__}") from exc
    if not rows:
        raise DynamicResolutionError("no row matched filter")
    rendered_rows = []
    for row in rows:
        values: dict[str, Any] = {spec["variable_name"]: getattr(row, spec["column"]) for spec in output_columns}
        rendered = qa.answer_markdown
        for name, value in values.items():
            rendered = rendered.replace("{{" + name + "}}", str(value))
        rendered_rows.append(rendered)
    # Multi-row rendering (tasks.md T073): join with a blank line, each row
    # rendered against the same pattern template.
    return DynamicResolution("\n\n".join(rendered_rows))
