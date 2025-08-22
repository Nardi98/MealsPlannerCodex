import io
import json
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mealplanner import crud
from mealplanner.models import Ingredient, MealPlan, MealSlot, Recipe, Tag


def _create_sample_data(session):
    """Populate the database with a small set of objects for testing."""
    tag = Tag(name="vegan")
    recipe = Recipe(title="Soup", servings_default=2)
    recipe.ingredients.append(Ingredient(name="Water", quantity=1, unit="cup"))
    recipe.tags.append(tag)
    plan = MealPlan(plan_date=date(2024, 1, 1))
    plan.slots.append(MealSlot(meal_time="lunch", recipe=recipe))
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
    assert recipe.ingredients[0].name == "Water"
    assert recipe.tags[0].name == "vegan"

    plan = db_session.query(MealPlan).one()
    assert plan.slots[0].recipe_id == recipe.id


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


def test_export_includes_related_objects(db_session):
    _create_sample_data(db_session)
    exported = crud.export_data(db_session)
    data = json.loads(exported)

    assert data["recipes"][0]["title"] == "Soup"
    assert data["recipes"][0]["ingredients"][0]["name"] == "Water"
    tag_id = data["recipes"][0]["tags"][0]
    tag_lookup = {t["id"]: t["name"] for t in data["tags"]}
    assert tag_lookup[tag_id] == "vegan"
    assert data["meal_plans"][0]["slots"][0]["meal_time"] == "lunch"
    assert data["meal_plans"][0]["slots"][0]["recipe_id"] == data["recipes"][0]["id"]


def test_import_creates_tables_when_missing():
    """import_data should initialise schema if tables are absent."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    payload = {
        "recipes": [
            {"title": "Temp", "servings_default": 1, "ingredients": [], "tags": []}
        ],
        "tags": [],
        "meal_plans": [],
    }

    with Session() as session:
        crud.import_data(io.StringIO(json.dumps(payload)), session, mode="overwrite")
        assert session.query(Recipe).count() == 1

