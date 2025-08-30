"""CRUD operations for the Meals Planner Codex application."""

from __future__ import annotations

from datetime import date
import json
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import SessionLocal, Base
from models import (
    Ingredient,
    MealPlan,
    Meal,
    MealSide,
    Recipe,
    Tag,
    RecipeIngredient,
    UnitEnum,
    recipe_tag_table,
)

_PLAN_CACHE: Dict[str, List[Dict[str, Any]]] = {}
_PLAN_SETTINGS: Dict[str, Any] = {}

__all__ = [
    "create_recipe",
    "get_or_create_tag",
    "get_or_create_ingredient",
    "get_recipe",
    "update_recipe",
    "delete_recipe",
    "set_meal_plan",
    "save_plan",
    "get_plan",
    "get_plan_settings",
    "mark_meal_accepted",
    "add_meal_side",
    "replace_meal_side",
    "remove_meal_side",
    "accept_recipe",
    "reject_recipe",
    "list_recipe_titles",
    "import_data",
    "export_data",
    "clear_data",
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
        if attr == "ingredients":
            _update_recipe_ingredients(recipe, value)
        else:
            setattr(recipe, attr, value)

    session.commit()
    session.refresh(recipe)
    return recipe


def _update_recipe_ingredients(
    recipe: Recipe, new_items: List[RecipeIngredient]
) -> None:
    """Synchronise ``recipe.ingredients`` with ``new_items``.

    Existing associations are updated in-place when possible to avoid
    unnecessary deletions. Any ingredients missing from ``new_items`` are
    removed from the recipe.
    """

    existing = {ri.ingredient_id: ri for ri in recipe.ingredients}
    for item in new_items:
        current = existing.pop(item.ingredient_id, None)
        if current is not None:
            current.quantity = item.quantity
            current.unit = item.unit
        else:
            recipe.ingredients.append(item)
    for leftover in existing.values():
        recipe.ingredients.remove(leftover)


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


def get_or_create_tag(session: Session, name: str) -> Tag:
    """Return a :class:`~mealplanner.models.Tag` with ``name``.

    The tag is created and added to the session if it does not already exist.
    The session is flushed so that tags added earlier in the transaction are
    visible to the lookup query.
    """

    session.flush()
    tag = session.execute(select(Tag).where(Tag.name == name)).scalar_one_or_none()
    if tag is None:
        tag = Tag(name=name)
        session.add(tag)
    return tag


def get_or_create_ingredient(
    session: Session,
    ingredient_id: int | None,
    name: str | None,
    unit: UnitEnum | None = None,
) -> Ingredient:
    """Return an :class:`Ingredient` looked up by ``ingredient_id`` or ``name``.

    The ingredient is created and added to the session if it does not already
    exist. The session is flushed so that ingredients added earlier in the
    transaction are visible to lookup queries.
    """

    session.flush()
    if ingredient_id is None and not name:
        raise ValueError("Ingredient requires an id or name")
    ingredient: Ingredient | None = None
    if ingredient_id is not None:
        ingredient = session.get(Ingredient, ingredient_id)
    if ingredient is None and name is not None:
        ingredient = session.execute(
            select(Ingredient).where(Ingredient.name == name)
        ).scalar_one_or_none()
    if ingredient is None:
        ingredient = Ingredient(name=name, unit=unit)
        session.add(ingredient)
    elif ingredient.unit is None and unit is not None:
        ingredient.unit = unit
    return ingredient


def get_recipes() -> List[str]:
    """Return a list of recipe names.

    Titles are loaded directly from the database using a lightweight query.
    ``tests.test_app`` replaces this function with a stub to avoid the database
    dependency during tests, but in normal operation we should perform a real
    query.
    """

    with SessionLocal() as session:
        stmt = select(Recipe.title).order_by(Recipe.title)
        return session.execute(stmt).scalars().all()


def set_meal_plan(
    session: Session, plan: Dict[str, Iterable[Any]]
) -> Dict[str, MealPlan]:
    """Create or replace meal plans for each day in ``plan``.

    Parameters
    ----------
    session:
        Database session for persistence.
    plan:
        Mapping of ISO formatted date strings to iterables describing meals.
        Each meal may be an integer recipe ID (main dish only) or a mapping/
        object with ``main_id`` and optional ``side_ids`` attribute.
        The order of meals within each iterable determines the ``meal_number``
        for the created :class:`Meal` rows.
    """

    plans: Dict[str, MealPlan] = {}
    for day, meals in plan.items():
        plan_date = day if isinstance(day, date) else date.fromisoformat(day)
        stmt = select(MealPlan).where(MealPlan.plan_date == plan_date)
        meal_plan = session.execute(stmt).scalar_one_or_none()
        if meal_plan is None:
            meal_plan = MealPlan(plan_date=plan_date)
            session.add(meal_plan)
            session.flush()
        else:
            meal_plan.meals = []

        for index, meal in enumerate(meals, start=1):
            if isinstance(meal, int):
                main_id = meal
                side_ids: List[int] = []
            elif isinstance(meal, dict):
                main_id = meal.get("main_id")
                side_ids = list(meal.get("side_ids", []) or [])
            else:
                main_id = getattr(meal, "main_id")
                side_ids = list(getattr(meal, "side_ids", []) or [])

            meal_plan.meals.append(
                Meal(
                    meal_number=index,
                    recipe_id=main_id,
                    sides=[
                        MealSide(position=i + 1, side_recipe_id=sid)
                        for i, sid in enumerate(side_ids)
                    ],
                )
            )
        plans[day] = meal_plan

    session.commit()
    for meal_plan in plans.values():
        session.refresh(meal_plan)
    return plans


def save_plan(
    plan: Dict[str, Iterable[Any]],
    *,
    bulk_leftovers: bool | None = None,
    keep_days: int | None = None,
) -> None:
    """Persist ``plan`` and optional metadata in memory for later retrieval."""

    _PLAN_CACHE.clear()
    normalised: Dict[str, List[Dict[str, Any]]] = {}
    for day, meals in plan.items():
        items: List[Dict[str, Any]] = []
        for meal in meals:
            if isinstance(meal, str):
                items.append({"recipe": meal, "side_recipes": [], "accepted": False})
            else:
                side_recipes = meal.get("side_recipes")
                if side_recipes is None:
                    sr = meal.get("side_recipe")
                    side_recipes = [sr] if sr else []
                items.append(
                    {
                        "recipe": meal.get("recipe"),
                        "side_recipes": side_recipes,
                        "accepted": bool(meal.get("accepted", False)),
                    }
                )
        normalised[day] = items
    _PLAN_CACHE.update(normalised)
    if bulk_leftovers is not None:
        _PLAN_SETTINGS["bulk_leftovers"] = bulk_leftovers
    if keep_days is not None:
        _PLAN_SETTINGS["keep_days"] = keep_days


def get_plan(
    session: Session | None = None,
    plan_date: Optional[date] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Return the cached plan or fetch from the database if a session is given.

    When ``start_date`` and ``end_date`` are provided, all plans within the
    inclusive date range are returned.
    """

    if session is None:
        return {
            day: [dict(item) for item in meals] for day, meals in _PLAN_CACHE.items()
        }

    if start_date is not None and end_date is not None:
        stmt = (
            select(MealPlan)
            .where(MealPlan.plan_date.between(start_date, end_date))
            .order_by(MealPlan.plan_date)
        )
        meal_plans = session.execute(stmt).scalars().all()
        result: Dict[str, List[Dict[str, Any]]] = {}
        for meal_plan in meal_plans:
            key = meal_plan.plan_date.isoformat()
            items: List[Dict[str, Any]] = []
            for meal in meal_plan.meals:
                if meal.recipe is None:
                    continue
                items.append(
                    {
                        "recipe": meal.recipe.title,
                        "side_recipes": [
                            ms.side_recipe.title for ms in meal.sides if ms.side_recipe
                        ],
                        "accepted": meal.accepted,
                    }
                )
            result[key] = items
        return result

    if plan_date is None:
        plan_date = date.today()

    stmt = select(MealPlan).where(MealPlan.plan_date == plan_date)
    meal_plan = session.execute(stmt).scalar_one_or_none()
    if meal_plan is None:
        return {}

    key = meal_plan.plan_date.isoformat()
    result: Dict[str, List[Dict[str, Any]]] = {key: []}
    for meal in meal_plan.meals:
        if meal.recipe is None:
            continue
        result[key].append(
            {
                "recipe": meal.recipe.title,
                "side_recipes": [
                    ms.side_recipe.title for ms in meal.sides if ms.side_recipe
                ],
                "accepted": meal.accepted,
            }
        )
    return result


def get_plan_settings() -> Dict[str, Any]:
    """Return cached plan metadata such as ``keep_days``.

    The settings are populated by :func:`save_plan` and stored in-memory only.
    A shallow copy is returned to prevent accidental modification of the
    internal cache.
    """

    return dict(_PLAN_SETTINGS)


def mark_meal_accepted(
    session: Session, plan_date: date, meal_number: int, accepted: bool
) -> Optional[Meal]:
    """Update the acceptance status of a specific meal."""

    stmt = select(Meal).where(
        Meal.plan_date == plan_date, Meal.meal_number == meal_number
    )
    meal = session.execute(stmt).scalar_one_or_none()
    if meal is None:
        return None
    meal.accepted = accepted
    session.commit()
    session.refresh(meal)
    return meal


def add_meal_side(
    session: Session, plan_date: date, meal_number: int, side_id: int
) -> Optional[Meal]:
    """Append a side dish to an existing meal."""

    stmt = select(Meal).where(
        Meal.plan_date == plan_date, Meal.meal_number == meal_number
    )
    meal = session.execute(stmt).scalar_one_or_none()
    if meal is None:
        return None

    if meal.accepted:
        raise ValueError("Meal already accepted")

    if any(ms.side_recipe_id == side_id for ms in meal.sides):
        raise ValueError("Side dish already added")

    position = len(meal.sides) + 1
    meal.sides.append(MealSide(position=position, side_recipe_id=side_id))
    session.commit()
    session.refresh(meal)

    key = plan_date.isoformat()
    meals = _PLAN_CACHE.get(key)
    if meals and 0 < meal_number <= len(meals):
        meals[meal_number - 1]["side_recipes"] = [
            ms.side_recipe.title for ms in meal.sides if ms.side_recipe
        ]
    return meal


def replace_meal_side(
    session: Session, plan_date: date, meal_number: int, index: int, side_id: int
) -> Optional[Meal]:
    """Replace a side dish at ``index`` for a meal."""

    stmt = select(Meal).where(
        Meal.plan_date == plan_date, Meal.meal_number == meal_number
    )
    meal = session.execute(stmt).scalar_one_or_none()
    if meal is None or index >= len(meal.sides):
        return None

    if any(
        ms.side_recipe_id == side_id and i != index
        for i, ms in enumerate(meal.sides)
    ):
        raise ValueError("Side dish already added")

    old_side_id = meal.sides[index].side_recipe_id
    if old_side_id != side_id:
        old_side = session.get(Recipe, old_side_id)
        if old_side is not None:
            old_side.score = (old_side.score or 0) - 1

    meal.sides[index].side_recipe_id = side_id
    session.commit()
    session.refresh(meal)

    key = plan_date.isoformat()
    meals = _PLAN_CACHE.get(key)
    if meals and 0 < meal_number <= len(meals):
        meals[meal_number - 1]["side_recipes"] = [
            ms.side_recipe.title for ms in meal.sides if ms.side_recipe
        ]
    return meal


def remove_meal_side(
    session: Session, plan_date: date, meal_number: int, index: int
) -> Optional[Meal]:
    """Remove a side dish at ``index`` from a meal."""

    stmt = select(Meal).where(
        Meal.plan_date == plan_date, Meal.meal_number == meal_number
    )
    meal = session.execute(stmt).scalar_one_or_none()
    if meal is None or index >= len(meal.sides):
        return None

    meal.sides.pop(index)
    for pos, side in enumerate(meal.sides, start=1):
        side.position = pos

    session.commit()
    session.refresh(meal)

    key = plan_date.isoformat()
    meals = _PLAN_CACHE.get(key)
    if meals and 0 < meal_number <= len(meals):
        meals[meal_number - 1]["side_recipes"] = [
            ms.side_recipe.title for ms in meal.sides if ms.side_recipe
        ]
    return meal


def accept_recipe(session: Session, title: str) -> Optional[Recipe]:
    """Increment ``title``'s score and update ``date_last_consumed``."""

    # ``scalar_one_or_none`` raises ``MultipleResultsFound`` if more than one
    # recipe shares the same title. While titles should ideally be unique,
    # user data might contain duplicates.  Fetch the first matching recipe
    # instead to gracefully handle such cases.
    stmt = select(Recipe).where(Recipe.title == title)
    recipe = session.scalars(stmt).first()
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
    recipe = session.scalars(stmt).first()
    if recipe is None:
        return None
    recipe.score = (recipe.score or 0) - 1
    session.commit()
    session.refresh(recipe)
    return recipe


def list_recipe_titles(session: Session, courses: Sequence[str] | None = None) -> List[str]:
    """Return recipe titles from the database.

    Parameters
    ----------
    session:
        SQLAlchemy session used for the query.
    courses:
        Optional sequence of course names. If provided, only recipes whose
        ``course`` attribute is one of these values will be returned.
    """

    stmt = select(Recipe.title)
    if courses:
        stmt = stmt.where(Recipe.course.in_(courses))
    return session.scalars(stmt).all()


def clear_data(session: Session) -> None:
    """Remove all application data from the database."""

    session.execute(recipe_tag_table.delete())
    session.query(Meal).delete()
    session.query(MealPlan).delete()
    session.query(RecipeIngredient).delete()
    session.query(Ingredient).delete()
    session.query(Tag).delete()
    session.query(Recipe).delete()
    session.commit()
    session.expunge_all()


def import_data(
    file_obj: Any, session: Optional[Session] = None, mode: str = "overwrite"
) -> None:
    """Import data from the given uploaded file object.

    Parameters
    ----------
    file_obj:
        File-like object providing the JSON payload via ``read``.
    session:
        Optional SQLAlchemy session. If omitted a new session is created using
        :func:`~mealplanner.db.SessionLocal`.
    mode:
        Specifies how imported data should be handled. ``"overwrite"`` clears
        existing tables before import, while ``"merge"`` leaves existing data
        intact.
    """

    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    # Ensure database tables exist for this session's engine
    Base.metadata.create_all(bind=session.get_bind())

    try:
        raw = file_obj.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 - broad to rewrap
        if close_session:
            session.close()
        raise ValueError("Malformed import data") from exc

    if mode not in {"overwrite", "merge"}:
        if close_session:
            session.close()
        raise ValueError("mode must be 'overwrite' or 'merge'")

    try:
        if mode == "overwrite":
            clear_data(session)

        tag_map: Dict[int, Tag] = {}
        for tag_info in data.get("tags", []):
            tag_id = tag_info.get("id")
            tag = session.get(Tag, tag_id) if tag_id is not None else None
            if tag is None:
                tag = Tag(id=tag_id, name=tag_info["name"])
                session.add(tag)
            else:
                tag.name = tag_info["name"]
            tag_map[tag_id] = tag

        recipe_id_map: Dict[int, int] = {}
        for rec_info in data.get("recipes", []):
            rec_id = rec_info.get("id")
            existing = session.get(Recipe, rec_id) if rec_id is not None else None
            if existing is None:
                recipe = Recipe(
                    id=rec_id,
                    title=rec_info["title"],
                    servings_default=rec_info["servings_default"],
                    procedure=rec_info.get("procedure"),
                    bulk_prep=rec_info.get("bulk_prep", False),
                    course=rec_info.get("course", "main"),
                    score=rec_info.get("score"),
                    date_last_consumed=(
                        date.fromisoformat(rec_info["date_last_consumed"])
                        if rec_info.get("date_last_consumed")
                        else None
                    ),
                )
            else:
                recipe = Recipe(
                    title=rec_info["title"],
                    servings_default=rec_info["servings_default"],
                    procedure=rec_info.get("procedure"),
                    bulk_prep=rec_info.get("bulk_prep", False),
                    course=rec_info.get("course", "main"),
                    score=rec_info.get("score"),
                    date_last_consumed=(
                        date.fromisoformat(rec_info["date_last_consumed"])
                        if rec_info.get("date_last_consumed")
                        else None
                    ),
                )
            session.add(recipe)
            session.flush()
            if rec_id is not None:
                recipe_id_map[rec_id] = recipe.id

            for ing_info in rec_info.get("ingredients", []):
                months = ing_info.get("season_months")
                if isinstance(months, str):
                    months = [int(m) for m in months.split(",") if m.strip()]
                ingredient_obj = get_or_create_ingredient(
                    session, ing_info.get("id"), ing_info.get("name")
                )
                if months is not None:
                    ingredient_obj.season_months = months
                unit_val = ing_info.get("unit")
                unit = UnitEnum(unit_val) if unit_val else None
                recipe.ingredients.append(
                    RecipeIngredient(
                        ingredient=ingredient_obj,
                        quantity=ing_info.get("quantity"),
                        unit=unit,
                    )
                )

            for tag_id in rec_info.get("tags", []):
                tag = tag_map.get(tag_id)
                if tag is not None:
                    recipe.tags.append(tag)

        for plan_info in data.get("meal_plans", []):
            pdate = date.fromisoformat(plan_info["plan_date"])
            meal_plan = session.get(MealPlan, pdate)
            if meal_plan is None:
                meal_plan = MealPlan(plan_date=pdate)
                session.add(meal_plan)
            else:
                meal_plan.meals.clear()
                session.flush()

            for meal_info in plan_info.get("meals", []):
                rid = meal_info.get("recipe_id")
                rid = recipe_id_map.get(rid, rid)
                meal = Meal(
                    plan_date=pdate,
                    meal_number=meal_info["meal_number"],
                    recipe_id=rid,
                    accepted=meal_info.get("accepted", False),
                )
                meal_plan.meals.append(meal)

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

    # Ensure database tables exist for this session's engine
    Base.metadata.create_all(bind=session.get_bind())

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
                    "course": recipe.course,
                    "score": recipe.score,
                    "date_last_consumed": (
                        recipe.date_last_consumed.isoformat()
                        if recipe.date_last_consumed
                        else None
                    ),
                    "ingredients": [
                        {
                            "id": ri.ingredient.id,
                            "name": ri.ingredient.name,
                            "quantity": ri.quantity,
                            "unit": ri.unit.value if ri.unit else None,
                            "season_months": ri.ingredient.season_months,
                        }
                        for ri in recipe.ingredients
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
                    "plan_date": plan.plan_date.isoformat(),
                    "meals": [
                        {
                            "plan_date": meal.plan_date.isoformat(),
                            "meal_number": meal.meal_number,
                            "recipe_id": meal.recipe_id,
                            "accepted": meal.accepted,
                        }
                        for meal in plan.meals
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
