"""CRUD operations for the Meals Planner Codex application."""

from __future__ import annotations

from datetime import date
import json
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Ingredient, MealPlan, MealSlot, Recipe, Tag, recipe_tag_table

_PLAN_CACHE: Dict[str, List[str]] = {}

__all__ = [
    "create_recipe",
    "get_recipe",
    "update_recipe",
    "delete_recipe",
    "set_meal_plan",
    "save_plan",
    "get_plan",
    "accept_recipe",
    "reject_recipe",
    "list_recipe_titles",
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


def save_plan(plan: Dict[str, List[str]]) -> None:
    """Persist ``plan`` in memory for later retrieval."""

    _PLAN_CACHE.clear()
    _PLAN_CACHE.update(plan)


def get_plan(
    session: Session | None = None, plan_date: Optional[date] = None
) -> Dict[str, List[str]]:
    """Return the cached plan or fetch from the database if a session is given."""

    if session is None:
        return dict(_PLAN_CACHE)

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


def accept_recipe(session: Session, title: str) -> Optional[Recipe]:
    """Increment ``title``'s score and update ``date_last_consumed``."""

    stmt = select(Recipe).where(Recipe.title == title)
    recipe = session.execute(stmt).scalar_one_or_none()
    if recipe is None:
        return None
    recipe.score = (recipe.score or 0) + 1
    recipe.date_last_consumed = date.today()
    session.commit()
    session.refresh(recipe)
    return recipe


def reject_recipe(session: Session, title: str) -> Optional[Recipe]:
    """Decrement ``title``'s score."""

    stmt = select(Recipe).where(Recipe.title == title)
    recipe = session.execute(stmt).scalar_one_or_none()
    if recipe is None:
        return None
    recipe.score = (recipe.score or 0) - 1
    session.commit()
    session.refresh(recipe)
    return recipe


def list_recipe_titles(session: Session) -> List[str]:
    """Return all recipe titles from the database."""

    return session.scalars(select(Recipe.title)).all()


def import_data(file_obj: Any, session: Optional[Session] = None) -> None:
    """Import data from the given uploaded file object.

    Parameters
    ----------
    file_obj:
        File-like object providing the JSON payload via ``read``.
    session:
        Optional SQLAlchemy session. If omitted a new session is created using
        :func:`~mealplanner.db.SessionLocal`.
    """

    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        raw = file_obj.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 - broad to rewrap
        if close_session:
            session.close()
        raise ValueError("Malformed import data") from exc

    try:
        # Clear existing data
        session.execute(recipe_tag_table.delete())
        session.query(MealSlot).delete()
        session.query(MealPlan).delete()
        session.query(Ingredient).delete()
        session.query(Tag).delete()
        session.query(Recipe).delete()
        session.commit()
        session.expunge_all()

        tag_map: Dict[int, Tag] = {}
        for tag_info in data.get("tags", []):
            tag = Tag(id=tag_info.get("id"), name=tag_info["name"])
            session.add(tag)
            tag_map[tag.id] = tag

        for rec_info in data.get("recipes", []):
            recipe = Recipe(
                id=rec_info.get("id"),
                title=rec_info["title"],
                servings_default=rec_info["servings_default"],
                procedure=rec_info.get("procedure"),
                bulk_prep=rec_info.get("bulk_prep", False),
                score=rec_info.get("score"),
                date_last_consumed=(
                    date.fromisoformat(rec_info["date_last_consumed"])
                    if rec_info.get("date_last_consumed")
                    else None
                ),
            )
            session.add(recipe)

            for ing_info in rec_info.get("ingredients", []):
                ingredient = Ingredient(
                    id=ing_info.get("id"),
                    name=ing_info["name"],
                    quantity=ing_info.get("quantity"),
                    unit=ing_info.get("unit"),
                    season_months=ing_info.get("season_months"),
                    recipe=recipe,
                )
                session.add(ingredient)

            for tag_id in rec_info.get("tags", []):
                tag = tag_map.get(tag_id)
                if tag is not None:
                    recipe.tags.append(tag)

        for plan_info in data.get("meal_plans", []):
            meal_plan = MealPlan(
                id=plan_info.get("id"),
                plan_date=date.fromisoformat(plan_info["plan_date"]),
            )
            session.add(meal_plan)
            for slot_info in plan_info.get("slots", []):
                slot = MealSlot(
                    meal_time=slot_info["meal_time"],
                    recipe_id=slot_info.get("recipe_id"),
                )
                meal_plan.slots.append(slot)

        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise ValueError("Malformed import data") from exc
    finally:
        if close_session:
            session.close()


def export_data(session: Optional[Session] = None) -> str:
    """Export application data and return a serialized representation.

    Parameters
    ----------
    session:
        Optional SQLAlchemy session. If omitted a new session is created using
        :func:`~mealplanner.db.SessionLocal`.
    """

    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        recipes_data = []
        for recipe in session.execute(select(Recipe)).scalars().all():
            recipes_data.append(
                {
                    "id": recipe.id,
                    "title": recipe.title,
                    "servings_default": recipe.servings_default,
                    "procedure": recipe.procedure,
                    "bulk_prep": recipe.bulk_prep,
                    "score": recipe.score,
                    "date_last_consumed": (
                        recipe.date_last_consumed.isoformat()
                        if recipe.date_last_consumed
                        else None
                    ),
                    "ingredients": [
                        {
                            "id": ing.id,
                            "name": ing.name,
                            "quantity": ing.quantity,
                            "unit": ing.unit,
                            "season_months": ing.season_months,
                        }
                        for ing in recipe.ingredients
                    ],
                    "tags": [tag.id for tag in recipe.tags],
                }
            )

        tags_data = [
            {"id": tag.id, "name": tag.name}
            for tag in session.execute(select(Tag)).scalars().all()
        ]

        meal_plans_data = []
        for plan in session.execute(select(MealPlan)).scalars().all():
            meal_plans_data.append(
                {
                    "id": plan.id,
                    "plan_date": plan.plan_date.isoformat(),
                    "slots": [
                        {
                            "meal_time": slot.meal_time,
                            "recipe_id": slot.recipe_id,
                        }
                        for slot in plan.slots
                    ],
                }
            )

        payload = {
            "recipes": recipes_data,
            "tags": tags_data,
            "meal_plans": meal_plans_data,
        }
        return json.dumps(payload)
    finally:
        if close_session:
            session.close()

