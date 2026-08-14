"""V2-6: mechanism-demonstration fixture table for the dynamic-pattern resolver.

Revision ID: 20260814_0002
Revises: 20260814_0001

Not a production dynamic-data source. See DynamicFixtureRow's docstring in
customer_care/infrastructure/models.py and
specs/002-v2-commercial-product-experience/plan.md §9.2.
"""

from alembic import op

revision = "20260814_0002"
down_revision = "20260814_0001"
branch_labels = None
depends_on = None


DDL = r"""
CREATE TABLE IF NOT EXISTS content.knowledge_dynamic_fixture (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category text NOT NULL,
    status text NOT NULL,
    label text NOT NULL,
    ordinal integer NOT NULL
);
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V2 migrations are forward-only, consistent with the V1 baseline")
