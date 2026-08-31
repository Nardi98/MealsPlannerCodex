"""Audit probes for the measurement-unit branch.

Each test states the behaviour the design document asks for. A failure here is
a bug in the branch, not in the test.
"""

import os
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.command import downgrade, upgrade

sys.path.append(str(Path(__file__).resolve().parent.parent))

import crud
from models import DimensionEnum, Ingredient, Recipe, RecipeIngredient, UnitEnum
from tests.test_migrations import _scratch_database


def _make(session, name, **factors):
    ing = Ingredient(name=name, categories=[], season_months=[], **factors)
    session.add(ing)
    session.flush()
    return ing


# --- 5. merge must not discard a quantity it cannot convert -----------------

def test_merge_keeps_an_unconvertible_quantity(db_session) -> None:
    """Neither ingredient can cross mass <-> piece, so nothing may be lost.

    The design's "the merged ingredient simply spans two" cannot apply inside
    one recipe: the composite key ``(recipe_id, ingredient_id)`` permits a
    single row, so there is no second row for the unconvertible line to
    occupy. The decided mechanism is therefore a refusal that names the recipe
    and the missing factor. The invariant the design actually protects is
    unchanged and asserted here: the amount the user wrote down survives.
    """
    source = _make(db_session, "Tomatoes")
    target = _make(db_session, "Tomato")
    recipe = Recipe(title="Sauce")
    db_session.add(recipe)
    db_session.flush()
    db_session.add_all(
        [
            RecipeIngredient(
                recipe_id=recipe.id, ingredient_id=source.id,
                quantity=2, unit=UnitEnum.PIECE,
            ),
            RecipeIngredient(
                recipe_id=recipe.id, ingredient_id=target.id,
                quantity=100, unit=UnitEnum.G,
            ),
        ]
    )
    db_session.flush()

    with pytest.raises(ValueError) as refusal:
        crud.merge_ingredients(db_session, source.id, target.id)

    # The refusal has to be actionable: which recipe blocks the merge, and
    # which factor would unblock it.
    assert "Sauce" in str(refusal.value)

    surviving = (
        db_session.execute(
            sa.select(RecipeIngredient).where(
                RecipeIngredient.recipe_id == recipe.id
            )
        )
        .scalars()
        .all()
    )
    # Both lines are still there, untouched -- the merge wrote nothing.
    assert len(surviving) == 2
    assert {(r.quantity, r.unit) for r in surviving} == {
        (2, UnitEnum.PIECE),
        (100, UnitEnum.G),
    }


# --- 6. the bulk switch must never touch a counted ingredient ---------------

def test_switch_leaves_a_counted_ingredient_alone(db_session) -> None:
    """"`piece` is never touched" -- including by the null fallback.

    An onion with a piece weight and no explicit preference is counted today.
    Switching the account to metric must not silently start weighing it.
    """
    onion = _make(db_session, "Onion", grams_per_piece=150.0)
    assert onion.preferred_dimension is None

    crud.switch_preferred_dimension(db_session, DimensionEnum.MASS)

    db_session.refresh(onion)
    assert onion.preferred_dimension is None


def test_switch_reports_a_conversionless_ingredient_as_skipped(db_session) -> None:
    """A control: an ingredient with no factors is named, not switched."""
    _make(db_session, "Salt")
    switched, skipped = crud.switch_preferred_dimension(
        db_session, DimensionEnum.VOLUME
    )
    assert "Salt" not in switched
    assert "Salt" in skipped


# --- 7. the migration must be reversible ------------------------------------

@pytest.mark.usefixtures("db_session")
def test_measurement_migration_downgrades() -> None:
    """``downgrade`` is part of the migration's contract, so it must run."""
    with _scratch_database() as (config, url):
        upgrade(config, "a1d4f7b2c903")
        downgrade(config, "2ca32a5d0e51")
        engine = sa.create_engine(url)
        try:
            with engine.connect() as conn:
                cols = sa.inspect(conn).get_columns("ingredients")
            assert any(c["name"] == "unit" for c in cols)
        finally:
            engine.dispose()


# --- export/import must carry every new ingredient field --------------------

def test_export_carries_the_display_preference(db_session) -> None:
    """The design says the JSON payload carries the new ingredient fields."""
    import json

    ing = _make(
        db_session, "Onion",
        grams_per_piece=150.0, preferred_dimension=DimensionEnum.PIECE,
    )
    recipe = Recipe(title="Soup", user_id=None)
    db_session.add(recipe)
    db_session.flush()
    db_session.add(
        RecipeIngredient(
            recipe_id=recipe.id, ingredient_id=ing.id,
            quantity=2, unit=UnitEnum.PIECE,
        )
    )
    db_session.commit()

    payload = json.loads(crud.export_data(db_session, None))
    line = payload["recipes"][0]["ingredients"][0]
    assert line["preferred_dimension"] == "piece"
