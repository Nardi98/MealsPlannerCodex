from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "005_meal_side_dishes"
down_revision = "004_add_side_recipe_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meal_side_dishes",
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("meal_number", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("side_recipe_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_date", "meal_number"],
            ["meals.plan_date", "meals.meal_number"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["side_recipe_id"], ["recipes.id"]),
        sa.PrimaryKeyConstraint("plan_date", "meal_number", "position"),
    )
    connection = op.get_bind()
    meals = sa.table(
        "meals",
        sa.column("plan_date", sa.Date()),
        sa.column("meal_number", sa.Integer()),
        sa.column("side_recipe_id", sa.Integer()),
    )
    meal_sides = sa.table(
        "meal_side_dishes",
        sa.column("plan_date", sa.Date()),
        sa.column("meal_number", sa.Integer()),
        sa.column("position", sa.Integer()),
        sa.column("side_recipe_id", sa.Integer()),
    )
    results = connection.execute(
        sa.select(
            meals.c.plan_date, meals.c.meal_number, meals.c.side_recipe_id
        ).where(meals.c.side_recipe_id.is_not(None))
    )
    for plan_date, meal_number, side_recipe_id in results:
        connection.execute(
            meal_sides.insert().values(
                plan_date=plan_date,
                meal_number=meal_number,
                position=1,
                side_recipe_id=side_recipe_id,
            )
        )
    op.drop_column("meals", "side_recipe_id")


def downgrade() -> None:
    op.add_column(
        "meals", sa.Column("side_recipe_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_meals_side_recipe_id_recipes",
        "meals",
        "recipes",
        ["side_recipe_id"],
        ["id"],
    )
    connection = op.get_bind()
    meals = sa.table(
        "meals",
        sa.column("plan_date", sa.Date()),
        sa.column("meal_number", sa.Integer()),
        sa.column("side_recipe_id", sa.Integer()),
    )
    meal_sides = sa.table(
        "meal_side_dishes",
        sa.column("plan_date", sa.Date()),
        sa.column("meal_number", sa.Integer()),
        sa.column("position", sa.Integer()),
        sa.column("side_recipe_id", sa.Integer()),
    )
    results = connection.execute(
        sa.select(
            meal_sides.c.plan_date,
            meal_sides.c.meal_number,
            meal_sides.c.side_recipe_id,
        ).where(meal_sides.c.position == 1)
    )
    for plan_date, meal_number, side_recipe_id in results:
        connection.execute(
            meals.update()
            .where(
                (meals.c.plan_date == plan_date)
                & (meals.c.meal_number == meal_number)
            )
            .values(side_recipe_id=side_recipe_id)
        )
    op.drop_table("meal_side_dishes")
