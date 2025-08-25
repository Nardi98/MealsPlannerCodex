from datetime import date
from sqlalchemy import select

from mealplanner.models import Recipe, Ingredient, RecipeIngredient, Tag, recipe_tag_table


def test_remove_tag_from_recipe(db_session):
    r = Recipe(title="Pizza", servings_default=2, course="main")
    t1 = Tag(name="italian")
    t2 = Tag(name="dinner")
    r.tags.extend([t1, t2])
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)

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
    r = Recipe(title="Bread", servings_default=4, course="main")
    base = Ingredient(name="Flour")
    ri = RecipeIngredient(ingredient=base, quantity=1, unit="kg")
    r.ingredients.append(ri)
    db_session.add(r)
    db_session.commit()

    ri.quantity = 2.5
    db_session.commit()
    db_session.refresh(ri)

    assert ri.quantity == 2.5
    assert ri.unit == "kg"
    assert base.season_months == []


def test_tag_cascade_delete(db_session):
    r = Recipe(title="Stir Fry", servings_default=1, course="main")
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
    r = Recipe(title="Soup", servings_default=2)
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
