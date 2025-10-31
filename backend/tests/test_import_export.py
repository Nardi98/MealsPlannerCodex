import io
import json
import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from mealplanner import crud
from mealplanner.models import Ingredient, MealPlan, Meal, Recipe, RecipeIngredient, Tag


def _create_sample_data(session):
    """Populate the database with a small set of objects for testing."""
    tag = Tag(name="vegan")
    recipe = Recipe(title="Soup", servings_default=2, course="main")
    base = Ingredient(name="Water")
    recipe.ingredients.append(RecipeIngredient(ingredient=base, quantity=1, unit="ml"))
    recipe.tags.append(tag)
    plan = MealPlan(plan_date=date(2024, 1, 1))
    plan.meals.append(Meal(meal_number=1, recipe=recipe, accepted=True, leftover=False))
    session.add_all([tag, recipe, plan])
    session.commit()


def test_round_trip_export_import(db_session):
    _create_sample_data(db_session)

    exported = crud.export_data(db_session)

    # Re-import into the same session; import_data should clear existing data first.
    crud.import_data(io.StringIO(exported), db_session, mode="overwrite")

    assert db_session.query(Recipe).count() == 1
    assert db_session.query(Tag).count() == 1
    assert db_session.query(Ingredient).count() == 1
    assert db_session.query(MealPlan).count() == 1

    recipe = db_session.query(Recipe).one()
    assert recipe.ingredients[0].ingredient.name == "Water"
    assert recipe.tags[0].name == "vegan"
    assert recipe.course == "main"

    plan = db_session.query(MealPlan).one()
    assert plan.plan_date == date(2024, 1, 1)
    assert plan.meals[0].recipe_id == recipe.id
    assert plan.meals[0].accepted is True
    assert plan.meals[0].leftover is False


def test_import_bad_data_raises(db_session):
    bad_file = io.StringIO("not json")
    with pytest.raises(ValueError):
        crud.import_data(bad_file, db_session)


def test_import_merge_adds_data(db_session):
    _create_sample_data(db_session)

    merge_payload = {
        "recipes": [
            {
                "title": "Salad",
                "servings_default": 1,
                "course": "main",
                "ingredients": [],
                "tags": [],
            }
        ],
        "tags": [],
        "meal_plans": [],
    }

    crud.import_data(io.StringIO(json.dumps(merge_payload)), db_session, mode="merge")

    titles = {r.title for r in db_session.query(Recipe).all()}
    assert titles == {"Soup", "Salad"}
    # Existing data remains untouched
    assert db_session.query(Tag).count() == 1


def test_import_merge_existing_ids(db_session):
    """Importing an export in merge mode duplicates recipes with new ids."""
    _create_sample_data(db_session)
    exported = crud.export_data(db_session)

    crud.import_data(io.StringIO(exported), db_session, mode="merge")

    recipes = db_session.query(Recipe).order_by(Recipe.id).all()
    assert len(recipes) == 2
    assert recipes[0].id != recipes[1].id
    assert db_session.query(Tag).count() == 1


def test_import_merge_tag_id_collision(db_session):
    """Tags imported in merge mode get new ids when ids clash."""
    existing = Tag(name="vegan")
    db_session.add(existing)
    db_session.commit()

    payload = {
        "recipes": [],
        "tags": [{"id": existing.id, "name": "vegetarian"}],
        "meal_plans": [],
    }

    crud.import_data(io.StringIO(json.dumps(payload)), db_session, mode="merge")

    tags = db_session.query(Tag).order_by(Tag.name).all()
    assert {t.name for t in tags} == {"vegan", "vegetarian"}
    assert len({t.id for t in tags}) == 2


def test_export_includes_related_objects(db_session):
    _create_sample_data(db_session)
    exported = crud.export_data(db_session)
    data = json.loads(exported)

    assert data["recipes"][0]["title"] == "Soup"
    assert data["recipes"][0]["course"] == "main"
    assert data["recipes"][0]["ingredients"][0]["name"] == "Water"
    tag_id = data["recipes"][0]["tags"][0]
    tag_lookup = {t["id"]: t["name"] for t in data["tags"]}
    assert tag_lookup[tag_id] == "vegan"
    assert data["meal_plans"][0]["plan_date"] == "2024-01-01"
    meal_info = data["meal_plans"][0]["meals"][0]
    assert meal_info["plan_date"] == "2024-01-01"
    assert meal_info["meal_number"] == 1
    assert meal_info["recipe_id"] == data["recipes"][0]["id"]
    assert meal_info["accepted"] is True
    assert meal_info["leftover"] is False


def test_import_creates_tables_when_missing(engine):
    """import_data should initialise schema if tables are absent."""

    schema = f"import_missing_{uuid.uuid4().hex}"
    payload = {
        "recipes": [
            {
                "title": "Temp",
                "servings_default": 1,
                "course": "main",
                "ingredients": [],
                "tags": [],
            }
        ],
        "tags": [],
        "meal_plans": [],
    }

    Session = sessionmaker(autoflush=False, autocommit=False, future=True)

    with engine.connect() as connection:
        connection = connection.execution_options(isolation_level="AUTOCOMMIT")
        connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    try:
        with engine.connect() as connection:
            connection.execute(text(f'SET search_path TO "{schema}"'))
            session = Session(bind=connection)
            try:
                crud.import_data(io.StringIO(json.dumps(payload)), session, mode="overwrite")
                assert session.query(Recipe).count() == 1
            finally:
                session.close()
    finally:
        with engine.connect() as connection:
            connection = connection.execution_options(isolation_level="AUTOCOMMIT")
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


def test_clear_data(db_session):
    _create_sample_data(db_session)
    assert db_session.query(Recipe).count() == 1
    crud.clear_data(db_session)
    assert db_session.query(Recipe).count() == 0
    assert db_session.query(Tag).count() == 0
    assert db_session.query(Ingredient).count() == 0
    assert db_session.query(MealPlan).count() == 0
    assert db_session.query(Meal).count() == 0
