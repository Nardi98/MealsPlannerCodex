"""Add users and ownership

Revision ID: bb1194d1b81e
Revises: 0001_baseline
Create Date: 2025-11-01 12:08:07.325595

"""
from __future__ import annotations

from typing import Iterable

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, table

revision = "bb1194d1b81e"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


UNIT_ENUM = postgresql.ENUM(name="unit_enum", create_type=False)


def _add_user_id_column(table_name: str, default_user_id: int) -> None:
    with op.batch_alter_table(table_name) as batch:
        batch.add_column(
            sa.Column(
                "user_id",
                sa.Integer(),
                nullable=True,
                server_default=sa.text(str(default_user_id)),
            )
        )

    with op.batch_alter_table(table_name) as batch:
        batch.alter_column("user_id", server_default=None)
        batch.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(
            f"fk_{table_name}_user_id_users",
            "users",
            ["user_id"],
            ["id"],
        )


def _drop_unique_constraint(table_name: str, columns: Iterable[str]) -> None:
    inspector = inspect(op.get_bind())
    target = [col.lower() for col in columns]
    for constraint in inspector.get_unique_constraints(table_name):
        if [c.lower() for c in constraint.get("column_names", [])] == target:
            name = constraint.get("name")
            if name:
                with op.batch_alter_table(table_name) as batch:
                    batch.drop_constraint(name, type_="unique")
            break


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("username", sa.String(), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    users_table = table(
        "users",
        column("id", sa.Integer()),
        column("email", sa.String()),
        column("username", sa.String()),
        column("hashed_password", sa.String()),
    )

    legacy_email = "legacy@example.com"
    legacy_username = "legacy"
    legacy_password = "not-set"

    bind.execute(
        users_table.insert().values(
            email=legacy_email,
            username=legacy_username,
            hashed_password=legacy_password,
        )
    )

    default_user_id = bind.execute(
        sa.select(users_table.c.id).where(users_table.c.email == legacy_email)
    ).scalar_one()

    _add_user_id_column("recipes", default_user_id)

    with op.batch_alter_table("recipes") as batch:
        batch.create_unique_constraint("uq_recipes_user_id_id", ["user_id", "id"])
        batch.create_unique_constraint("uq_recipes_user_id_title", ["user_id", "title"])

    _add_user_id_column("ingredients", default_user_id)
    _drop_unique_constraint("ingredients", ["name"])
    with op.batch_alter_table("ingredients") as batch:
        batch.create_unique_constraint("uq_ingredients_user_id_id", ["user_id", "id"])
        batch.create_unique_constraint("uq_ingredients_user_id_name", ["user_id", "name"])

    _add_user_id_column("tags", default_user_id)
    _drop_unique_constraint("tags", ["name"])
    with op.batch_alter_table("tags") as batch:
        batch.create_unique_constraint("uq_tags_user_id_id", ["user_id", "id"])
        batch.create_unique_constraint("uq_tags_user_id_name", ["user_id", "name"])

    meal_side_rows = bind.execute(
        sa.text(
            "SELECT plan_date, meal_number, position, side_recipe_id FROM meal_side_dishes"
        )
    ).fetchall()
    meals_rows = bind.execute(
        sa.text(
            "SELECT plan_date, meal_number, recipe_id, accepted, leftover FROM meals"
        )
    ).fetchall()
    meal_plan_rows = bind.execute(
        sa.text("SELECT plan_date FROM meal_plans")
    ).fetchall()

    op.drop_table("meal_side_dishes")
    op.drop_table("meals")
    op.drop_table("meal_plans")

    op.create_table(
        "meal_plans",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "plan_date"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )

    if meal_plan_rows:
        bind.execute(
            sa.text(
                "INSERT INTO meal_plans (user_id, plan_date) VALUES (:user_id, :plan_date)"
            ),
            [
                {"user_id": default_user_id, "plan_date": row.plan_date}
                for row in meal_plan_rows
            ],
        )

    op.create_table(
        "meals",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("meal_number", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer()),
        sa.Column("accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("leftover", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("user_id", "plan_date", "meal_number"),
        sa.CheckConstraint("meal_number IN (1,2)"),
        sa.ForeignKeyConstraint(
            ["user_id", "plan_date"],
            ["meal_plans.user_id", "meal_plans.plan_date"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id", "recipe_id"], ["recipes.user_id", "recipes.id"]),
    )

    if meals_rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO meals (user_id, plan_date, meal_number, recipe_id, accepted, leftover)
                VALUES (:user_id, :plan_date, :meal_number, :recipe_id, :accepted, :leftover)
                """
            ),
            [
                {
                    "user_id": default_user_id,
                    "plan_date": row.plan_date,
                    "meal_number": row.meal_number,
                    "recipe_id": row.recipe_id,
                    "accepted": row.accepted,
                    "leftover": row.leftover,
                }
                for row in meals_rows
            ],
        )

    op.create_table(
        "meal_side_dishes",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("meal_number", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("side_recipe_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "plan_date", "meal_number", "position"),
        sa.ForeignKeyConstraint(
            ["user_id", "plan_date", "meal_number"],
            ["meals.user_id", "meals.plan_date", "meals.meal_number"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "side_recipe_id"], ["recipes.user_id", "recipes.id"]
        ),
    )

    if meal_side_rows:
        insert_stmt = sa.text(
            """
            INSERT INTO meal_side_dishes (user_id, plan_date, meal_number, position, side_recipe_id)
            VALUES (:user_id, :plan_date, :meal_number, :position, :side_recipe_id)
            """
        )
        params = []
        for row in meal_side_rows:
            user = bind.execute(
                sa.text(
                    "SELECT user_id FROM meals WHERE plan_date = :plan_date AND meal_number = :meal_number"
                ),
                {"plan_date": row.plan_date, "meal_number": row.meal_number},
            ).scalar()
            params.append(
                {
                    "user_id": user if user is not None else default_user_id,
                    "plan_date": row.plan_date,
                    "meal_number": row.meal_number,
                    "position": row.position,
                    "side_recipe_id": row.side_recipe_id,
                }
            )
        if params:
            bind.execute(insert_stmt, params)

    recipe_tag_rows = bind.execute(
        sa.text(
            """
            SELECT rt.recipe_id, rt.tag_id, r.user_id
            FROM recipe_tag AS rt
            JOIN recipes AS r ON rt.recipe_id = r.id
            """
        )
    ).fetchall()
    op.drop_table("recipe_tag")
    op.create_table(
        "recipe_tag",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "recipe_id", "tag_id"),
        sa.ForeignKeyConstraint(
            ["user_id", "recipe_id"], ["recipes.user_id", "recipes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "tag_id"], ["tags.user_id", "tags.id"], ondelete="CASCADE"
        ),
    )
    if recipe_tag_rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO recipe_tag (user_id, recipe_id, tag_id)
                VALUES (:user_id, :recipe_id, :tag_id)
                """
            ),
            [
                {
                    "user_id": row.user_id,
                    "recipe_id": row.recipe_id,
                    "tag_id": row.tag_id,
                }
                for row in recipe_tag_rows
            ],
        )

    recipe_ingredient_rows = bind.execute(
        sa.text(
            """
            SELECT ri.recipe_id, ri.ingredient_id, ri.quantity, ri.unit, r.user_id
            FROM recipe_ingredients AS ri
            JOIN recipes AS r ON ri.recipe_id = r.id
            """
        )
    ).fetchall()
    op.drop_table("recipe_ingredients")
    op.create_table(
        "recipe_ingredients",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Float()),
        sa.Column("unit", UNIT_ENUM),
        sa.PrimaryKeyConstraint("user_id", "recipe_id", "ingredient_id"),
        sa.ForeignKeyConstraint(
            ["user_id", "recipe_id"], ["recipes.user_id", "recipes.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "ingredient_id"],
            ["ingredients.user_id", "ingredients.id"],
            ondelete="CASCADE",
        ),
    )
    if recipe_ingredient_rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO recipe_ingredients (user_id, recipe_id, ingredient_id, quantity, unit)
                VALUES (:user_id, :recipe_id, :ingredient_id, :quantity, :unit)
                """
            ),
            [
                {
                    "user_id": row.user_id,
                    "recipe_id": row.recipe_id,
                    "ingredient_id": row.ingredient_id,
                    "quantity": row.quantity,
                    "unit": row.unit,
                }
                for row in recipe_ingredient_rows
            ],
        )


def downgrade() -> None:
    bind = op.get_bind()

    recipe_ingredient_rows = bind.execute(
        sa.text(
            """
            SELECT user_id, recipe_id, ingredient_id, quantity, unit
            FROM recipe_ingredients
            """
        )
    ).fetchall()
    recipe_tag_rows = bind.execute(
        sa.text(
            "SELECT user_id, recipe_id, tag_id FROM recipe_tag"
        )
    ).fetchall()

    meal_side_rows = bind.execute(
        sa.text(
            """
            SELECT user_id, plan_date, meal_number, position, side_recipe_id
            FROM meal_side_dishes
            """
        )
    ).fetchall()
    meals_rows = bind.execute(
        sa.text(
            """
            SELECT user_id, plan_date, meal_number, recipe_id, accepted, leftover
            FROM meals
            """
        )
    ).fetchall()
    meal_plan_rows = bind.execute(
        sa.text("SELECT user_id, plan_date FROM meal_plans")
    ).fetchall()

    op.drop_table("recipe_ingredients")
    op.drop_table("recipe_tag")
    op.drop_table("meal_side_dishes")
    op.drop_table("meals")
    op.drop_table("meal_plans")

    op.create_table(
        "meal_plans",
        sa.Column("plan_date", sa.Date(), primary_key=True),
    )

    if meal_plan_rows:
        seen_dates = set()
        params = []
        for row in meal_plan_rows:
            if row.plan_date not in seen_dates:
                params.append({"plan_date": row.plan_date})
                seen_dates.add(row.plan_date)
        if params:
            bind.execute(
                sa.text("INSERT INTO meal_plans (plan_date) VALUES (:plan_date)"),
                params,
            )

    op.create_table(
        "meals",
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("meal_number", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer()),
        sa.Column("accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("leftover", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("plan_date", "meal_number"),
        sa.ForeignKeyConstraint(["plan_date"], ["meal_plans.plan_date"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"]),
        sa.CheckConstraint("meal_number IN (1,2)"),
    )

    if meals_rows:
        seen = set()
        params = []
        for row in meals_rows:
            key = (row.plan_date, row.meal_number)
            if key not in seen:
                params.append(
                    {
                        "plan_date": row.plan_date,
                        "meal_number": row.meal_number,
                        "recipe_id": row.recipe_id,
                        "accepted": row.accepted,
                        "leftover": row.leftover,
                    }
                )
                seen.add(key)
        if params:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO meals (plan_date, meal_number, recipe_id, accepted, leftover)
                    VALUES (:plan_date, :meal_number, :recipe_id, :accepted, :leftover)
                    """
                ),
                params,
            )

    op.create_table(
        "meal_side_dishes",
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("meal_number", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("side_recipe_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("plan_date", "meal_number", "position"),
        sa.ForeignKeyConstraint(
            ["plan_date", "meal_number"],
            ["meals.plan_date", "meals.meal_number"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["side_recipe_id"], ["recipes.id"]),
    )

    if meal_side_rows:
        seen = set()
        params = []
        for row in meal_side_rows:
            key = (row.plan_date, row.meal_number, row.position)
            if key not in seen:
                params.append(
                    {
                        "plan_date": row.plan_date,
                        "meal_number": row.meal_number,
                        "position": row.position,
                        "side_recipe_id": row.side_recipe_id,
                    }
                )
                seen.add(key)
        if params:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO meal_side_dishes (plan_date, meal_number, position, side_recipe_id)
                    VALUES (:plan_date, :meal_number, :position, :side_recipe_id)
                    """
                ),
                params,
            )

    op.create_table(
        "recipe_tag",
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("recipe_id", "tag_id"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
    )
    if recipe_tag_rows:
        seen = set()
        params = []
        for row in recipe_tag_rows:
            key = (row.recipe_id, row.tag_id)
            if key not in seen:
                params.append({"recipe_id": row.recipe_id, "tag_id": row.tag_id})
                seen.add(key)
        if params:
            bind.execute(
                sa.text(
                    "INSERT INTO recipe_tag (recipe_id, tag_id) VALUES (:recipe_id, :tag_id)"
                ),
                params,
            )

    op.create_table(
        "recipe_ingredients",
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Float()),
        sa.Column("unit", UNIT_ENUM),
        sa.PrimaryKeyConstraint("recipe_id", "ingredient_id"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"),
    )
    if recipe_ingredient_rows:
        seen = set()
        params = []
        for row in recipe_ingredient_rows:
            key = (row.recipe_id, row.ingredient_id)
            if key not in seen:
                params.append(
                    {
                        "recipe_id": row.recipe_id,
                        "ingredient_id": row.ingredient_id,
                        "quantity": row.quantity,
                        "unit": row.unit,
                    }
                )
                seen.add(key)
        if params:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity, unit)
                    VALUES (:recipe_id, :ingredient_id, :quantity, :unit)
                    """
                ),
                params,
            )

    with op.batch_alter_table("tags") as batch:
        batch.drop_constraint("uq_tags_user_id_id", type_="unique")
        batch.drop_constraint("uq_tags_user_id_name", type_="unique")
        batch.drop_constraint("fk_tags_user_id_users", type_="foreignkey")
        batch.drop_column("user_id")
        batch.create_unique_constraint("tags_name_key", ["name"])

    with op.batch_alter_table("ingredients") as batch:
        batch.drop_constraint("uq_ingredients_user_id_id", type_="unique")
        batch.drop_constraint("uq_ingredients_user_id_name", type_="unique")
        batch.drop_constraint("fk_ingredients_user_id_users", type_="foreignkey")
        batch.drop_column("user_id")
        batch.create_unique_constraint("ingredients_name_key", ["name"])

    with op.batch_alter_table("recipes") as batch:
        batch.drop_constraint("uq_recipes_user_id_id", type_="unique")
        batch.drop_constraint("uq_recipes_user_id_title", type_="unique")
        batch.drop_constraint("fk_recipes_user_id_users", type_="foreignkey")
        batch.drop_column("user_id")

    op.drop_table("users")
