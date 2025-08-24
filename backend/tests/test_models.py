import pytest
from datetime import date
from sqlalchemy import select
from mealplanner.models import Recipe, Ingredient, Tag, RecipeIngredient

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

def test_ingredient_relationship(db_session):
    r = Recipe(title="Soup", servings_default=4)
    ri = RecipeIngredient(
        quantity=2, ingredient=Ingredient(name="Carrot", unit="piece")
    )
    r.recipe_ingredients.append(ri)
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    assert len(r.ingredients) == 1
    assert r.ingredients[0].name == "Carrot"
    assert r.recipe_ingredients[0].recipe_id == r.id  # FK set

def test_delete_orphan_ingredients(db_session):
    r = Recipe(title="Stew", servings_default=3)
    r.recipe_ingredients.append(RecipeIngredient(ingredient=Ingredient(name="Onion")))
    db_session.add(r)
    db_session.commit()
    rid = r.id
    db_session.delete(r)
    db_session.commit()
    # no stray associations after cascade delete-orphan
    assert db_session.execute(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id == rid)
    ).first() is None

def test_many_to_many_tags(db_session):
    r = Recipe(title="Salad", servings_default=1)
    t1, t2 = Tag(name="vegetarian"), Tag(name="quick")
    r.tags.extend([t1, t2])
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    assert {t.name for t in r.tags} == {"vegetarian", "quick"}
    assert r in t1.recipes  # bidirectional

def test_tag_name_unique_constraint(db_session):
    db_session.add_all([Tag(name="pasta"), Tag(name="pasta")])
    with pytest.raises(Exception):   # IntegrityError once the 2nd insert hits
        db_session.commit()
    db_session.rollback()