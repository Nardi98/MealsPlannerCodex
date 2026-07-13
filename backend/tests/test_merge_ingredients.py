import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parent.parent))

import crud
from main import app
from database import Base, engine
from models import Ingredient, Recipe, RecipeIngredient, UnitEnum


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _make(session, name, unit, categories=None, season=None):
    ing = Ingredient(
        name=name, unit=unit, categories=categories or [], season_months=season or []
    )
    session.add(ing)
    session.flush()
    return ing


def test_merge_repoints_references(db_session) -> None:
    source = _make(db_session, "Tomatoes", UnitEnum.PIECE)
    target = _make(db_session, "Tomato", UnitEnum.G)
    recipe = Recipe(title="Salad", servings_default=2)
    db_session.add(recipe)
    db_session.flush()
    db_session.add(
        RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=source.id,
            quantity=2,
            unit=UnitEnum.PIECE,
        )
    )
    db_session.flush()

    merged = crud.merge_ingredients(
        db_session, source.id, target.id, surviving_unit=UnitEnum.G,
        conversion_factor=150.0,
    )
    assert merged.id == target.id
    line = db_session.get(RecipeIngredient, (recipe.id, target.id))
    assert line is not None
    assert line.quantity == 300.0
    assert line.unit == UnitEnum.G
    assert db_session.get(Ingredient, source.id) is None


def test_merge_folds_colliding_line(db_session) -> None:
    source = _make(db_session, "Tomatoes", UnitEnum.G)
    target = _make(db_session, "Tomato", UnitEnum.G)
    recipe = Recipe(title="Sauce", servings_default=2)
    db_session.add(recipe)
    db_session.flush()
    db_session.add_all(
        [
            RecipeIngredient(
                recipe_id=recipe.id, ingredient_id=source.id, quantity=100,
                unit=UnitEnum.G,
            ),
            RecipeIngredient(
                recipe_id=recipe.id, ingredient_id=target.id, quantity=50,
                unit=UnitEnum.G,
            ),
        ]
    )
    db_session.flush()

    crud.merge_ingredients(db_session, source.id, target.id)
    line = db_session.get(RecipeIngredient, (recipe.id, target.id))
    assert line.quantity == 150.0
    assert db_session.get(RecipeIngredient, (recipe.id, source.id)) is None


def test_merge_leaves_units_when_no_factor(db_session) -> None:
    source = _make(db_session, "Tomatoes", UnitEnum.ML)
    target = _make(db_session, "Tomato", UnitEnum.G)
    recipe = Recipe(title="Soup", servings_default=2)
    db_session.add(recipe)
    db_session.flush()
    db_session.add(
        RecipeIngredient(
            recipe_id=recipe.id, ingredient_id=source.id, quantity=100,
            unit=UnitEnum.ML,
        )
    )
    db_session.flush()

    crud.merge_ingredients(
        db_session, source.id, target.id, surviving_unit=UnitEnum.G,
        conversion_factor=None,
    )
    line = db_session.get(RecipeIngredient, (recipe.id, target.id))
    assert line.quantity == 100
    assert line.unit == UnitEnum.ML


def test_merge_unions_categories_and_season(db_session) -> None:
    source = _make(
        db_session, "Tomatoes", UnitEnum.G, categories=["Fruit"], season=[1, 2]
    )
    target = _make(
        db_session, "Tomato", UnitEnum.G, categories=["Vegetables"], season=[2, 3]
    )
    merged = crud.merge_ingredients(db_session, source.id, target.id)
    assert merged.categories == ["Vegetables", "Fruit"]
    assert merged.season_months == [1, 2, 3]


def test_merge_same_id_raises(db_session) -> None:
    ing = _make(db_session, "Tomato", UnitEnum.G)
    with pytest.raises(ValueError):
        crud.merge_ingredients(db_session, ing.id, ing.id)


def test_merge_missing_returns_none(db_session) -> None:
    ing = _make(db_session, "Tomato", UnitEnum.G)
    assert crud.merge_ingredients(db_session, ing.id, 9999) is None


def test_merge_endpoint_404_and_400() -> None:
    _reset_db()
    client = TestClient(app)
    a = client.post("/ingredients", json={"name": "Tomato", "unit": "g"}).json()
    res = client.post(
        "/ingredients/merge",
        json={"source_id": a["id"], "target_id": a["id"]},
    )
    assert res.status_code == 400
    res = client.post(
        "/ingredients/merge",
        json={"source_id": a["id"], "target_id": 9999},
    )
    assert res.status_code == 404
