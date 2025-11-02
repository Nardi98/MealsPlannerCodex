import pytest

from mealplanner.crud import (
    create_recipe,
    get_recipe,
    update_recipe,
    delete_recipe,
)
from mealplanner.models import Recipe, Ingredient, RecipeIngredient, UnitEnum


def test_create_recipe(db_session, test_user):
    """Recipes can be created with ingredients via ``RecipeIngredient``."""
    bread = Ingredient(name="Bread")
    recipe = create_recipe(
        db_session,
        title="Toast",
        servings_default=1,
        course="main",
        ingredients=[
            RecipeIngredient(ingredient=bread, quantity=2, unit=UnitEnum.PIECE)
        ],
        user=test_user,
    )
    assert recipe.id is not None
    assert len(recipe.ingredients) == 1
    assert recipe.ingredients[0].ingredient.name == "Bread"
    assert recipe.ingredients[0].quantity == 2
    assert db_session.get(Recipe, recipe.id) is not None
    assert recipe.course == "main"
    assert recipe.user_id == test_user.id
    assert recipe.ingredients[0].user_id == test_user.id
    assert recipe.ingredients[0].ingredient.user_id == test_user.id


def test_get_recipe(db_session, test_user):
    recipe = create_recipe(
        db_session, title="Soup", servings_default=3, course="main", user=test_user
    )
    fetched = get_recipe(db_session, recipe.id, user=test_user)
    assert fetched is not None
    assert fetched.id == recipe.id
    assert fetched.title == "Soup"
    assert fetched.course == "main"
    assert fetched.user_id == test_user.id


def test_update_recipe(db_session, test_user):
    cheese = Ingredient(name="Cheese")
    recipe = create_recipe(
        db_session,
        title="Burger",
        servings_default=1,
        course="main",
        ingredients=[
            RecipeIngredient(ingredient=cheese, quantity=1, unit=UnitEnum.PIECE)
        ],
        user=test_user,
    )
    updated = update_recipe(
        db_session,
        recipe.id,
        title="Vegan Burger",
        servings_default=2,
        course="main",
        ingredients=[
            RecipeIngredient(ingredient=cheese, quantity=2, unit=UnitEnum.PIECE)
        ],
        user=test_user,
    )
    assert updated is not None
    assert updated.title == "Vegan Burger"
    assert updated.servings_default == 2
    assert updated.ingredients[0].quantity == 2
    assert updated.course == "main"
    assert updated.user_id == test_user.id


def test_delete_recipe(db_session, test_user):
    recipe = create_recipe(
        db_session, title="Salad", servings_default=1, course="main", user=test_user
    )
    deleted = delete_recipe(db_session, recipe.id, user=test_user)
    assert deleted is True
    assert get_recipe(db_session, recipe.id, user=test_user) is None
    # ensure deleting non-existent returns False
    assert delete_recipe(db_session, 9999, user=test_user) is False


def test_create_recipe_defaults_course(db_session, test_user):
    recipe = create_recipe(
        db_session, title="Plain", servings_default=1, user=test_user
    )
    assert recipe.course == "main"
    assert recipe.user_id == test_user.id
