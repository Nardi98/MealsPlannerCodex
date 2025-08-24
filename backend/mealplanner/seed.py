"""Database seeding helpers for the Meals Planner Codex application.

This module contains small utilities to populate the database with some
demonstration data.  The seeded data is intentionally tiny but exercises the
relationships between :class:`Recipe`, :class:`Ingredient` and :class:`Tag`.

The seeding functions are written so that they can be run multiple times
without creating duplicate records or raising integrity errors (for instance
the ``Tag`` table has a uniqueness constraint on ``name``).
"""

from __future__ import annotations

from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Ingredient, Recipe, Tag


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------

def _get_or_create_tag(session: Session, name: str) -> Tag:
    """Return a ``Tag`` with *name*, creating it if necessary.

    Parameters
    ----------
    session:
        Active SQLAlchemy session.
    name:
        Name of the tag to fetch or create.
    """

    # ``autoflush`` is disabled for the project's sessions which means pending
    # objects won't be written to the database before queries are issued.  We
    # explicitly flush so that a tag added earlier in the same transaction is
    # visible to the ``SELECT`` below.
    session.flush()
    tag = session.execute(select(Tag).where(Tag.name == name)).scalar_one_or_none()
    if tag is None:
        tag = Tag(name=name)
        session.add(tag)
    return tag


def _create_recipe(
    session: Session,
    title: str,
    servings: int,
    procedure: str,
    ingredients: Iterable[tuple[str, float, str]],
    tags: Iterable[str],
) -> None:
    """Create a recipe with ``ingredients`` and ``tags``.

    This helper checks if a recipe with the given ``title`` already exists and
    only creates it when missing, making it safe to call repeatedly.
    """

    exists = session.execute(select(Recipe).where(Recipe.title == title)).scalar_one_or_none()
    if exists is not None:
        return

    recipe = Recipe(title=title, servings_default=servings, procedure=procedure)
    session.add(recipe)

    for name, qty, unit in ingredients:
        recipe.ingredients.append(Ingredient(name=name, quantity=qty, unit=unit))

    for tag_name in tags:
        recipe.tags.append(_get_or_create_tag(session, tag_name))


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


__all__ = ["seed_sample_data"]

