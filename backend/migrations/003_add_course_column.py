from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "003_add_course_column"
down_revision = "002_recipe_ingredients_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column("course", sa.String(), nullable=False, server_default="main"),
    )


def downgrade() -> None:
    op.drop_column("recipes", "course")
