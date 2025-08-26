import pytest
from datetime import date
from sqlalchemy import select
from mealplanner.models import Recipe, Ingredient, RecipeIngredient, Tag


def test_recipe_insert_defaults(db_session):
    r = Recipe(title="Pasta", servings_default=2)
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    assert r.id is not None
    assert r.servings_default == 2
    assert r.procedure is None
    assert r.score is None
    assert r.date_last_consumed is None
    assert r.bulk_prep is False
    assert r.course == "main course"


def test_ingredient_relationship(db_session):
    r = Recipe(title="Soup", servings_default=4, course="main course")
    ing = Ingredient(name="Carrot")
    r.ingredients.append(RecipeIngredient(ingredient=ing, quantity=2, unit="piece"))
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    assert len(r.ingredients) == 1
    assert r.ingredients[0].ingredient.name == "Carrot"
    assert r.ingredients[0].ingredient_id == ing.id


def test_delete_orphan_ingredients(db_session):
    r = Recipe(title="Stew", servings_default=3, course="main course")
    ing = Ingredient(name="Onion")
    r.ingredients.append(RecipeIngredient(ingredient=ing))
    db_session.add(r)
    db_session.commit()
    ing_id = ing.id
    rid = r.id
    db_session.delete(r)
    db_session.commit()
    # association removed but ingredient remains
    assert db_session.get(Ingredient, ing_id) is not None
    assert (
        db_session.execute(
            select(RecipeIngredient).where(RecipeIngredient.recipe_id == rid)
        ).first()
        is None
    )


def test_shared_ingredient_multiple_recipes(db_session):
    """A single Ingredient can appear in many recipes with different amounts."""
    salt = Ingredient(name="Salt")
    soup = Recipe(title="Soup", servings_default=2, course="main course")
    salad = Recipe(title="Salad", servings_default=1, course="main course")

    soup.ingredients.append(
        RecipeIngredient(ingredient=salt, quantity=1, unit="g")
    )
    salad.ingredients.append(
        RecipeIngredient(ingredient=salt, quantity=2, unit="g")
    )
    db_session.add_all([soup, salad])
    db_session.commit()

    assert soup.ingredients[0].ingredient_id == salt.id
    assert salad.ingredients[0].ingredient_id == salt.id
    assert soup.ingredients[0].quantity == 1
    assert salad.ingredients[0].quantity == 2


def test_many_to_many_tags(db_session):
    r = Recipe(title="Salad", servings_default=1, course="main course")
    t1, t2 = Tag(name="vegetarian"), Tag(name="quick")
    r.tags.extend([t1, t2])
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    assert {t.name for t in r.tags} == {"vegetarian", "quick"}
    assert r in t1.recipes  # bidirectional


def test_tag_name_unique_constraint(db_session):
    db_session.add_all([Tag(name="pasta"), Tag(name="pasta")])
    with pytest.raises(Exception):  # IntegrityError once the 2nd insert hits
        db_session.commit()
    db_session.rollback()
