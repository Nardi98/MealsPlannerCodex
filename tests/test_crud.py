import pytest

from mealplanner.crud import (
    create_recipe,
    get_recipe,
    update_recipe,
    delete_recipe,
)
from mealplanner.models import Recipe


def test_create_recipe(db_session):
    recipe = create_recipe(db_session, title="Toast", servings_default=1)
    assert recipe.id is not None
    assert db_session.get(Recipe, recipe.id) is not None


def test_get_recipe(db_session):
    recipe = create_recipe(db_session, title="Soup", servings_default=3)
    fetched = get_recipe(db_session, recipe.id)
    assert fetched is not None
    assert fetched.id == recipe.id
    assert fetched.title == "Soup"


def test_update_recipe(db_session):
    recipe = create_recipe(db_session, title="Burger", servings_default=1)
    updated = update_recipe(
        db_session, recipe.id, title="Vegan Burger", servings_default=2
    )
    assert updated is not None
    assert updated.title == "Vegan Burger"
    assert updated.servings_default == 2


def test_delete_recipe(db_session):
    recipe = create_recipe(db_session, title="Salad", servings_default=1)
    deleted = delete_recipe(db_session, recipe.id)
    assert deleted is True
    assert get_recipe(db_session, recipe.id) is None
    # ensure deleting non-existent returns False
    assert delete_recipe(db_session, 9999) is False
