"""CRUD operations for the Meals Planner Codex application."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from .models import Recipe

__all__ = [
    "create_recipe",
    "get_recipe",
    "update_recipe",
    "delete_recipe",
]


def create_recipe(session: Session, **data: Any) -> Recipe:
    """Create a new :class:`~mealplanner.models.Recipe`.

    Parameters
    ----------
    session:
        SQLAlchemy session used for persisting the object.
    **data:
        Fields to initialise the :class:`Recipe` with. At minimum ``title`` and
        ``servings_default`` should be supplied.

    Returns
    -------
    Recipe
        The newly created and persisted recipe instance.
    """

    recipe = Recipe(**data)
    session.add(recipe)
    session.commit()
    session.refresh(recipe)
    return recipe


def get_recipe(session: Session, recipe_id: int) -> Optional[Recipe]:
    """Return a recipe by primary key or ``None`` if not found."""

    return session.get(Recipe, recipe_id)


def update_recipe(session: Session, recipe_id: int, **data: Any) -> Optional[Recipe]:
    """Update fields on an existing recipe.

    Parameters
    ----------
    session:
        SQLAlchemy session used for database interaction.
    recipe_id:
        Primary key of the recipe to update.
    **data:
        Mapping of attribute names to their new values.
    """

    recipe = session.get(Recipe, recipe_id)
    if recipe is None:
        return None

    for attr, value in data.items():
        setattr(recipe, attr, value)

    session.commit()
    session.refresh(recipe)
    return recipe


def delete_recipe(session: Session, recipe_id: int) -> bool:
    """Delete a recipe by primary key.

    Returns ``True`` if a recipe was deleted, ``False`` if the id was not
    present in the database."""

    recipe = session.get(Recipe, recipe_id)
    if recipe is None:
        return False

    session.delete(recipe)
    session.commit()
    return True

