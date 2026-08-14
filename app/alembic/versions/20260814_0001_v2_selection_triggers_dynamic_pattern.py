"""V2: message selections, generation triggers, dynamic-pattern bindings.

Revision ID: 20260814_0001
Revises: 20260810_0001

See specs/002-v2-commercial-product-experience/{plan,data-model}.md for
rationale. All new columns are nullable/defaulted; no backfill required.
"""

from alembic import op

revision = "20260814_0001"
down_revision = "20260810_0001"
branch_labels = None
depends_on = None


DDL = r"""
ALTER TABLE customer_service.conversations
    ADD COLUMN IF NOT EXISTS last_customer_activity_at timestamptz,
    ADD COLUMN IF NOT EXISTS last_customer_typing_at timestamptz,
    ADD COLUMN IF NOT EXISTS auto_draft_covers_through_message_id uuid
        REFERENCES customer_service.messages(id);

ALTER TABLE customer_service.ai_generations
    ALTER COLUMN triggering_message_id DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS trigger text NOT NULL DEFAULT 'MANUAL_DRAFT'
        CHECK (trigger IN ('AUTOMATIC', 'MANUAL_DRAFT', 'MANUAL_EVIDENCE')),
    ADD COLUMN IF NOT EXISTS manual_search_text text,
    ADD COLUMN IF NOT EXISTS dynamic_pattern_used boolean NOT NULL DEFAULT false;
ALTER TABLE customer_service.ai_generations ALTER COLUMN trigger DROP DEFAULT;

CREATE TABLE IF NOT EXISTS customer_service.message_selections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ai_generation_id uuid NOT NULL REFERENCES customer_service.ai_generations(id),
    message_id uuid NOT NULL REFERENCES customer_service.messages(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (ai_generation_id, message_id)
);

CREATE TABLE IF NOT EXISTS content.qa_dynamic_bindings (
    qa_id text PRIMARY KEY REFERENCES content.qa_entries(qa_id),
    source_table text NOT NULL,
    filter jsonb NOT NULL DEFAULT '{}'::jsonb,
    output_columns jsonb NOT NULL,
    row_limit integer NOT NULL DEFAULT 4 CHECK (row_limit > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V2 migrations are forward-only, consistent with the V1 baseline")
