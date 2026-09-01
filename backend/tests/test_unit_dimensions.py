"""Storage holds base metric units only, and ingredients carry their physics.

``kg`` and ``l`` stop being storable and become *formatting*, on the same
footing as ``cup``: a narrow storage vocabulary is what makes aggregation well
defined. In their place the ingredient gains the two numbers that let a reader
cross a dimension -- a density and a piece weight -- plus a display preference
saying which of its dimensions should lead.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

import models
from models import DimensionEnum, Ingredient, Recipe, RecipeIngredient, UnitEnum


def test_storage_vocabulary_is_one_base_unit_per_dimension():
    assert [u.value for u in UnitEnum] == ["g", "ml", "piece"]


def test_kg_and_l_are_no_longer_storable_units():
    # They are ways of writing a stored amount down, not amounts themselves.
    for written in ("kg", "l"):
        with pytest.raises(ValueError):
            UnitEnum(written)


def test_the_database_rejects_a_unit_outside_the_vocabulary(db_session, user):
    recipe = Recipe(title="Rejects", user_id=user.id)
    ingredient = Ingredient(name="Flour", user_id=user.id)
    db_session.add_all([recipe, ingredient])
    db_session.flush()

    db_session.execute(
        models.RecipeIngredient.__table__.insert().values(
            recipe_id=recipe.id, ingredient_id=ingredient.id, quantity=1,
        )
    )
    with pytest.raises(DatabaseError):
        db_session.execute(text("UPDATE recipe_ingredients SET unit = 'KG'"))


def test_an_ingredient_carries_a_density_and_a_piece_weight(db_session, user):
    flour = Ingredient(name="Flour", user_id=user.id, grams_per_ml=0.53)
    db_session.add(flour)
    db_session.flush()

    assert flour.grams_per_ml == 0.53
    # Null is a recorded fact -- flour has no meaningful piece weight -- not a
    # gap waiting to be filled.
    assert flour.grams_per_piece is None


def test_an_ingredient_prefers_a_dimension_not_a_unit(db_session, user):
    # g vs kg vs oz is formatting the metric/US setting already decides. The
    # only question open per ingredient is: weigh it, measure it, or count it.
    assert [d.value for d in DimensionEnum] == ["mass", "volume", "piece"]

    onion = Ingredient(
        name="Onion",
        user_id=user.id,
        grams_per_piece=150,
        preferred_dimension=DimensionEnum.PIECE,
    )
    db_session.add(onion)
    db_session.flush()
    assert onion.preferred_dimension is DimensionEnum.PIECE


def test_an_ingredient_no_longer_owns_a_canonical_unit():
    # Recipes keep the dimension they were authored in; unification happens at
    # read time, so a bad conversion can only ever produce a bad *display*.
    assert not hasattr(Ingredient, "unit")


def test_an_account_reads_amounts_in_one_system(db_session, user):
    assert user.unit_system == "metric"
    user.unit_system = "us"
    db_session.flush()
    db_session.refresh(user)
    assert user.unit_system == "us"


def test_a_recipe_line_still_owns_its_unit(db_session, user):
    recipe = Recipe(title="Soup", user_id=user.id)
    ingredient = Ingredient(name="Milk", user_id=user.id)
    db_session.add_all([recipe, ingredient])
    db_session.flush()
    line = RecipeIngredient(
        recipe_id=recipe.id,
        ingredient_id=ingredient.id,
        quantity=500,
        unit=UnitEnum.ML,
    )
    db_session.add(line)
    db_session.flush()
    assert line.unit is UnitEnum.ML
