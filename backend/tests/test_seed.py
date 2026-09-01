import pytest
from sqlalchemy import select

from models import CATEGORIES, DimensionEnum, Recipe, Ingredient, RecipeIngredient, Tag, UnitEnum
from mealplanner.seed import (
    SYSTEM_INGREDIENTS,
    SYSTEM_TAGS,
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
    # Guards hand-edits to data/system_ingredients.json: every preferred
    # dimension must be a real DimensionEnum, every category one of the
    # canonical CATEGORIES, and every conversion a positive number.
    valid_dimensions = {d.value for d in DimensionEnum}
    valid_categories = set(CATEGORIES)

    assert len(SYSTEM_INGREDIENTS) >= 150
    names = [entry["name"] for entry in SYSTEM_INGREDIENTS]
    assert len(names) == len(set(names)), "duplicate ingredient names in fixture"

    for entry in SYSTEM_INGREDIENTS:
        assert entry["preferred_dimension"] in valid_dimensions, entry
        assert set(entry["categories"]) <= valid_categories, entry
        assert all(1 <= m <= 12 for m in entry["season_months"]), entry
        for factor in ("grams_per_ml", "grams_per_piece"):
            # Absent is a legitimate, permanent answer. Present must be real.
            if factor in entry:
                assert entry[factor] > 0, entry


def test_the_fixture_states_conversions_only_where_they_make_sense():
    """The seeded pantry must exercise the null path, not pretend it is rare.

    A new account should arrive able to unify what it can -- an onion weighed
    or counted -- and honest about what it cannot: nothing knows what one
    millilitre of egg is, and nothing should invent it.
    """
    by_name = {entry["name"]: entry for entry in SYSTEM_INGREDIENTS}

    assert by_name["Onion"]["grams_per_piece"] == 150
    assert "grams_per_ml" not in by_name["Onion"]
    assert by_name["Milk"]["grams_per_ml"] == 1.03
    assert "grams_per_piece" not in by_name["Milk"]

    without_any = [
        e["name"] for e in SYSTEM_INGREDIENTS
        if "grams_per_ml" not in e and "grams_per_piece" not in e
    ]
    assert len(without_any) > 20


def test_seed_system_ingredients_populates(db_session, user):
    seed_system_ingredients(db_session, user.id)

    potato = db_session.execute(
        select(Ingredient).where(
            Ingredient.name == "Potato", Ingredient.user_id == user.id
        )
    ).scalar_one()
    assert potato.preferred_dimension is DimensionEnum.MASS
    assert potato.grams_per_piece == 170
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


def test_seed_system_tags_includes_meat(db_session):
    # ``meat`` is descriptive, not a format tag: repeating it is fine, so it
    # must not carry the repetition penalty.
    seed_system_tags(db_session)

    meat = db_session.execute(select(Tag).where(Tag.name == "meat")).scalar_one()
    assert meat.is_system is True
    assert meat.penalize_repetition is False


def test_system_tags_fixture_is_valid():
    # Guards hand-edits to data/system_tags.json, which the starter pack's
    # frontend test reads as the tag vocabulary it is allowed to use.
    names = [entry["name"] for entry in SYSTEM_TAGS]
    assert len(names) == len(set(names)), "duplicate tag names in fixture"
    for entry in SYSTEM_TAGS:
        assert entry["name"] == entry["name"].lower(), entry
        assert isinstance(entry["penalize_repetition"], bool), entry
