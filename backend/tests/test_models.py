"""Model-level invariants: defaults, relationships and per-user uniqueness.

Covers what the ORM itself guarantees without a route in the way -- column
defaults on insert and update, the recipe/ingredient and recipe/tag
associations (including what survives a delete), and the per-user uniqueness
scoping that lets two accounts hold same-named tags.
"""
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from models import (
    Recipe,
    Ingredient,
    RecipeIngredient,
    Tag,
    User,
    recipe_tag_table,
)


def test_user_email_is_canonicalised_on_assignment(db_session):
    """The invariant lives on the model, so direct ORM construction obeys it too."""
    user = User(
        email="  Direct.ORM@Example.COM ",
        username="direct_orm",
        hashed_password="x",
        auth_provider="local",
    )
    assert user.email == "direct.orm@example.com"

    user.email = "Reassigned@Example.COM"
    assert user.email == "reassigned@example.com"


def test_recipe_insert_defaults(db_session):
    r = Recipe(title="Pasta")
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    assert r.id is not None
    assert r.procedure is None
    assert r.score is None
    assert r.date_last_consumed is None
    assert r.bulk_prep is False
    assert r.course == "main"
    # Quantities are stored as authored, for this many people.
    assert r.servings == 1


def test_recipe_servings_must_be_at_least_one(db_session):
    db_session.add(Recipe(title="Impossible", servings=0))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_recipe_keeps_its_authored_servings(db_session):
    r = Recipe(title="Ribollita", servings=4)
    ing = Ingredient(name="Cavolo nero")
    r.ingredients.append(RecipeIngredient(ingredient=ing, quantity=800, unit="g"))
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    assert r.servings == 4
    assert r.ingredients[0].quantity == 800


def test_ingredient_relationship(db_session):
    r = Recipe(title="Soup", course="main")
    ing = Ingredient(name="Carrot")
    r.ingredients.append(RecipeIngredient(ingredient=ing, quantity=2, unit="piece"))
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    assert len(r.ingredients) == 1
    assert r.ingredients[0].ingredient.name == "Carrot"
    assert r.ingredients[0].ingredient_id == ing.id


def test_delete_orphan_ingredients(db_session):
    r = Recipe(title="Stew", course="main")
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
    soup = Recipe(title="Soup", course="main")
    salad = Recipe(title="Salad", course="main")

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
    r = Recipe(title="Salad", course="main")
    t1, t2 = Tag(name="vegetarian"), Tag(name="quick")
    r.tags.extend([t1, t2])
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    assert {t.name for t in r.tags} == {"vegetarian", "quick"}
    assert r in t1.recipes  # bidirectional


def test_tag_name_unique_constraint(db_session):
    # Uniqueness is now scoped per user: two same-named tags owned by the same
    # user collide, but different users may each own a "pasta" tag.
    user = User(
        email="tags@x.test", username="tags", hashed_password="x",
        auth_provider="local",
    )
    db_session.add(user)
    db_session.flush()
    db_session.add_all([
        Tag(name="pasta", user_id=user.id),
        Tag(name="pasta", user_id=user.id),
    ])
    with pytest.raises(Exception):  # IntegrityError once the 2nd insert hits
        db_session.commit()
    db_session.rollback()


def test_remove_tag_from_recipe(db_session):
    r = Recipe(title="Pizza", course="main")
    t1 = Tag(name="italian")
    t2 = Tag(name="dinner")
    r.tags.extend([t1, t2])
    db_session.add(r)
    db_session.commit()

    # remove one tag and ensure association is updated
    r.tags.remove(t1)
    db_session.commit()
    db_session.refresh(r)

    assert {t.name for t in r.tags} == {"dinner"}
    assert db_session.get(Tag, t1.id) is not None
    assoc = db_session.execute(
        select(recipe_tag_table).where(
            recipe_tag_table.c.recipe_id == r.id,
            recipe_tag_table.c.tag_id == t1.id,
        )
    ).first()
    assert assoc is None


def test_update_ingredient_quantity(db_session):
    r = Recipe(title="Bread", course="main")
    base = Ingredient(name="Flour")
    ri = RecipeIngredient(ingredient=base, quantity=1000, unit="g")
    r.ingredients.append(ri)
    db_session.add(r)
    db_session.commit()

    ri.quantity = 2.5
    db_session.commit()

    assert ri.quantity == 2.5
    assert ri.unit == "g"
    assert base.season_months == []


def test_tag_cascade_delete(db_session):
    r = Recipe(title="Stir Fry", course="main")
    tag = Tag(name="asian")
    r.tags.append(tag)
    db_session.add(r)
    db_session.commit()

    db_session.delete(tag)
    db_session.commit()
    db_session.refresh(r)

    assert tag not in r.tags
    assert db_session.get(Tag, tag.id) is None
    assoc = db_session.execute(
        select(recipe_tag_table).where(recipe_tag_table.c.tag_id == tag.id)
    ).first()
    assert assoc is None


def test_optional_field_and_defaults_on_update(db_session):
    r = Recipe(title="Soup")
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)

    assert r.bulk_prep is False
    assert r.date_last_consumed is None
    assert r.course == "main"

    r.title = "Tomato Soup"
    r.date_last_consumed = date(2023, 10, 1)
    db_session.commit()
    db_session.refresh(r)

    assert r.date_last_consumed == date(2023, 10, 1)
    assert r.bulk_prep is False

    r.date_last_consumed = None
    db_session.commit()
    db_session.refresh(r)

    assert r.date_last_consumed is None
