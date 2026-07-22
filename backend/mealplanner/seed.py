"""Database seeding helpers for the Meals Planner Codex application.

This module contains small utilities to populate the database with some
demonstration data.  The seeded data is intentionally tiny but exercises the
relationships between :class:`Recipe`, :class:`Ingredient` and :class:`Tag`.

The seeding functions are written so that they can be run multiple times
without creating duplicate records or raising integrity errors (for instance
the ``Tag`` table has a uniqueness constraint on ``name``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

import crud
from models import Ingredient, Recipe, RecipeIngredient, Tag, UnitEnum
from scoping import scope

# Curated starter ingredient library handed to every new account so the app is
# usable without adding ingredients one by one. Loaded once at import from a
# JSON fixture that non-coders can extend. Each entry is
# ``{"name", "unit", "season_months": [int], "categories": [str]}``.
_SYSTEM_INGREDIENTS_PATH = Path(__file__).resolve().parent.parent / "data" / "system_ingredients.json"
SYSTEM_INGREDIENTS: list[dict] = json.loads(_SYSTEM_INGREDIENTS_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------

def _create_recipe(
    session: Session,
    title: str,
    servings: int,
    procedure: str,
    ingredients: Iterable[tuple[str, float, str | UnitEnum]],
    tags: Iterable[str],
    *,
    course: str = "main",
) -> None:
    """Create a recipe with ``ingredients`` and ``tags``.

    This helper checks if a recipe with the given ``title`` already exists and
    only creates it when missing, making it safe to call repeatedly.
    """

    exists = session.execute(select(Recipe).where(Recipe.title == title)).scalar_one_or_none()
    if exists is not None:
        return

    recipe = Recipe(
        title=title,
        servings_default=servings,
        procedure=procedure,
        course=course,
    )
    session.add(recipe)

    for name, qty, unit in ingredients:
        ing = session.execute(select(Ingredient).where(Ingredient.name == name)).scalar_one_or_none()
        if ing is None:
            ing = Ingredient(name=name)
            session.add(ing)
        if isinstance(unit, str):
            unit = UnitEnum(unit)
        recipe.ingredients.append(
            RecipeIngredient(ingredient=ing, quantity=qty, unit=unit)
        )

    for tag_name in tags:
        recipe.tags.append(crud.get_or_create_tag(session, tag_name))


# Curated system tags. Format tags carry the repetition penalty; attribute
# tags do not (repeating them every meal is fine).
_PENALIZED_SYSTEM_TAGS = [
    "pasta", "soup", "risotto", "rice", "pizza", "salad", "stew", "roast",
    "sandwich", "curry", "noodles", "gnocchi",
]
_NEUTRAL_SYSTEM_TAGS = [
    "vegetarian", "vegan", "quick", "cheap", "spicy", "gluten-free", "breakfast",
]


def seed_system_tags(session: Session, user_id: int | None = None) -> None:
    """Idempotently upsert the curated system tags for ``user_id``.

    Marks each tag ``is_system=True`` and sets ``penalize_repetition`` according
    to whether it is a format tag. Pre-existing plain tags of the same name (and
    owner) are upgraded in place rather than duplicated. A ``commit`` is issued
    at the end.

    The curated set is fetched in one query rather than per tag: this runs on
    every registration (where it is a guaranteed miss for all of them) and on
    startup for each existing account.
    """

    curated = {name: True for name in _PENALIZED_SYSTEM_TAGS}
    curated.update({name: False for name in _NEUTRAL_SYSTEM_TAGS})

    session.flush()
    stmt = scope(select(Tag).where(Tag.name.in_(curated)), Tag.user_id, user_id)
    existing = {tag.name: tag for tag in session.execute(stmt).scalars()}

    for name, penalize in curated.items():
        tag = existing.get(name)
        if tag is None:
            tag = Tag(name=name, user_id=user_id)
            session.add(tag)
        tag.is_system = True
        tag.penalize_repetition = penalize

    session.commit()


def seed_system_ingredients(session: Session, user_id: int | None = None) -> None:
    """Idempotently give ``user_id`` its own copy of the starter ingredients.

    Each new account gets a full per-user copy of :data:`SYSTEM_INGREDIENTS`
    (there is no shared catalogue and no ``is_system`` marker on ``Ingredient`` --
    the ``(user_id, name)`` uniqueness constraint alone makes this safe to re-run).
    Names the user already owns are skipped, so this never duplicates rows and
    never clobbers ingredients the user has since edited. A ``commit`` is issued
    at the end, mirroring :func:`seed_system_tags`.
    """

    session.flush()
    names = [entry["name"] for entry in SYSTEM_INGREDIENTS]
    stmt = scope(
        select(Ingredient.name).where(Ingredient.name.in_(names)),
        Ingredient.user_id,
        user_id,
    )
    existing = set(session.execute(stmt).scalars())

    for entry in SYSTEM_INGREDIENTS:
        if entry["name"] in existing:
            continue
        session.add(
            Ingredient(
                name=entry["name"],
                unit=UnitEnum(entry["unit"]),
                season_months=entry["season_months"],
                categories=entry["categories"],
                user_id=user_id,
            )
        )

    session.commit()


def seed_sample_data(session: Session) -> None:
    """Populate the database with a small set of example data.

    The function can be executed multiple times; existing records will be left
    untouched.  A ``commit`` is issued at the end so callers do not need to
    manage transactions explicitly.
    """

    _create_recipe(
        session,
        title="Oatmeal",
        servings=1,
        procedure="Boil water and oats until thick.",
        ingredients=[
            ("Oats", 100.0, "g"),
            ("Water", 250.0, "ml"),
        ],
        tags=["vegetarian", "breakfast"],
    )

    _create_recipe(
        session,
        title="Grilled Cheese",
        servings=1,
        procedure="Butter bread, add cheese and grill until golden.",
        ingredients=[
            ("Bread", 2.0, "piece"),
            ("Cheddar Cheese", 1.0, "piece"),
            ("Butter", 15.0, "g"),
        ],
        tags=["quick", "vegetarian"],
    )

    session.commit()


__all__ = [
    "SYSTEM_INGREDIENTS",
    "seed_sample_data",
    "seed_system_ingredients",
    "seed_system_tags",
]
