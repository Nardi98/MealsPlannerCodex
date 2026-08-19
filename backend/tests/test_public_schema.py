"""PRV-1/PRV-2/PRV-4 — the public serialiser is an allowlist, not a denylist.

The literal frozenset below *is* the requirement. It is written out by hand so
that adding a column to ``Recipe`` can never widen what the unauthenticated
surface emits: the equality assertion fails loudly instead.
"""

import datetime

import pytest

from public_schema import (
    PublicAttribution,
    PublicIngredient,
    PublicRecipe,
)

# PRV-2, verbatim. ``notes`` is struck by decision (no such column exists).
PRV2_ALLOWLIST = frozenset(
    {
        "title",
        "image_url",
        "servings",
        "procedure",
        "ingredients",
        "tags",
        "course",
        "author_display_name",
        "author_username",
        "attribution",
    }
)

PRV2_INGREDIENT_ALLOWLIST = frozenset({"name", "quantity", "unit"})

PRV2_ATTRIBUTION_ALLOWLIST = frozenset(
    {"author_username", "recipe_title", "copied_at"}
)


def test_public_recipe_fields_equal_the_prv2_allowlist():
    assert set(PublicRecipe.model_fields) == PRV2_ALLOWLIST


def test_public_ingredient_fields_equal_the_allowlist():
    assert set(PublicIngredient.model_fields) == PRV2_INGREDIENT_ALLOWLIST


def test_public_attribution_fields_equal_the_allowlist():
    assert set(PublicAttribution.model_fields) == PRV2_ATTRIBUTION_ALLOWLIST


def test_public_recipe_does_not_read_arbitrary_orm_attributes():
    """FC-6/PRV-1: no ``from_attributes``, so no column is exposed by default."""
    assert PublicRecipe.model_config.get("from_attributes") is not True
    assert PublicIngredient.model_config.get("from_attributes") is not True


def _seed(db_session, user, *, image_url=None, procedure="Mix well."):
    import crud
    import models

    recipe = crud.create_recipe(
        db_session,
        title="Pasta al forno",
        course="main",
        servings_default=4,
        user_id=user.id,
        procedure=procedure,
        image_url=image_url,
        bulk_prep=True,
        score=0.87,
        date_last_consumed=datetime.date(2026, 1, 1),
        date_last_rejected=datetime.date(2026, 2, 2),
    )
    ing = crud.get_or_create_ingredient(
        db_session, ingredient_id=None, name="Farina", user_id=user.id
    )
    db_session.flush()
    db_session.add(
        models.RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=ing.id,
            quantity=250.0,
            unit=models.UnitEnum.G,
        )
    )
    tag = crud.get_or_create_tag(db_session, name="comfort", user_id=user.id)
    recipe.tags.append(tag)
    db_session.commit()
    db_session.refresh(recipe)
    return recipe


def test_from_recipe_maps_the_permitted_fields(db_session, user):
    user.display_name = "Owner Person"
    db_session.commit()
    recipe = _seed(db_session, user, image_url="/media/x.jpg")

    public = PublicRecipe.from_recipe(recipe, user)

    assert public.title == "Pasta al forno"
    assert public.servings == 4
    assert public.course == "main"
    assert public.image_url == "/media/x.jpg"
    assert public.procedure == "Mix well."
    assert public.author_display_name == "Owner Person"
    assert public.author_username == "owner"
    assert public.tags == ["comfort"]
    assert [(i.name, i.quantity, i.unit) for i in public.ingredients] == [
        ("Farina", 250.0, "g")
    ]
    assert public.attribution is None


def test_from_recipe_falls_back_to_username_when_no_display_name(
    db_session, user
):
    user.display_name = None
    db_session.commit()
    recipe = _seed(db_session, user)

    assert PublicRecipe.from_recipe(recipe, user).author_display_name == "owner"


def test_from_recipe_dump_never_contains_private_columns(db_session, user):
    recipe = _seed(db_session, user)

    dumped = PublicRecipe.from_recipe(recipe, user).model_dump()
    blob = repr(dumped)

    for forbidden in (
        "score",
        "bulk_prep",
        "date_last_consumed",
        "date_last_rejected",
        "user_id",
        "email",
        "visibility",
        "copy_count",
    ):
        assert forbidden not in blob


def test_from_recipe_carries_the_attribution_snapshot(db_session, user):
    recipe = _seed(db_session, user)
    recipe.source_author_username = "chefanna"
    recipe.source_recipe_title = "Ragu originale"
    recipe.copied_at = datetime.datetime(2026, 3, 4, 5, 6, 7)
    db_session.commit()

    attribution = PublicRecipe.from_recipe(recipe, user).attribution

    assert attribution is not None
    assert attribution.author_username == "chefanna"
    assert attribution.recipe_title == "Ragu originale"
    assert attribution.copied_at == datetime.datetime(2026, 3, 4, 5, 6, 7)


def test_attribution_is_none_when_the_snapshot_is_incomplete(db_session, user):
    """AT-1: a half-written snapshot must not render a dangling credit."""
    recipe = _seed(db_session, user)
    recipe.source_recipe_title = "Ragu originale"
    db_session.commit()

    assert PublicRecipe.from_recipe(recipe, user).attribution is None


def test_public_recipe_rejects_extra_fields():
    with pytest.raises(Exception):
        PublicRecipe(
            title="t",
            image_url=None,
            servings=1,
            procedure=None,
            ingredients=[],
            tags=[],
            course="main",
            author_display_name="a",
            author_username="a",
            attribution=None,
            score=9.0,
        )


def test_ingredient_unit_is_a_plain_string(db_session, user):
    """No enum leaks into the template context."""
    recipe = _seed(db_session, user)
    unit = PublicRecipe.from_recipe(recipe, user).ingredients[0].unit
    assert isinstance(unit, str)


def test_scale_returns_a_new_recipe_with_scaled_quantities(db_session, user):
    """SP-2: server-side scaling, expressed on the public model."""
    recipe = _seed(db_session, user)
    public = PublicRecipe.from_recipe(recipe, user)

    scaled = public.scaled_to(8)

    assert scaled.servings == 8
    assert scaled.ingredients[0].quantity == 500.0
    assert public.ingredients[0].quantity == 250.0


def test_scale_to_zero_or_negative_is_ignored(db_session, user):
    recipe = _seed(db_session, user)
    public = PublicRecipe.from_recipe(recipe, user)

    assert public.scaled_to(0).servings == 4
    assert public.scaled_to(-3).ingredients[0].quantity == 250.0
