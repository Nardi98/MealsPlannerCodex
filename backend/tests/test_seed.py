import pytest
from sqlalchemy import select

from models import CATEGORIES, Recipe, Ingredient, RecipeIngredient, Tag, UnitEnum
from mealplanner.seed import (
    SYSTEM_INGREDIENTS,
    seed_sample_data,
    seed_system_ingredients,
    seed_system_tags,
)


def test_seed_populates_sample_data(db_session):
    seed_sample_data(db_session)

    oatmeal = db_session.execute(select(Recipe).where(Recipe.title == "Oatmeal")).scalar_one_or_none()
    grilled = db_session.execute(select(Recipe).where(Recipe.title == "Grilled Cheese")).scalar_one_or_none()
    assert oatmeal is not None
    assert grilled is not None
    assert oatmeal.course == "main"
    assert grilled.course == "main"

    # Ingredients linked correctly
    oatmeal_ing = {ri.ingredient.name for ri in oatmeal.ingredients}
    assert {"Oats", "Water"} <= oatmeal_ing

    tag_names = {t.name for t in db_session.execute(select(Tag)).scalars()}
    assert {"vegetarian", "breakfast", "quick"} <= tag_names

    # quick tag is associated with grilled cheese
    quick_tag = db_session.execute(select(Tag).where(Tag.name == "quick")).scalar_one()
    assert any(r.title == "Grilled Cheese" for r in quick_tag.recipes)


def test_seed_is_idempotent(db_session):
    seed_sample_data(db_session)
    recipes_before = db_session.execute(select(Recipe)).scalars().all()
    tags_before = db_session.execute(select(Tag)).scalars().all()
    ingredients_before = db_session.execute(select(Ingredient)).scalars().all()

    # Run seeding again; should not create duplicates or errors
    seed_sample_data(db_session)
    recipes_after = db_session.execute(select(Recipe)).scalars().all()
    tags_after = db_session.execute(select(Tag)).scalars().all()
    ingredients_after = db_session.execute(select(Ingredient)).scalars().all()

    assert len(recipes_before) == len(recipes_after)
    assert len(tags_before) == len(tags_after)
    assert len(ingredients_before) == len(ingredients_after)


def test_seed_system_tags_sets_flags(db_session):
    seed_system_tags(db_session)

    pasta = db_session.execute(select(Tag).where(Tag.name == "pasta")).scalar_one()
    assert pasta.is_system is True
    assert pasta.penalize_repetition is True

    vegetarian = db_session.execute(
        select(Tag).where(Tag.name == "vegetarian")
    ).scalar_one()
    assert vegetarian.is_system is True
    assert vegetarian.penalize_repetition is False


def test_seed_system_tags_is_idempotent(db_session):
    seed_system_tags(db_session)
    tags_before = db_session.execute(select(Tag)).scalars().all()
    seed_system_tags(db_session)
    tags_after = db_session.execute(select(Tag)).scalars().all()
    assert len(tags_before) == len(tags_after)


def test_seed_system_tags_upgrades_preexisting_plain_tag(db_session):
    # A user-created plain tag of the same name should gain the flags.
    db_session.add(Tag(name="pasta"))
    db_session.commit()

    seed_system_tags(db_session)

    tags = db_session.execute(select(Tag).where(Tag.name == "pasta")).scalars().all()
    assert len(tags) == 1
    assert tags[0].is_system is True
    assert tags[0].penalize_repetition is True


def test_system_ingredients_fixture_is_valid():
    # Guards hand-edits to data/system_ingredients.json: every unit must be a
    # real UnitEnum and every category one of the canonical CATEGORIES.
    valid_units = {u.value for u in UnitEnum}
    valid_categories = set(CATEGORIES)

    assert len(SYSTEM_INGREDIENTS) >= 150
    names = [entry["name"] for entry in SYSTEM_INGREDIENTS]
    assert len(names) == len(set(names)), "duplicate ingredient names in fixture"

    for entry in SYSTEM_INGREDIENTS:
        assert entry["unit"] in valid_units, entry
        assert set(entry["categories"]) <= valid_categories, entry
        assert all(1 <= m <= 12 for m in entry["season_months"]), entry


def test_seed_system_ingredients_populates(db_session, user):
    seed_system_ingredients(db_session, user.id)

    potato = db_session.execute(
        select(Ingredient).where(
            Ingredient.name == "Potato", Ingredient.user_id == user.id
        )
    ).scalar_one()
    assert potato.unit == UnitEnum.G
    assert potato.season_months == [9, 10, 11, 12, 1]
    assert "Vegetables" in potato.categories

    count = db_session.execute(
        select(Ingredient).where(Ingredient.user_id == user.id)
    ).scalars().all()
    assert len(count) == len(SYSTEM_INGREDIENTS)


def test_seed_system_ingredients_is_idempotent(db_session, user):
    seed_system_ingredients(db_session, user.id)
    before = db_session.execute(
        select(Ingredient).where(Ingredient.user_id == user.id)
    ).scalars().all()

    seed_system_ingredients(db_session, user.id)
    after = db_session.execute(
        select(Ingredient).where(Ingredient.user_id == user.id)
    ).scalars().all()

    assert len(before) == len(after)


def test_seed_system_ingredients_scoped_to_user(db_session, user):
    import crud

    other = crud.create_user(
        db_session, email="other@test.local", hashed_password="x"
    )
    seed_system_ingredients(db_session, user.id)

    # The seeded rows are owned by ``user`` and invisible to ``other``.
    owned = db_session.execute(
        select(Ingredient).where(Ingredient.user_id == user.id)
    ).scalars().all()
    others = db_session.execute(
        select(Ingredient).where(Ingredient.user_id == other.id)
    ).scalars().all()

    assert len(owned) == len(SYSTEM_INGREDIENTS)
    assert others == []
