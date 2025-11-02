"""Add user ownership to existing domain tables."""
from __future__ import annotations

from typing import Iterable, Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.sql import column, table

revision = "1f2760d87a15"
down_revision = "bb1194d1b81e"
branch_labels = None
depends_on = None

ADMIN_EMAIL = "admin@example.com"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "not-set"

USERS_TABLE = table(
    "users",
    column("id", sa.Integer()),
    column("email", sa.String()),
    column("username", sa.String()),
    column("hashed_password", sa.String()),
)

UNIT_ENUM = sa.Enum(
    "g",
    "kg",
    "l",
    "ml",
    "piece",
    name="unit_enum",
    create_type=False,
)


def _ensure_admin_user(connection: sa.engine.Connection) -> int:
    existing = connection.execute(
        sa.select(USERS_TABLE.c.id).where(USERS_TABLE.c.email == ADMIN_EMAIL)
    ).scalar_one_or_none()
    if existing is not None:
        return int(existing)

    connection.execute(
        USERS_TABLE.insert().values(
            email=ADMIN_EMAIL,
            username=ADMIN_USERNAME,
            hashed_password=ADMIN_PASSWORD,
        )
    )
    new_id = connection.execute(
        sa.select(USERS_TABLE.c.id).where(USERS_TABLE.c.email == ADMIN_EMAIL)
    ).scalar_one()
    return int(new_id)


def _get_inspector() -> Inspector:
    return inspect(op.get_bind())


def _drop_unique_constraint(table_name: str, columns: Sequence[str]) -> None:
    inspector = _get_inspector()
    target = [col.lower() for col in columns]
    for constraint in inspector.get_unique_constraints(table_name):
        existing = [col.lower() for col in constraint.get("column_names", [])]
        if existing == target:
            name = constraint.get("name")
            if name:
                with op.batch_alter_table(table_name) as batch:
                    batch.drop_constraint(name, type_="unique")
            break


def _has_index(table_name: str, columns: Sequence[str]) -> bool:
    inspector = _get_inspector()
    target = [col.lower() for col in columns]
    for index in inspector.get_indexes(table_name):
        existing = [col.lower() for col in index.get("column_names", [])]
        if existing == target:
            return True
    return False


def _has_unique_constraint(table_name: str, columns: Sequence[str]) -> bool:
    inspector = _get_inspector()
    target = [col.lower() for col in columns]
    for constraint in inspector.get_unique_constraints(table_name):
        existing = [col.lower() for col in constraint.get("column_names", [])]
        if existing == target:
            return True
    return False


def _has_foreign_key(
    table_name: str,
    columns: Sequence[str],
    referred_table: str,
    referred_columns: Sequence[str],
) -> bool:
    inspector = _get_inspector()
    target_local = [col.lower() for col in columns]
    target_remote = [col.lower() for col in referred_columns]
    for fk in inspector.get_foreign_keys(table_name):
        local_cols = [col.lower() for col in fk.get("constrained_columns", [])]
        remote_cols = [col.lower() for col in fk.get("referred_columns", [])]
        if (
            local_cols == target_local
            and remote_cols == target_remote
            and fk.get("referred_table", "").lower() == referred_table.lower()
        ):
            return True
    return False


def _add_user_id_column(
    table_name: str,
    default_user_id: int,
    *,
    unique_constraints: Iterable[tuple[str, Sequence[str]]] = (),
    drop_uniques: Iterable[Sequence[str]] = (),
    index_columns: Iterable[tuple[str, Sequence[str]]] = (),
) -> None:
    bind = op.get_bind()
    inspector = _get_inspector()
    existing_columns = {col["name"].lower() for col in inspector.get_columns(table_name)}
    dialect = bind.dialect.name

    for columns in drop_uniques:
        _drop_unique_constraint(table_name, columns)

    if "user_id" not in existing_columns:
        with op.batch_alter_table(table_name) as batch:
            batch.add_column(
                sa.Column(
                    "user_id",
                    sa.Integer(),
                    nullable=True,
                    server_default=sa.text(str(default_user_id)),
                )
            )
    else:
        if dialect != "sqlite":
            bind.execute(
                sa.text(
                    f"ALTER TABLE {table_name} ALTER COLUMN user_id SET DEFAULT :default"
                ).bindparams(default=default_user_id)
            )

    bind.execute(
        sa.text(
            f"UPDATE {table_name} SET user_id = :user_id WHERE user_id IS NULL"
        ).bindparams(user_id=default_user_id)
    )

    with op.batch_alter_table(table_name) as batch:
        batch.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("user_id", server_default=None)
        if not _has_foreign_key(table_name, ["user_id"], "users", ["id"]):
            batch.create_foreign_key(
                f"fk_{table_name}_user_id_users",
                "users",
                ["user_id"],
                ["id"],
            )
        for name, columns in unique_constraints:
            if not _has_unique_constraint(table_name, columns):
                batch.create_unique_constraint(name, list(columns))

    for name, columns in index_columns:
        if not _has_index(table_name, columns):
            op.create_index(name, table_name, list(columns))

    if "user_id" in existing_columns and dialect != "sqlite":
        bind.execute(
            sa.text(
                f"ALTER TABLE {table_name} ALTER COLUMN user_id DROP DEFAULT"
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    admin_user_id = _ensure_admin_user(bind)

    _add_user_id_column(
        "recipes",
        admin_user_id,
        unique_constraints=(
            ("uq_recipes_user_id_id", ("user_id", "id")),
            ("uq_recipes_user_id_title", ("user_id", "title")),
        ),
        index_columns=(("ix_recipes_user_id", ("user_id",)),),
    )

    _add_user_id_column(
        "ingredients",
        admin_user_id,
        drop_uniques=(("name",),),
        unique_constraints=(
            ("uq_ingredients_user_id_id", ("user_id", "id")),
            ("uq_ingredients_user_id_name", ("user_id", "name")),
        ),
        index_columns=(("ix_ingredients_user_id", ("user_id",)),),
    )

    _add_user_id_column(
        "tags",
        admin_user_id,
        drop_uniques=(("name",),),
        unique_constraints=(
            ("uq_tags_user_id_id", ("user_id", "id")),
            ("uq_tags_user_id_name", ("user_id", "name")),
        ),
        index_columns=(("ix_tags_user_id", ("user_id",)),),
    )

    recipe_tag_rows = bind.execute(
        sa.text("SELECT recipe_id, tag_id FROM recipe_tag")
    ).fetchall()
    recipe_ingredient_rows = bind.execute(
        sa.text(
            """
            SELECT recipe_id, ingredient_id, quantity, unit
            FROM recipe_ingredients
            """
        )
    ).fetchall()
    meal_side_rows = bind.execute(
        sa.text(
            "SELECT plan_date, meal_number, position, side_recipe_id FROM meal_side_dishes"
        )
    ).fetchall()
    meals_rows = bind.execute(
        sa.text(
            """
            SELECT plan_date, meal_number, recipe_id, accepted, leftover
            FROM meals
            """
        )
    ).fetchall()
    meal_plan_rows = bind.execute(sa.text("SELECT plan_date FROM meal_plans")).fetchall()

    recipe_owner_rows = bind.execute(
        sa.text("SELECT id, user_id FROM recipes")
    ).fetchall()
    recipe_user_map = {
        int(row.id): int(row.user_id) if row.user_id is not None else admin_user_id
        for row in recipe_owner_rows
    }

    tag_owner_rows = bind.execute(
        sa.text("SELECT id, user_id FROM tags")
    ).fetchall()
    tag_user_map = {
        int(row.id): int(row.user_id) if row.user_id is not None else admin_user_id
        for row in tag_owner_rows
    }

    ingredient_owner_rows = bind.execute(
        sa.text("SELECT id, user_id FROM ingredients")
    ).fetchall()
    ingredient_user_map = {
        int(row.id): int(row.user_id) if row.user_id is not None else admin_user_id
        for row in ingredient_owner_rows
    }

    def _resolve_recipe_user(recipe_id: int | None) -> int:
        if recipe_id is None:
            return admin_user_id
        return recipe_user_map.get(int(recipe_id), admin_user_id)

    def _ensure_tag_owner(tag_id: int | None, desired_user: int) -> int:
        if tag_id is None:
            return desired_user
        tag_key = int(tag_id)
        current = tag_user_map.get(tag_key)
        if current != desired_user:
            bind.execute(
                sa.text("UPDATE tags SET user_id = :user_id WHERE id = :tag_id"),
                {"user_id": desired_user, "tag_id": tag_key},
            )
            tag_user_map[tag_key] = desired_user
        return desired_user

    def _ensure_ingredient_owner(ingredient_id: int | None, desired_user: int) -> int:
        if ingredient_id is None:
            return desired_user
        ingredient_key = int(ingredient_id)
        current = ingredient_user_map.get(ingredient_key)
        if current != desired_user:
            bind.execute(
                sa.text(
                    "UPDATE ingredients SET user_id = :user_id WHERE id = :ingredient_id"
                ),
                {"user_id": desired_user, "ingredient_id": ingredient_key},
            )
            ingredient_user_map[ingredient_key] = desired_user
        return desired_user

    op.drop_table("recipe_tag")
    op.drop_table("recipe_ingredients")
    op.drop_table("meal_side_dishes")
    op.drop_table("meals")
    op.drop_table("meal_plans")

    op.create_table(
        "meal_plans",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "plan_date"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_meal_plans_user_plan_date",
        "meal_plans",
        ["user_id", "plan_date"],
        unique=False,
    )

    meal_plan_payload: set[tuple[int, object]] = {
        (admin_user_id, row.plan_date) for row in meal_plan_rows
    }

    meals_payload = []
    for row in meals_rows:
        user_id = _resolve_recipe_user(row.recipe_id)
        meal_plan_payload.add((user_id, row.plan_date))
        meals_payload.append(
            {
                "user_id": user_id,
                "plan_date": row.plan_date,
                "meal_number": row.meal_number,
                "recipe_id": row.recipe_id,
                "accepted": row.accepted,
                "leftover": row.leftover,
            }
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
        sa.ForeignKeyConstraint(
            ["user_id", "recipe_id"],
            ["recipes.user_id", "recipes.id"],
        ),
    )
    op.create_index(
        "ix_meals_user_plan_date",
        "meals",
        ["user_id", "plan_date"],
        unique=False,
    )

    meal_user_lookup = {
        (payload["plan_date"], payload["meal_number"]): payload["user_id"]
        for payload in meals_payload
    }

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
            ["user_id", "side_recipe_id"],
            ["recipes.user_id", "recipes.id"],
        ),
    )

    meal_side_payload = []
    for row in meal_side_rows:
        key = (row.plan_date, row.meal_number)
        existing_user = meal_user_lookup.get(key)
        side_owner = _resolve_recipe_user(row.side_recipe_id)
        if existing_user is None:
            user_id = side_owner
            meal_user_lookup[key] = user_id
        elif row.side_recipe_id is not None and side_owner != existing_user:
            meal_plan_payload.discard((existing_user, row.plan_date))
            user_id = side_owner
            meal_user_lookup[key] = user_id
            for payload in meals_payload:
                if (
                    payload["plan_date"] == row.plan_date
                    and payload["meal_number"] == row.meal_number
                ):
                    payload["user_id"] = user_id
                    break
        else:
            user_id = existing_user
        meal_plan_payload.add((user_id, row.plan_date))
        meal_side_payload.append(
            {
                "user_id": user_id,
                "plan_date": row.plan_date,
                "meal_number": row.meal_number,
                "position": row.position,
                "side_recipe_id": row.side_recipe_id,
            }
        )

    if meal_plan_payload:
        bind.execute(
            sa.text(
                "INSERT INTO meal_plans (user_id, plan_date) VALUES (:user_id, :plan_date)"
            ),
            [
                {"user_id": user_id, "plan_date": plan_date}
                for user_id, plan_date in sorted(meal_plan_payload, key=lambda item: (item[0], item[1]))
            ],
        )

    if meals_payload:
        bind.execute(
            sa.text(
                """
                INSERT INTO meals (user_id, plan_date, meal_number, recipe_id, accepted, leftover)
                VALUES (:user_id, :plan_date, :meal_number, :recipe_id, :accepted, :leftover)
                """
            ),
            meals_payload,
        )

    if meal_side_payload:
        bind.execute(
            sa.text(
                """
                INSERT INTO meal_side_dishes (user_id, plan_date, meal_number, position, side_recipe_id)
                VALUES (:user_id, :plan_date, :meal_number, :position, :side_recipe_id)
                """
            ),
            meal_side_payload,
        )

    op.create_table(
        "recipe_tag",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "recipe_id", "tag_id"),
        sa.ForeignKeyConstraint(
            ["user_id", "recipe_id"],
            ["recipes.user_id", "recipes.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "tag_id"],
            ["tags.user_id", "tags.id"],
            ondelete="CASCADE",
        ),
    )

    recipe_tag_payload = []
    for row in recipe_tag_rows:
        user_id = _resolve_recipe_user(row.recipe_id)
        user_id = _ensure_tag_owner(row.tag_id, user_id)
        recipe_tag_payload.append(
            {
                "user_id": user_id,
                "recipe_id": row.recipe_id,
                "tag_id": row.tag_id,
            }
        )

    if recipe_tag_payload:
        bind.execute(
            sa.text(
                """
                INSERT INTO recipe_tag (user_id, recipe_id, tag_id)
                VALUES (:user_id, :recipe_id, :tag_id)
                """
            ),
            recipe_tag_payload,
        )

    op.create_table(
        "recipe_ingredients",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("ingredient_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Float()),
        sa.Column("unit", UNIT_ENUM),
        sa.PrimaryKeyConstraint("user_id", "recipe_id", "ingredient_id"),
        sa.ForeignKeyConstraint(
            ["user_id", "recipe_id"],
            ["recipes.user_id", "recipes.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "ingredient_id"],
            ["ingredients.user_id", "ingredients.id"],
            ondelete="CASCADE",
        ),
    )

    recipe_ingredient_payload = []
    for row in recipe_ingredient_rows:
        user_id = _resolve_recipe_user(row.recipe_id)
        user_id = _ensure_ingredient_owner(row.ingredient_id, user_id)
        recipe_ingredient_payload.append(
            {
                "user_id": user_id,
                "recipe_id": row.recipe_id,
                "ingredient_id": row.ingredient_id,
                "quantity": row.quantity,
                "unit": row.unit,
            }
        )

    if recipe_ingredient_payload:
        bind.execute(
            sa.text(
                """
                INSERT INTO recipe_ingredients (user_id, recipe_id, ingredient_id, quantity, unit)
                VALUES (:user_id, :recipe_id, :ingredient_id, :quantity, :unit)
                """
            ),
            recipe_ingredient_payload,
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
        sa.text("SELECT user_id, recipe_id, tag_id FROM recipe_tag")
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
    op.drop_index("ix_meals_user_plan_date", table_name="meals")
    op.drop_table("meals")
    op.drop_index("ix_meal_plans_user_plan_date", table_name="meal_plans")
    op.drop_table("meal_plans")

    op.create_table(
        "meal_plans",
        sa.Column("plan_date", sa.Date(), primary_key=True),
    )

    if meal_plan_rows:
        bind.execute(
            sa.text("INSERT INTO meal_plans (plan_date) VALUES (:plan_date)"),
            [
                {"plan_date": row.plan_date}
                for row in meal_plan_rows
            ],
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
        bind.execute(
            sa.text(
                """
                INSERT INTO meals (plan_date, meal_number, recipe_id, accepted, leftover)
                VALUES (:plan_date, :meal_number, :recipe_id, :accepted, :leftover)
                """
            ),
            [
                {
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
        bind.execute(
            sa.text(
                """
                INSERT INTO meal_side_dishes (plan_date, meal_number, position, side_recipe_id)
                VALUES (:plan_date, :meal_number, :position, :side_recipe_id)
                """
            ),
            [
                {
                    "plan_date": row.plan_date,
                    "meal_number": row.meal_number,
                    "position": row.position,
                    "side_recipe_id": row.side_recipe_id,
                }
                for row in meal_side_rows
            ],
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
        bind.execute(
            sa.text(
                "INSERT INTO recipe_tag (recipe_id, tag_id) VALUES (:recipe_id, :tag_id)"
            ),
            [
                {
                    "recipe_id": row.recipe_id,
                    "tag_id": row.tag_id,
                }
                for row in recipe_tag_rows
            ],
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
        bind.execute(
            sa.text(
                """
                INSERT INTO recipe_ingredients (recipe_id, ingredient_id, quantity, unit)
                VALUES (:recipe_id, :ingredient_id, :quantity, :unit)
                """
            ),
            [
                {
                    "recipe_id": row.recipe_id,
                    "ingredient_id": row.ingredient_id,
                    "quantity": row.quantity,
                    "unit": row.unit,
                }
                for row in recipe_ingredient_rows
            ],
        )

    for index_name, table_name in (
        ("ix_tags_user_id", "tags"),
        ("ix_ingredients_user_id", "ingredients"),
        ("ix_recipes_user_id", "recipes"),
    ):
        op.drop_index(index_name, table_name=table_name)

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

