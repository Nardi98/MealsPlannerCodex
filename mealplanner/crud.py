"""CRUD operations for the Meals Planner Codex application."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import MealPlan, MealSlot, Recipe

__all__ = [
    "create_recipe",
    "get_recipe",
    "update_recipe",
    "delete_recipe",
    "set_meal_plan",
    "get_plan",
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


def get_recipes() -> List[str]:
    """Return a list of recipe names.

    This function is a placeholder that represents fetching recipe data from
    a database or external service. It is intentionally left unimplemented so
    that tests can mock it to provide deterministic data.
    """

    raise NotImplementedError("Database access not implemented")


def set_meal_plan(
    session: Session, plan_date: date, plan: Dict[str, Iterable[int]]
) -> MealPlan:
    """Create or replace a meal plan for the given date.

    Parameters
    ----------
    session:
        Database session for persistence.
    plan_date:
        The date this plan applies to.
    plan:
        Mapping of meal times to iterables of recipe IDs.
    """

    stmt = select(MealPlan).where(MealPlan.plan_date == plan_date)
    meal_plan = session.execute(stmt).scalar_one_or_none()
    if meal_plan is None:
        meal_plan = MealPlan(plan_date=plan_date)
        session.add(meal_plan)
        session.flush()
    else:
        meal_plan.slots = []

    for meal_time, recipe_ids in plan.items():
        for rid in recipe_ids:
            meal_plan.slots.append(MealSlot(meal_time=meal_time, recipe_id=rid))

    session.commit()
    session.refresh(meal_plan)
    return meal_plan


def get_plan(session: Session, plan_date: Optional[date] = None) -> Dict[str, List[str]]:
    """Return the meal plan for ``plan_date`` or today if ``None``.

    The returned mapping associates meal times with a list of recipe titles.
    If no plan exists for the requested date an empty dictionary is returned.
    """

    if plan_date is None:
        plan_date = date.today()

    stmt = select(MealPlan).where(MealPlan.plan_date == plan_date)
    meal_plan = session.execute(stmt).scalar_one_or_none()
    if meal_plan is None:
        return {}

    result: Dict[str, List[str]] = {}
    for slot in meal_plan.slots:
        if slot.recipe is None:
            continue
        result.setdefault(slot.meal_time, []).append(slot.recipe.title)
    return result


def import_data(file_obj: Any) -> None:
    """Import data from the given uploaded file object."""
    raise NotImplementedError("Import not implemented")


def export_data() -> str:
    """Export application data and return a serialized representation."""
    raise NotImplementedError("Export not implemented")

