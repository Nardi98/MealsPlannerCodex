"""Baseline schema for Meals Planner Codex."""
from __future__ import annotations

import re
from calendar import month_abbr, month_name
from typing import Iterable

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


UNIT_ENUM = sa.Enum("g", "kg", "l", "ml", "piece", name="unit_enum")


def _create_table_if_missing(name: str, columns: Iterable[sa.Column], *constraints) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(name):
        return False
    op.create_table(name, *columns, *constraints)
    return True


def _ensure_unit_enum() -> None:
    bind = op.get_bind()
    UNIT_ENUM.create(bind, checkfirst=True)


def _ensure_recipes_table() -> None:
    _create_table_if_missing(
        "recipes",
        (
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("servings_default", sa.Integer(), nullable=False),
            sa.Column("procedure", sa.Text()),
            sa.Column("bulk_prep", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("score", sa.Float()),
            sa.Column("date_last_consumed", sa.Date()),
            sa.Column("course", sa.String(), nullable=False, server_default="main"),
        ),
    )


def _ensure_tags_table() -> None:
    _create_table_if_missing(
        "tags",
        (
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False, unique=True),
        ),
    )


def _ensure_ingredients_table() -> None:
    _create_table_if_missing(
        "ingredients",
        (
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False, unique=True),
            sa.Column("season_months", sa.String()),
            sa.Column("unit", UNIT_ENUM),
        ),
    )


def _ensure_recipe_tag_table() -> None:
    _create_table_if_missing(
        "recipe_tag",
        (
            sa.Column("recipe_id", sa.Integer(), nullable=False),
            sa.Column("tag_id", sa.Integer(), nullable=False),
        ),
        sa.PrimaryKeyConstraint("recipe_id", "tag_id"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
    )


def _ensure_recipe_ingredients_table() -> None:
    _create_table_if_missing(
        "recipe_ingredients",
        (
            sa.Column("recipe_id", sa.Integer(), nullable=False),
            sa.Column("ingredient_id", sa.Integer(), nullable=False),
            sa.Column("quantity", sa.Float()),
            sa.Column("unit", UNIT_ENUM),
        ),
        sa.PrimaryKeyConstraint("recipe_id", "ingredient_id"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"),
    )


def _ensure_meal_plans_table() -> None:
    _create_table_if_missing(
        "meal_plans",
        (
            sa.Column("plan_date", sa.Date(), primary_key=True),
        ),
    )


def _ensure_meals_table() -> None:
    created = _create_table_if_missing(
        "meals",
        (
            sa.Column("plan_date", sa.Date(), nullable=False),
            sa.Column("meal_number", sa.Integer(), nullable=False),
            sa.Column("recipe_id", sa.Integer()),
            sa.Column("accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("leftover", sa.Boolean(), nullable=False, server_default=sa.false()),
        ),
        sa.PrimaryKeyConstraint("plan_date", "meal_number"),
        sa.ForeignKeyConstraint(["plan_date"], ["meal_plans.plan_date"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"]),
        sa.CheckConstraint("meal_number IN (1,2)"),
    )
    if created and op.get_bind().dialect.name != "sqlite":
        op.alter_column("meals", "accepted", server_default=None)
        op.alter_column("meals", "leftover", server_default=None)


def _ensure_meal_side_dishes_table() -> None:
    _create_table_if_missing(
        "meal_side_dishes",
        (
            sa.Column("plan_date", sa.Date(), nullable=False),
            sa.Column("meal_number", sa.Integer(), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("side_recipe_id", sa.Integer(), nullable=False),
        ),
        sa.PrimaryKeyConstraint("plan_date", "meal_number", "position"),
        sa.ForeignKeyConstraint(
            ["plan_date", "meal_number"],
            ["meals.plan_date", "meals.meal_number"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["side_recipe_id"], ["recipes.id"]),
    )


def _convert_ingredient_season_months() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ingredients" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("ingredients")}
    if "season_months" not in columns:
        return

    month_map = {name.lower(): i for i, name in enumerate(month_name) if name}
    month_map.update({abbr.lower(): i for i, abbr in enumerate(month_abbr) if abbr})

    results = bind.execute(text("SELECT id, season_months FROM ingredients")).fetchall()
    for ingredient_id, raw in results:
        if not raw:
            cleaned = None
        else:
            tokens = re.split(r"[^A-Za-z0-9]+", raw.lower())
            months = []
            for token in tokens:
                if token.isdigit():
                    value = int(token)
                    if 1 <= value <= 12:
                        months.append(value)
                elif token in month_map:
                    months.append(month_map[token])
            cleaned = ",".join(str(m) for m in sorted(set(months))) if months else None
        bind.execute(
            text("UPDATE ingredients SET season_months = :val WHERE id = :id"),
            {"val": cleaned, "id": ingredient_id},
        )


def _migrate_recipe_ingredients() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "ingredients" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("ingredients")}
    legacy_cols = {"recipe_id", "quantity", "unit"}
    if not legacy_cols.issubset(columns):
        return

    rows = bind.execute(
        text(
            "SELECT id AS ingredient_id, recipe_id, quantity, unit FROM ingredients "
            "WHERE recipe_id IS NOT NULL"
        )
    ).fetchall()
    if rows:
        bind.execute(
            text(
                "INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity, unit) "
                "VALUES (:recipe_id, :ingredient_id, :quantity, :unit)"
            ),
            rows,
        )

    with op.batch_alter_table("ingredients") as batch:
        if "recipe_id" in columns:
            batch.drop_column("recipe_id")
        if "quantity" in columns:
            batch.drop_column("quantity")
        if "unit" in columns:
            batch.drop_column("unit")


def _ensure_recipe_course() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "recipes" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("recipes")}
    if "course" in columns:
        return
    op.add_column(
        "recipes",
        sa.Column("course", sa.String(), nullable=False, server_default="main"),
    )
    bind.execute(text("UPDATE recipes SET course = 'main' WHERE course IS NULL"))


def _populate_meal_side_dishes() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "meals" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("meals")}
    if "side_recipe_id" not in columns:
        return

    results = bind.execute(
        text(
            "SELECT plan_date, meal_number, side_recipe_id FROM meals "
            "WHERE side_recipe_id IS NOT NULL"
        )
    ).fetchall()
    if results:
        bind.execute(
            text(
                "INSERT INTO meal_side_dishes (plan_date, meal_number, position, side_recipe_id) "
                "VALUES (:plan_date, :meal_number, 1, :side_recipe_id)"
            ),
            results,
        )

    fks = sa.inspect(bind).get_foreign_keys("meals")
    for fk in fks:
        if fk["referred_table"] == "recipes" and fk["constrained_columns"] == ["side_recipe_id"]:
            if fk["name"]:
                op.drop_constraint(fk["name"], "meals", type_="foreignkey")
            break
    with op.batch_alter_table("meals") as batch:
        batch.drop_column("side_recipe_id")


def _ensure_meals_leftover() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "meals" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("meals")}
    if "leftover" in columns:
        return
    op.add_column(
        "meals",
        sa.Column("leftover", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("meals", "leftover", server_default=None)


def upgrade() -> None:
    _ensure_unit_enum()
    _ensure_recipes_table()
    _ensure_tags_table()
    _ensure_ingredients_table()
    _ensure_recipe_tag_table()
    _ensure_recipe_ingredients_table()
    _ensure_meal_plans_table()
    _ensure_meals_table()
    _ensure_meal_side_dishes_table()

    _convert_ingredient_season_months()
    _migrate_recipe_ingredients()
    _ensure_recipe_course()
    _populate_meal_side_dishes()
    _ensure_meals_leftover()


def downgrade() -> None:
    op.drop_table("meal_side_dishes")
    op.drop_table("recipe_ingredients")
    op.drop_table("recipe_tag")
    op.drop_table("meals")
    op.drop_table("meal_plans")
    op.drop_table("ingredients")
    op.drop_table("tags")
    op.drop_table("recipes")
    UNIT_ENUM.drop(op.get_bind(), checkfirst=True)
