"""V3-5 acceptance outcome 5: evaluation-case isolation from production
conversations/metrics must be structural, not a runtime filter that could
later be forgotten (plan.md §3.3). Verified here by inspecting the
SQLAlchemy mapper metadata directly — no database connection needed, and
no query anywhere could accidentally join across a relationship that does
not exist in the schema."""

from sqlalchemy import inspect

from customer_care.infrastructure.models import AIGeneration, Conversation, EvaluationCase


def foreign_key_target_tables(model: type) -> set[str]:
    mapper = inspect(model)
    return {fk.column.table.name for column in mapper.columns for fk in column.foreign_keys}


def test_evaluation_case_has_no_foreign_key_into_conversations_or_generations() -> None:
    targets = foreign_key_target_tables(EvaluationCase)
    assert "conversations" not in targets
    assert "ai_generations" not in targets


def test_conversations_and_generations_have_no_foreign_key_into_evaluation_cases() -> None:
    assert "evaluation_cases" not in foreign_key_target_tables(Conversation)
    assert "evaluation_cases" not in foreign_key_target_tables(AIGeneration)
