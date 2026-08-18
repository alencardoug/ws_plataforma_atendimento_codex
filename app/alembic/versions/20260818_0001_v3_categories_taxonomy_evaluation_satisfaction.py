"""V3: category registry, operator-feedback taxonomy columns, evaluation
cases, satisfaction responses.

Revision ID: 20260818_0001
Revises: 20260814_0002

See specs/003-v3-measured-n2/{plan,data-model}.md for rationale. The
category registry is backfilled from BOTH content.qa_entries.category and
content.documents.cancer_type (plan.md §3.1, resolved 2026-08-18 after
review — clinical-site categories are not ignored). All new
ai_generations columns are nullable; no backfill required for them.
"""

from alembic import op

revision = "20260818_0001"
down_revision = "20260814_0002"
branch_labels = None
depends_on = None


DDL = r"""
CREATE TABLE IF NOT EXISTS content.categories (
    slug text PRIMARY KEY,
    label text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO content.categories (slug, label)
SELECT DISTINCT category, category FROM content.qa_entries WHERE category IS NOT NULL
UNION
SELECT DISTINCT cancer_type, cancer_type FROM content.documents WHERE cancer_type IS NOT NULL
ON CONFLICT DO NOTHING;

ALTER TABLE content.qa_entries
    ADD CONSTRAINT qa_entries_category_fkey
        FOREIGN KEY (category) REFERENCES content.categories(slug);

ALTER TABLE content.documents
    ADD CONSTRAINT documents_cancer_type_fkey
        FOREIGN KEY (cancer_type) REFERENCES content.categories(slug);

ALTER TABLE customer_service.ai_generations
    ADD COLUMN IF NOT EXISTS instruction_text text,
    ADD COLUMN IF NOT EXISTS category_slug text REFERENCES content.categories(slug),
    ADD COLUMN IF NOT EXISTS marked_incorrect_at timestamptz,
    ADD COLUMN IF NOT EXISTS marked_incorrect_by_operator_id uuid REFERENCES customer_service.operator_users(id),
    ADD COLUMN IF NOT EXISTS escalated_at timestamptz,
    ADD COLUMN IF NOT EXISTS escalated_by_operator_id uuid REFERENCES customer_service.operator_users(id);

CREATE TABLE IF NOT EXISTS content.evaluation_cases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category_slug text REFERENCES content.categories(slug),
    question text NOT NULL,
    expected_status text NOT NULL CHECK (expected_status IN ('ANSWER', 'ABSTAIN')),
    expected_evidence_ids jsonb,
    actual_status text CHECK (actual_status IN ('ANSWER', 'ABSTAIN')),
    actual_notes text,
    last_reviewed_at timestamptz,
    created_by_operator_id uuid NOT NULL REFERENCES customer_service.operator_users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS customer_service.conversation_satisfaction_responses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL UNIQUE REFERENCES customer_service.conversations(id),
    score smallint NOT NULL CHECK (score BETWEEN 1 AND 5),
    resolved boolean NOT NULL,
    category_slug text REFERENCES content.categories(slug),
    submitted_at timestamptz NOT NULL DEFAULT now()
);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V3 migrations are forward-only, consistent with the V1/V2 baseline")
