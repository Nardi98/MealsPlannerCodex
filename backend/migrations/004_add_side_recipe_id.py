from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "004_add_side_recipe_id"
down_revision = "003_add_course_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("meals", sa.Column("side_recipe_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_meals_side_recipe_id_recipes",
        "meals",
        "recipes",
        ["side_recipe_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_meals_side_recipe_id_recipes", "meals", type_="foreignkey")
    op.drop_column("meals", "side_recipe_id")
