"""CRUD operations for the Meals Planner Codex application."""

from __future__ import annotations

from datetime import date
import difflib
import json
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from database import SessionLocal, Base
from mealplanner.config import DEFAULT_PLAN_SETTINGS
from models import (
    CATEGORIES,
    Ingredient,
    MealPlan,
    Meal,
    MealSide,
    Recipe,
    Tag,
    RecipeIngredient,
    UnitEnum,
    User,
    recipe_tag_table,
)

__all__ = [
    "create_user",
    "get_user",
    "get_user_by_email",
    "get_user_by_google_sub",
    "create_recipe",
    "create_ingredient",
    "get_or_create_tag",
    "get_or_create_ingredient",
    "get_recipe",
    "get_ingredient",
    "get_recipes_by_ingredient",
    "find_similar_ingredients",
    "find_duplicate_pairs",
    "merge_ingredients",
    "update_recipe",
    "delete_recipe",
    "delete_ingredient",
    "set_meal_plan",
    "get_plan",
    "delete_meal_plans",
    "remove_leftovers_for_source",
    "get_plan_settings",
    "mark_meal_accepted",
    "add_meal_side",
    "replace_meal_side",
    "remove_meal_side",
    "accept_recipe",
    "reject_recipe",
    "list_recipe_titles",
    "list_planned_titles",
    "import_data",
    "export_data",
    "clear_data",
]


def create_user(
    session: Session,
    *,
    email: str,
    hashed_password: Optional[str] = None,
    display_name: Optional[str] = None,
    auth_provider: str = "local",
    google_sub: Optional[str] = None,
) -> User:
    """Create and persist a :class:`~models.User`."""
    user = User(
        email=email,
        hashed_password=hashed_password,
        display_name=display_name,
        auth_provider=auth_provider,
        google_sub=google_sub,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user(session: Session, user_id: int) -> Optional[User]:
    return session.get(User, user_id)


def get_user_by_email(session: Session, email: str) -> Optional[User]:
    return session.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()


def get_user_by_google_sub(session: Session, google_sub: str) -> Optional[User]:
    return session.execute(
        select(User).where(User.google_sub == google_sub)
    ).scalar_one_or_none()


def create_recipe(session: Session, **data: Any) -> Recipe:
    """Create a new :class:`~models.Recipe`.

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


def create_ingredient(
    session: Session,
    name: str,
    unit: UnitEnum | None,
    season_months: List[int],
    categories: List[str] | None = None,
) -> Ingredient:
    """Create and persist a new :class:`Ingredient`."""

    ingredient = Ingredient(
        name=name,
        unit=unit,
        season_months=season_months,
        categories=categories or [],
    )
    session.add(ingredient)
    session.commit()
    session.refresh(ingredient)
    return ingredient


def _normalize_name(name: str) -> str:
    """Normalise an ingredient name for fuzzy comparison.

    Lowercases, strips, collapses internal whitespace, and removes a naive
    trailing plural ``s`` for singularisation.
    """

    normalized = re.sub(r"\s+", " ", name.strip().lower())
    if len(normalized) > 1 and normalized.endswith("s"):
        normalized = normalized[:-1]
    return normalized


def _similarity(a: str, b: str) -> float:
    """Return a 0-1 similarity ratio between two normalised names."""

    x = _normalize_name(a)
    y = _normalize_name(b)
    if x == y:
        return 1.0
    return difflib.SequenceMatcher(None, x, y).ratio()


def find_similar_ingredients(
    session: Session,
    name: str,
    *,
    exclude_id: int | None = None,
    threshold: float = 0.8,
) -> List[Ingredient]:
    """Return ingredients whose name is similar to ``name``.

    Results are sorted by descending similarity score.
    """

    stmt = select(Ingredient)
    if exclude_id is not None:
        stmt = stmt.where(Ingredient.id != exclude_id)
    candidates = session.execute(stmt).scalars().all()
    scored = [
        (other, _similarity(name, other.name)) for other in candidates
    ]
    matches = [(o, s) for o, s in scored if s >= threshold]
    matches.sort(key=lambda pair: pair[1], reverse=True)
    return [o for o, _ in matches]


def find_duplicate_pairs(
    session: Session, *, threshold: float = 0.8
) -> List[Tuple[Ingredient, Ingredient, float]]:
    """Return every candidate duplicate pair of ingredients.

    Compares each unordered pair once and keeps those scoring at or above
    ``threshold``, sorted by descending score.
    """

    ingredients = (
        session.execute(select(Ingredient).order_by(Ingredient.id))
        .scalars()
        .all()
    )
    pairs: List[Tuple[Ingredient, Ingredient, float]] = []
    for i in range(len(ingredients)):
        for j in range(i + 1, len(ingredients)):
            score = _similarity(ingredients[i].name, ingredients[j].name)
            if score >= threshold:
                pairs.append((ingredients[i], ingredients[j], score))
    pairs.sort(key=lambda pair: pair[2], reverse=True)
    return pairs


def merge_ingredients(
    session: Session,
    source_id: int,
    target_id: int,
    *,
    surviving_unit: UnitEnum | None = None,
    conversion_factor: float | None = None,
) -> Ingredient | None:
    """Merge ``source_id`` into ``target_id`` within a single transaction.

    Recipe references to the source are re-pointed to the target (folding into
    an existing target line when the composite PK would collide). When the
    source line's unit differs from ``surviving_unit`` and ``conversion_factor``
    is provided, quantities are converted. Categories and season months are
    unioned onto the target, then the source ingredient is deleted.
    """

    if source_id == target_id:
        raise ValueError("Cannot merge an ingredient into itself")

    source = session.get(Ingredient, source_id)
    target = session.get(Ingredient, target_id)
    if source is None or target is None:
        return None

    source_lines = (
        session.execute(
            select(RecipeIngredient).where(
                RecipeIngredient.ingredient_id == source_id
            )
        )
        .scalars()
        .all()
    )
    for line in source_lines:
        if (
            surviving_unit is not None
            and line.unit != surviving_unit
            and conversion_factor is not None
        ):
            if line.quantity is not None:
                line.quantity *= conversion_factor
            line.unit = surviving_unit

        existing = session.get(RecipeIngredient, (line.recipe_id, target_id))
        if existing is not None:
            if line.quantity is not None:
                existing.quantity = (existing.quantity or 0) + line.quantity
            session.delete(line)
        else:
            line.ingredient_id = target_id
        session.flush()

    if surviving_unit is not None:
        target.unit = surviving_unit

    merged_categories = [
        c for c in CATEGORIES
        if c in (target.categories or []) or c in (source.categories or [])
    ]
    target.categories = merged_categories
    target.season_months = sorted(
        set(target.season_months or []) | set(source.season_months or [])
    )

    session.delete(source)
    session.commit()
    session.refresh(target)
    return target


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
    """Return a :class:`~models.Tag` with ``name``.

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


def get_ingredient(session: Session, ingredient_id: int) -> Ingredient | None:
    """Return an ingredient by primary key or ``None`` if not found."""

    return session.get(Ingredient, ingredient_id)


def get_recipes_by_ingredient(session: Session, ingredient_id: int) -> List[Recipe]:
    """Return all recipes that reference ``ingredient_id``."""

    stmt = (
        select(Recipe)
        .join(RecipeIngredient)
        .where(RecipeIngredient.ingredient_id == ingredient_id)
        .order_by(Recipe.title)
    )
    return session.execute(stmt).scalars().all()


def delete_ingredient(
    session: Session, ingredient_id: int, *, force: bool = False
) -> bool | None:
    """Delete an ingredient by id.

    Parameters
    ----------
    session:
        Database session used for the operation.
    ingredient_id:
        Primary key of the ingredient to remove.
    force:
        When ``True`` the ingredient and any associations are removed even if
        recipes reference it. When ``False`` (the default) the deletion will be
        aborted if the ingredient is still referenced.

    Returns
    -------
    bool | None
        ``True`` if the ingredient was deleted, ``False`` if references prevent
        deletion, or ``None`` if the ingredient was not found.
    """

    ingredient = session.get(Ingredient, ingredient_id)
    if ingredient is None:
        return None

    if not force:
        count = session.scalar(
            select(func.count(RecipeIngredient.recipe_id)).where(
                RecipeIngredient.ingredient_id == ingredient_id
            )
        )
        if count:
            return False

    session.delete(ingredient)
    session.commit()
    return True


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
    # Built meals paired with their leftover hint, fed to _assign_leftover_sources
    # once every day is rebuilt so cross-day links resolve in date order.
    entries: List[tuple] = []
    # Positions whose recipe changed on re-persist, so their now-orphaned
    # leftovers can be cascade-removed after the rebuild.
    replaced_sources: List[tuple] = []

    def _day_key(item):
        day = item[0]
        return day if isinstance(day, date) else date.fromisoformat(day)

    for day, meals in sorted(plan.items(), key=_day_key):
        plan_date = day if isinstance(day, date) else date.fromisoformat(day)
        stmt = select(MealPlan).where(MealPlan.plan_date == plan_date)
        meal_plan = session.execute(stmt).scalar_one_or_none()
        old_recipe_by_number: Dict[int, Optional[int]] = {}
        if meal_plan is None:
            meal_plan = MealPlan(plan_date=plan_date)
            session.add(meal_plan)
            session.flush()
        else:
            old_recipe_by_number = {
                m.meal_number: m.recipe_id for m in meal_plan.meals
            }
            # Flush the delete before re-inserting rows with the same composite
            # PK, otherwise SQLAlchemy issues an UPDATE that leaves unset columns
            # (e.g. a stale leftover link) untouched.
            meal_plan.meals = []
            session.flush()

        new_recipe_by_number: Dict[int, Optional[int]] = {}
        for index, meal in enumerate(meals, start=1):
            if isinstance(meal, int):
                main_id = meal
                side_ids: List[int] = []
                leftover = False
            elif isinstance(meal, dict):
                main_id = meal.get("main_id")
                side_ids = list(meal.get("side_ids", []) or [])
                leftover = bool(meal.get("leftover", False))
            else:
                main_id = getattr(meal, "main_id")
                side_ids = list(getattr(meal, "side_ids", []) or [])
                leftover = bool(getattr(meal, "leftover", False))

            new_recipe_by_number[index] = main_id
            meal_obj = Meal(
                meal_number=index,
                recipe_id=main_id,
                accepted=False,
                sides=[
                    MealSide(position=i + 1, side_recipe_id=sid)
                    for i, sid in enumerate(side_ids)
                ],
            )
            meal_plan.meals.append(meal_obj)
            entries.append((meal_obj, plan_date, index, main_id, leftover))

        # A source position whose recipe changed (or was removed) leaves its
        # leftovers orphaned; schedule them for cascade removal.
        for number, old_recipe in old_recipe_by_number.items():
            if new_recipe_by_number.get(number) != old_recipe:
                replaced_sources.append((plan_date, number))

        plans[day] = meal_plan

    _assign_leftover_sources(entries, session=session)
    for source_date, source_number in replaced_sources:
        remove_leftovers_for_source(session, source_date, source_number)

    session.commit()
    for meal_plan in plans.values():
        session.refresh(meal_plan)
    return plans


def remove_leftovers_for_source(
    session: Session, source_date: date, source_meal: int
) -> int:
    """Delete every leftover meal linked to the given source meal.

    Returns the number of leftover meals removed.
    """

    stmt = select(Meal).where(
        Meal.leftover_source_date == source_date,
        Meal.leftover_source_meal == source_meal,
    )
    leftovers = session.execute(stmt).scalars().all()
    for meal in leftovers:
        session.delete(meal)
    session.flush()
    return len(leftovers)


def _db_source_for(
    session: Session, recipe_id: int, before_date: date
) -> Optional[tuple]:
    """Most recent non-leftover meal of ``recipe_id`` planned before a date."""

    row = session.execute(
        select(Meal.plan_date, Meal.meal_number)
        .where(
            Meal.recipe_id == recipe_id,
            Meal.leftover_source_date.is_(None),
            Meal.plan_date < before_date,
        )
        .order_by(Meal.plan_date.desc(), Meal.meal_number.desc())
        .limit(1)
    ).first()
    return (row[0], row[1]) if row else None


def _assign_leftover_sources(
    entries: Iterable[tuple], session: Optional[Session] = None
) -> None:
    """Link leftover meals to the source meal that produced them.

    ``entries`` is an iterable of ``(meal, plan_date, meal_number, recipe_id,
    is_leftover)`` tuples. Processed in ``(plan_date, meal_number)`` order so a
    leftover resolves to the most recent earlier non-leftover meal of the same
    recipe. When a source is not among ``entries`` and ``session`` is provided,
    it is looked up from the existing plan so a re-persisted day keeps a leftover
    linked to a source on another day. Unresolved leftovers keep both link
    columns ``NULL``.
    """

    last_source: Dict[int, tuple] = {}
    for meal, plan_date, meal_number, recipe_id, is_leftover in sorted(
        entries, key=lambda e: (e[1], e[2])
    ):
        if is_leftover:
            source = last_source.get(recipe_id)
            if source is None and session is not None:
                source = _db_source_for(session, recipe_id, plan_date)
            if source is not None:
                meal.leftover_source_date, meal.leftover_source_meal = source
        else:
            last_source[recipe_id] = (plan_date, meal_number)


def delete_meal_plans(
    session: Session, start_date: date, end_date: date
) -> int:
    """Delete meal plans within ``start_date`` and ``end_date`` inclusive."""

    stmt = select(MealPlan).where(
        MealPlan.plan_date.between(start_date, end_date)
    )
    meal_plans = session.execute(stmt).scalars().all()
    deleted = len(meal_plans)

    for meal_plan in meal_plans:
        session.delete(meal_plan)

    session.commit()

    return deleted


def get_plan(
    session: Session,
    plan_date: Optional[date] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch a plan from the database.

    The database is the single source of truth. When ``start_date`` and
    ``end_date`` are provided, all plans within the inclusive date range are
    returned; otherwise the plan for ``plan_date`` (defaulting to today) is
    returned.
    """

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
                        "leftover": meal.leftover,
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
                "leftover": meal.leftover,
            }
        )
    return result


def get_plan_settings(
    session: Session | None = None, user_id: int | None = None
) -> Dict[str, Any]:
    """Return plan settings.

    For now this returns a copy of :data:`DEFAULT_PLAN_SETTINGS`. The
    ``session`` and ``user_id`` parameters are accepted so that a future
    per-user settings feature can layer stored overrides on top of the
    defaults without changing this call signature.
    """

    return dict(DEFAULT_PLAN_SETTINGS)


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

    position = len(meal.sides) + 1
    meal.sides.append(MealSide(position=position, side_recipe_id=side_id))
    session.commit()
    session.refresh(meal)
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

    old_side_id = meal.sides[index].side_recipe_id
    if old_side_id != side_id:
        old_side = session.get(Recipe, old_side_id)
        if old_side is not None:
            old_side.score = (old_side.score or 0) - 1

    meal.sides[index].side_recipe_id = side_id
    session.commit()
    session.refresh(meal)
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
    return meal


def accept_recipe(
    session: Session, title: str, consumed_date: date
) -> Optional[Recipe]:
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
    recipe.date_last_consumed = consumed_date
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
    recipe.date_last_rejected = date.today()
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


def list_planned_titles(session: Session) -> set[str]:
    """Return the distinct set of main-recipe titles across all persisted plans.

    This replaces the former in-memory ``_PLAN_CACHE`` lookup used when
    suggesting rejection replacements: the DB is the single source of truth.
    """

    stmt = (
        select(Recipe.title)
        .join(Meal, Meal.recipe_id == Recipe.id)
        .distinct()
    )
    return set(session.scalars(stmt).all())


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


def _recipe_from_payload(rec_info: Dict[str, Any], rec_id: Optional[int] = None) -> Recipe:
    """Build a :class:`Recipe` from an import payload entry.

    ``rec_id`` is only supplied when the recipe should keep its original id
    (a brand-new recipe in overwrite mode); otherwise the id is left for the
    database to assign.
    """

    consumed = rec_info.get("date_last_consumed")
    return Recipe(
        id=rec_id,
        title=rec_info["title"],
        servings_default=rec_info["servings_default"],
        procedure=rec_info.get("procedure"),
        bulk_prep=rec_info.get("bulk_prep", False),
        course=rec_info.get("course", "main"),
        image_url=rec_info.get("image_url"),
        score=rec_info.get("score"),
        date_last_consumed=date.fromisoformat(consumed) if consumed else None,
    )


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
        :func:`~database.SessionLocal`.
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
            if mode == "merge":
                tag = get_or_create_tag(session, tag_info["name"])
            else:
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
            # In overwrite mode a brand-new recipe keeps its original id; in
            # every other case (merge, or overwrite of an existing id) a fresh
            # id is assigned. The field values are identical regardless.
            keep_id = (
                mode == "overwrite"
                and rec_id is not None
                and session.get(Recipe, rec_id) is None
            )
            recipe = _recipe_from_payload(rec_info, rec_id if keep_id else None)
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

        imported_meals: List[tuple] = []
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
                imported_meals.append(
                    (meal, pdate, meal.meal_number, rid,
                     bool(meal_info.get("leftover", False)))
                )

        _assign_leftover_sources(imported_meals)
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
        :func:`~database.SessionLocal`.
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
                    "image_url": recipe.image_url,
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
                            "leftover": meal.leftover,
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
