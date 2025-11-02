from datetime import date

import sqlalchemy as sa

from tests.conftest import TEST_DATABASE_URL, temporary_database
from migration_runner import upgrade as run_migrations


def test_migration_adds_course_default():
    with temporary_database(TEST_DATABASE_URL) as url:
        engine = sa.create_engine(url, future=True, pool_pre_ping=True)
        with engine.connect() as conn:
            if engine.dialect.name == "postgresql":
                create_sql = """
CREATE TABLE recipes (
    id SERIAL PRIMARY KEY,
    title VARCHAR NOT NULL,
    servings_default INTEGER NOT NULL
)
"""
            else:
                create_sql = """
CREATE TABLE recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR NOT NULL,
    servings_default INTEGER NOT NULL
)
"""

            conn.execute(sa.text(create_sql))
            insert_sql = sa.text(
                "INSERT INTO recipes (title, servings_default) "
                "VALUES ('Soup', 1)"
            )
            conn.execute(insert_sql)
            conn.commit()

        run_migrations(url)

        with engine.connect() as conn:
            result = conn.execute(
                sa.text("SELECT course FROM recipes")
            ).fetchone()
            assert result[0] == "main"
        engine.dispose()


def test_migrations_add_user_ownership_constraints():
    with temporary_database(TEST_DATABASE_URL) as url:
        engine = sa.create_engine(url, future=True, pool_pre_ping=True)
        metadata = sa.MetaData()
        unit_enum = sa.Enum("g", "kg", "l", "ml", "piece", name="unit_enum")

        recipes = sa.Table(
            "recipes",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("title", sa.String, nullable=False),
            sa.Column("servings_default", sa.Integer, nullable=False),
            sa.Column("procedure", sa.Text),
            sa.Column("bulk_prep", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("score", sa.Float),
            sa.Column("date_last_consumed", sa.Date),
            sa.Column("course", sa.String, nullable=False, server_default="main"),
        )
        ingredients = sa.Table(
            "ingredients",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String, nullable=False, unique=True),
            sa.Column("season_months", sa.String),
            sa.Column("unit", unit_enum),
        )
        tags = sa.Table(
            "tags",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String, nullable=False, unique=True),
        )
        recipe_tag = sa.Table(
            "recipe_tag",
            metadata,
            sa.Column("recipe_id", sa.Integer, nullable=False),
            sa.Column("tag_id", sa.Integer, nullable=False),
            sa.PrimaryKeyConstraint("recipe_id", "tag_id"),
        )
        recipe_ingredients = sa.Table(
            "recipe_ingredients",
            metadata,
            sa.Column("recipe_id", sa.Integer, nullable=False),
            sa.Column("ingredient_id", sa.Integer, nullable=False),
            sa.Column("quantity", sa.Float),
            sa.Column("unit", unit_enum),
            sa.PrimaryKeyConstraint("recipe_id", "ingredient_id"),
        )
        meal_plans = sa.Table(
            "meal_plans",
            metadata,
            sa.Column("plan_date", sa.Date, primary_key=True),
        )
        meals = sa.Table(
            "meals",
            metadata,
            sa.Column("plan_date", sa.Date, nullable=False),
            sa.Column("meal_number", sa.Integer, nullable=False),
            sa.Column("recipe_id", sa.Integer),
            sa.Column("accepted", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("leftover", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.PrimaryKeyConstraint("plan_date", "meal_number"),
        )
        meal_side_dishes = sa.Table(
            "meal_side_dishes",
            metadata,
            sa.Column("plan_date", sa.Date, nullable=False),
            sa.Column("meal_number", sa.Integer, nullable=False),
            sa.Column("position", sa.Integer, nullable=False),
            sa.Column("side_recipe_id", sa.Integer, nullable=False),
            sa.PrimaryKeyConstraint("plan_date", "meal_number", "position"),
        )

        metadata.create_all(engine)

        with engine.begin() as conn:
            conn.execute(
                recipes.insert(),
                {
                    "id": 1,
                    "title": "Chili",
                    "servings_default": 4,
                    "procedure": "Simmer beans",
                    "bulk_prep": False,
                    "course": "main",
                },
            )
            conn.execute(
                ingredients.insert(),
                {
                    "id": 1,
                    "name": "Beans",
                    "season_months": "1,2",
                    "unit": "kg",
                },
            )
            conn.execute(tags.insert(), {"id": 1, "name": "Comfort"})
            conn.execute(recipe_tag.insert(), {"recipe_id": 1, "tag_id": 1})
            conn.execute(
                recipe_ingredients.insert(),
                {
                    "recipe_id": 1,
                    "ingredient_id": 1,
                    "quantity": 1.5,
                    "unit": "kg",
                },
            )
            conn.execute(meal_plans.insert(), {"plan_date": date(2024, 1, 1)})
            conn.execute(
                meals.insert(),
                {
                    "plan_date": date(2024, 1, 1),
                    "meal_number": 1,
                    "recipe_id": 1,
                    "accepted": True,
                    "leftover": False,
                },
            )
            conn.execute(
                meal_side_dishes.insert(),
                {
                    "plan_date": date(2024, 1, 1),
                    "meal_number": 1,
                    "position": 1,
                    "side_recipe_id": 1,
                },
            )

        run_migrations(url)

        with engine.connect() as conn:
            inspector = sa.inspect(conn)
            user_columns = {col["name"] for col in inspector.get_columns("users")}
            assert {"created_at", "updated_at"}.issubset(user_columns)

            admin_id = conn.execute(
                sa.text("SELECT id FROM users WHERE email = :email"),
                {"email": "admin@example.com"},
            ).scalar_one()

            assert conn.execute(
                sa.text("SELECT COUNT(*) FROM recipes WHERE user_id = :uid"),
                {"uid": admin_id},
            ).scalar_one() == 1
            assert conn.execute(
                sa.text("SELECT COUNT(*) FROM ingredients WHERE user_id = :uid"),
                {"uid": admin_id},
            ).scalar_one() == 1
            assert conn.execute(
                sa.text("SELECT COUNT(*) FROM tags WHERE user_id = :uid"),
                {"uid": admin_id},
            ).scalar_one() == 1
            assert conn.execute(
                sa.text("SELECT COUNT(*) FROM meal_plans WHERE user_id = :uid"),
                {"uid": admin_id},
            ).scalar_one() == 1
            assert conn.execute(
                sa.text("SELECT COUNT(*) FROM meals WHERE user_id = :uid"),
                {"uid": admin_id},
            ).scalar_one() == 1
            assert conn.execute(
                sa.text("SELECT COUNT(*) FROM meal_side_dishes WHERE user_id = :uid"),
                {"uid": admin_id},
            ).scalar_one() == 1
            assert conn.execute(
                sa.text("SELECT COUNT(*) FROM recipe_tag WHERE user_id = :uid"),
                {"uid": admin_id},
            ).scalar_one() == 1
            assert conn.execute(
                sa.text(
                    "SELECT COUNT(*) FROM recipe_ingredients WHERE user_id = :uid"
                ),
                {"uid": admin_id},
            ).scalar_one() == 1

            meal_plan_pk = inspector.get_pk_constraint("meal_plans")
            assert meal_plan_pk["constrained_columns"] == ["user_id", "plan_date"]

            meal_indexes = {idx["name"] for idx in inspector.get_indexes("meals")}
            assert "ix_meals_user_plan_date" in meal_indexes

            meal_plan_indexes = {
                idx["name"] for idx in inspector.get_indexes("meal_plans")
            }
            assert "ix_meal_plans_user_plan_date" in meal_plan_indexes

            recipe_unique = {
                constraint["name"]
                for constraint in inspector.get_unique_constraints("recipes")
            }
            assert "uq_recipes_user_id_title" in recipe_unique

            ingredient_unique = {
                constraint["name"]
                for constraint in inspector.get_unique_constraints("ingredients")
            }
            assert "uq_ingredients_user_id_name" in ingredient_unique

            tag_unique = {
                constraint["name"]
                for constraint in inspector.get_unique_constraints("tags")
            }
            assert "uq_tags_user_id_name" in tag_unique

            recipe_columns = {col["name"] for col in inspector.get_columns("recipe_tag")}
            assert "user_id" in recipe_columns

            recipe_ing_columns = {
                col["name"] for col in inspector.get_columns("recipe_ingredients")
            }
            assert "user_id" in recipe_ing_columns

        engine.dispose()
