import io
import json
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import crud
from models import Ingredient, MealPlan, Meal, Recipe, RecipeIngredient, Tag


def _create_sample_data(session):
    """Populate the database with a small set of objects for testing."""
    tag = Tag(name="vegan")
    recipe = Recipe(title="Soup", servings_default=2, course="main")
    base = Ingredient(name="Water")
    recipe.ingredients.append(RecipeIngredient(ingredient=base, quantity=1, unit="ml"))
    recipe.tags.append(tag)
    plan = MealPlan(plan_date=date(2024, 1, 1))
    plan.meals.append(Meal(meal_number=1, recipe=recipe, accepted=True))
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


def test_import_creates_tables_when_missing():
    """import_data should initialise schema if tables are absent."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

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

    with Session() as session:
        crud.import_data(io.StringIO(json.dumps(payload)), session, mode="overwrite")
        assert session.query(Recipe).count() == 1


_FULL_RECIPE_PAYLOAD = {
    "title": "Stew",
    "servings_default": 4,
    "procedure": "Simmer everything.",
    "bulk_prep": True,
    "course": "first-course",
    "score": 3.5,
    "date_last_consumed": "2024-02-03",
    "ingredients": [],
    "tags": [],
}


def _assert_full_recipe(recipe):
    assert recipe.title == "Stew"
    assert recipe.servings_default == 4
    assert recipe.procedure == "Simmer everything."
    assert recipe.bulk_prep is True
    assert recipe.course == "first-course"
    assert recipe.score == 3.5
    assert recipe.date_last_consumed == date(2024, 2, 3)


def test_import_merge_builds_all_recipe_fields(db_session):
    payload = {"recipes": [dict(_FULL_RECIPE_PAYLOAD)], "tags": [], "meal_plans": []}
    crud.import_data(io.StringIO(json.dumps(payload)), db_session, mode="merge")
    _assert_full_recipe(db_session.query(Recipe).one())


def test_import_overwrite_new_builds_all_recipe_fields(db_session):
    payload = {"recipes": [dict(_FULL_RECIPE_PAYLOAD)], "tags": [], "meal_plans": []}
    crud.import_data(io.StringIO(json.dumps(payload)), db_session, mode="overwrite")
    _assert_full_recipe(db_session.query(Recipe).one())


def test_import_overwrite_existing_builds_all_recipe_fields(db_session):
    existing = Recipe(id=7, title="Old", servings_default=1, course="main")
    db_session.add(existing)
    db_session.commit()

    payload = {
        "recipes": [dict(_FULL_RECIPE_PAYLOAD, id=7)],
        "tags": [],
        "meal_plans": [],
    }
    crud.import_data(io.StringIO(json.dumps(payload)), db_session, mode="overwrite")
    _assert_full_recipe(db_session.query(Recipe).one())


def test_get_recipes_dead_stub_removed():
    """The dead ``tests.test_app``-stub-referencing helper is gone."""
    assert not hasattr(crud, "get_recipes")


def test_clear_data(db_session):
    _create_sample_data(db_session)
    assert db_session.query(Recipe).count() == 1
    crud.clear_data(db_session)
    assert db_session.query(Recipe).count() == 0
    assert db_session.query(Tag).count() == 0
    assert db_session.query(Ingredient).count() == 0
    assert db_session.query(MealPlan).count() == 0
    assert db_session.query(Meal).count() == 0
