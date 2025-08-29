from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "004_add_main_recipe_id"
down_revision = "003_add_course_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "meals",
        sa.Column("main_recipe_id", sa.Integer(), sa.ForeignKey("recipes.id")),
    )


def downgrade() -> None:
    op.drop_column("meals", "main_recipe_id")
