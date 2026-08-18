"""T111: proves docs/metrics/v3_queries.sql's HCR query agrees with
classify_generation()'s Python logic against the same live data — not a
fixture, the actual accumulated ai_generations/audit_events rows in
whatever database DATABASE_URL points at. Needs a live populated database
(same class of requirement as the other smoke_*.py scripts, hence this
naming — python_files=["test_*.py"] in pyproject.toml deliberately does
not collect it into the DB-free fast pytest suite); run manually:

    PYTHONPATH=. python tests/smoke_v3_metrics_agreement.py
"""

from collections import defaultdict

from sqlalchemy import select, text

from customer_care.ai.router import classify_generation
from customer_care.infrastructure.database import get_session_factory
from customer_care.infrastructure.models import AIGeneration


def run() -> None:
    session = get_session_factory()()
    try:
        # Python side: classify_generation() per generation, tallied by category.
        python_counts: dict[str | None, dict[str, int]] = defaultdict(lambda: {"approve": 0, "edit": 0})
        for generation in session.scalars(select(AIGeneration)).all():
            tags = classify_generation(session, generation)
            if "approve" in tags:
                python_counts[generation.category_slug]["approve"] += 1
            if "edit" in tags:
                python_counts[generation.category_slug]["edit"] += 1

        # SQL side: the same aggregation docs/metrics/v3_queries.sql's HCR
        # query performs (category-level only, no ROLLUP row here).
        sql_rows = session.execute(
            text(
                """
                SELECT
                    g.category_slug,
                    COUNT(*) FILTER (WHERE a.event_type = 'ai.draft_accepted') AS approve_count,
                    COUNT(*) FILTER (WHERE a.event_type = 'ai.draft_edited') AS edit_count
                FROM customer_service.audit_events a
                JOIN customer_service.ai_generations g
                  ON a.payload_json->>'ai_generation_id' = g.id::text
                WHERE a.event_type IN ('ai.draft_edited', 'ai.draft_accepted')
                GROUP BY g.category_slug
                """
            )
        ).all()
        sql_counts = {row.category_slug: {"approve": row.approve_count, "edit": row.edit_count} for row in sql_rows}

        categories = set(python_counts.keys()) | set(sql_counts.keys())
        mismatches = []
        for category in categories:
            python_side = python_counts.get(category, {"approve": 0, "edit": 0})
            sql_side = sql_counts.get(category, {"approve": 0, "edit": 0})
            if python_side != sql_side:
                mismatches.append((category, python_side, sql_side))

        if mismatches:
            for category, python_side, sql_side in mismatches:
                print(f"MISMATCH category={category!r}: classify_generation()={python_side} vs SQL={sql_side}")
            raise AssertionError(f"{len(mismatches)} category/categories disagree between classify_generation() and the documented SQL")

        print(f"metrics_agreement_ok: {len(categories)} categories checked, classify_generation() and docs/metrics/v3_queries.sql's HCR query agree exactly")
    finally:
        session.close()


if __name__ == "__main__":
    run()
