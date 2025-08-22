import io
from datetime import date

import pytest

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
    crud.import_data(io.StringIO(exported), db_session)

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

