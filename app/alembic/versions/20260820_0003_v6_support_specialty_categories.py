"""V6 (006/SC): new content.categories rows for the three newly-covered
support specialties.

Revision ID: 20260820_0003
Revises: 20260820_0002

No existing category fits nutrição/endocrinologia/fisioterapia oncológica
— `apoio_emocional` is the closest and covers psico-oncologia only.
Additive, matches `20260818_0001`'s own `INSERT ... ON CONFLICT DO
NOTHING` shape. See specs/006-specialty-scheduling-breadth/plan.md §2,
data-model.md §1.
"""

from alembic import op

revision = "20260820_0003"
down_revision = "20260820_0002"
branch_labels = None
depends_on = None


DDL = r"""
INSERT INTO content.categories (slug, label) VALUES
    ('nutricao_oncologica', 'Nutrição oncológica'),
    ('endocrinologia_oncologica', 'Endocrinologia oncológica'),
    ('fisioterapia_oncologica', 'Fisioterapia oncológica')
ON CONFLICT DO NOTHING;
"""


def upgrade() -> None:
    op.execute(DDL)


def downgrade() -> None:
    raise RuntimeError("V6 migrations are forward-only, consistent with the V1-V7 baseline")
