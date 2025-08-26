from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "004_add_side_dishes_table"
down_revision = "003_add_course_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meal_side_dishes",
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("meal_number", sa.Integer(), nullable=False),
        sa.Column("side_number", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), sa.ForeignKey("recipes.id"), nullable=False),
        sa.PrimaryKeyConstraint("plan_date", "meal_number", "side_number"),
        sa.ForeignKeyConstraint(
            ["plan_date", "meal_number"],
            ["meals.plan_date", "meals.meal_number"],
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    op.drop_table("meal_side_dishes")
