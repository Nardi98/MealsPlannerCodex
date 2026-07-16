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
from scoping import owned as _owned, scope as _scope
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
    "set_plan_settings",
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
    "meal_item",
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
    user_id: int | None = None,
) -> Ingredient:
    """Create and persist a new :class:`Ingredient`."""

    ingredient = Ingredient(
        name=name,
        unit=unit,
        season_months=season_months,
        categories=categories or [],
        user_id=user_id,
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
    user_id: int | None = None,
) -> List[Ingredient]:
    """Return ingredients whose name is similar to ``name``.

    Results are sorted by descending similarity score, scoped to ``user_id``
    when given.
    """

    stmt = select(Ingredient)
    if exclude_id is not None:
        stmt = stmt.where(Ingredient.id != exclude_id)
    stmt = _scope(stmt, Ingredient.user_id, user_id)
    candidates = session.execute(stmt).scalars().all()
    scored = [
        (other, _similarity(name, other.name)) for other in candidates
    ]
    matches = [(o, s) for o, s in scored if s >= threshold]
    matches.sort(key=lambda pair: pair[1], reverse=True)
    return [o for o, _ in matches]


def find_duplicate_pairs(
    session: Session, *, threshold: float = 0.8, user_id: int | None = None
) -> List[Tuple[Ingredient, Ingredient, float]]:
    """Return every candidate duplicate pair of ingredients.

    Compares each unordered pair once and keeps those scoring at or above
    ``threshold``, sorted by descending score, scoped to ``user_id`` when given.
    """

    stmt = _scope(
        select(Ingredient).order_by(Ingredient.id), Ingredient.user_id, user_id
    )
    ingredients = session.execute(stmt).scalars().all()
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
    user_id: int | None = None,
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
    if not _owned(source, user_id) or not _owned(target, user_id):
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


def get_recipe(
    session: Session, recipe_id: int, user_id: int | None = None
) -> Optional[Recipe]:
    """Return a recipe by primary key, scoped to ``user_id`` when given."""

    recipe = session.get(Recipe, recipe_id)
    return recipe if _owned(recipe, user_id) else None


def update_recipe(
    session: Session, recipe_id: int, user_id: int | None = None, **data: Any
) -> Optional[Recipe]:
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

    recipe = get_recipe(session, recipe_id, user_id)
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


def delete_recipe(
    session: Session, recipe_id: int, user_id: int | None = None
) -> bool:
    """Delete a recipe by primary key, scoped to ``user_id`` when given.

    Returns ``True`` if a recipe was deleted, ``False`` if the id was not
    present (or not owned by ``user_id``)."""

    recipe = get_recipe(session, recipe_id, user_id)
    if recipe is None:
        return False

    session.delete(recipe)
    session.commit()
    return True


def get_or_create_tag(
    session: Session, name: str, user_id: int | None = None
) -> Tag:
    """Return a :class:`~models.Tag` with ``name`` owned by ``user_id``.

    The tag is created and added to the session if it does not already exist
    for that owner. The session is flushed so that tags added earlier in the
    transaction are visible to the lookup query.
    """

    session.flush()
    stmt = _scope(select(Tag).where(Tag.name == name), Tag.user_id, user_id)
    tag = session.execute(stmt).scalar_one_or_none()
    if tag is None:
        tag = Tag(name=name, user_id=user_id)
        session.add(tag)
    return tag


def get_or_create_ingredient(
    session: Session,
    ingredient_id: int | None,
    name: str | None,
    unit: UnitEnum | None = None,
    user_id: int | None = None,
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
        ingredient = get_ingredient(session, ingredient_id, user_id)
    if ingredient is None and name is not None:
        stmt = _scope(
            select(Ingredient).where(Ingredient.name == name),
            Ingredient.user_id,
            user_id,
        )
        ingredient = session.execute(stmt).scalar_one_or_none()
    if ingredient is None:
        ingredient = Ingredient(name=name, unit=unit, user_id=user_id)
        session.add(ingredient)
    elif ingredient.unit is None and unit is not None:
        ingredient.unit = unit
    return ingredient


def get_ingredient(
    session: Session, ingredient_id: int, user_id: int | None = None
) -> Ingredient | None:
    """Return an ingredient by primary key, scoped to ``user_id`` when given."""

    ingredient = session.get(Ingredient, ingredient_id)
    return ingredient if _owned(ingredient, user_id) else None


def get_recipes_by_ingredient(
    session: Session, ingredient_id: int, user_id: int | None = None
) -> List[Recipe]:
    """Return all recipes that reference ``ingredient_id`` (owner-scoped)."""

    stmt = (
        select(Recipe)
        .join(RecipeIngredient)
        .where(RecipeIngredient.ingredient_id == ingredient_id)
        .order_by(Recipe.title)
    )
    stmt = _scope(stmt, Recipe.user_id, user_id)
    return session.execute(stmt).scalars().all()


def delete_ingredient(
    session: Session,
    ingredient_id: int,
    *,
    force: bool = False,
    user_id: int | None = None,
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
    if not _owned(ingredient, user_id):
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
    session: Session, plan: Dict[str, Iterable[Any]], user_id: int
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
    user_id:
        Owner of the plan. Stamped on the :class:`MealPlan` (and cascaded to its
        meals / sides) and used to scope the existing-plan lookup so days are
        replaced per user.
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
        stmt = _scope(
            select(MealPlan).where(MealPlan.plan_date == plan_date),
            MealPlan.user_id,
            user_id,
        )
        meal_plan = session.execute(stmt).scalar_one_or_none()
        old_recipe_by_number: Dict[int, Optional[int]] = {}
        if meal_plan is None:
            meal_plan = MealPlan(plan_date=plan_date, user_id=user_id)
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

    _assign_leftover_sources(entries, session=session, user_id=user_id)
    for source_date, source_number in replaced_sources:
        remove_leftovers_for_source(session, source_date, source_number, user_id)

    session.commit()
    for meal_plan in plans.values():
        session.refresh(meal_plan)
    return plans


def remove_leftovers_for_source(
    session: Session,
    source_date: date,
    source_meal: int,
    user_id: int | None = None,
) -> int:
    """Delete every leftover meal linked to the given source meal.

    Returns the number of leftover meals removed. Scoped to ``user_id`` when
    given so a source only clears its own account's leftovers.
    """

    stmt = select(Meal).where(
        Meal.leftover_source_date == source_date,
        Meal.leftover_source_meal == source_meal,
    )
    stmt = _scope(stmt, Meal.user_id, user_id)
    leftovers = session.execute(stmt).scalars().all()
    for meal in leftovers:
        session.delete(meal)
    session.flush()
    return len(leftovers)


def _db_source_for(
    session: Session,
    recipe_id: int,
    before_date: date,
    user_id: int | None = None,
) -> Optional[tuple]:
    """Most recent non-leftover meal of ``recipe_id`` planned before a date."""

    stmt = (
        select(Meal.plan_date, Meal.meal_number)
        .where(
            Meal.recipe_id == recipe_id,
            Meal.leftover_source_date.is_(None),
            Meal.plan_date < before_date,
        )
        .order_by(Meal.plan_date.desc(), Meal.meal_number.desc())
        .limit(1)
    )
    row = session.execute(_scope(stmt, Meal.user_id, user_id)).first()
    return (row[0], row[1]) if row else None


def _assign_leftover_sources(
    entries: Iterable[tuple],
    session: Optional[Session] = None,
    user_id: int | None = None,
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
                source = _db_source_for(session, recipe_id, plan_date, user_id)
            if source is not None:
                meal.leftover_source_date, meal.leftover_source_meal = source
        else:
            last_source[recipe_id] = (plan_date, meal_number)


def delete_meal_plans(
    session: Session,
    start_date: date,
    end_date: date,
    user_id: int | None = None,
) -> int:
    """Delete meal plans within ``start_date`` and ``end_date`` inclusive.

    Scoped to ``user_id`` when given so a caller only clears its own plans.
    """

    stmt = select(MealPlan).where(
        MealPlan.plan_date.between(start_date, end_date)
    )
    stmt = _scope(stmt, MealPlan.user_id, user_id)
    meal_plans = session.execute(stmt).scalars().all()
    deleted = len(meal_plans)

    for meal_plan in meal_plans:
        session.delete(meal_plan)

    session.commit()

    return deleted


def meal_item(meal: Meal) -> Dict[str, Any]:
    """Serialize a meal into the shape the plan/meal routes return.

    Shared with ``main.py`` so the single-meal routes and :func:`get_plan`
    cannot drift apart on the wire format.
    """

    return {
        "recipe": meal.recipe.title,
        "side_recipes": [
            ms.side_recipe.title for ms in meal.sides if ms.side_recipe
        ],
        "accepted": meal.accepted,
        "leftover": meal.leftover,
    }


def get_plan(
    session: Session,
    plan_date: Optional[date] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    user_id: int | None = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch a plan from the database.

    The database is the single source of truth. When ``start_date`` and
    ``end_date`` are provided, all plans within the inclusive date range are
    returned; otherwise the plan for ``plan_date`` (defaulting to today) is
    returned — an absent single day yields ``{}`` rather than an empty list.
    Scoped to ``user_id`` when given.
    """

    ranged = start_date is not None and end_date is not None
    if ranged:
        where = MealPlan.plan_date.between(start_date, end_date)
    else:
        where = MealPlan.plan_date == (plan_date or date.today())

    stmt = _scope(
        select(MealPlan).where(where).order_by(MealPlan.plan_date),
        MealPlan.user_id,
        user_id,
    )
    return {
        meal_plan.plan_date.isoformat(): [
            meal_item(meal) for meal in meal_plan.meals if meal.recipe is not None
        ]
        for meal_plan in session.execute(stmt).scalars().all()
    }


def get_plan_settings(
    session: Session | None = None, user_id: int | None = None
) -> Dict[str, Any]:
    """Return plan settings for ``user_id`` merged over the shared defaults.

    A copy of :data:`DEFAULT_PLAN_SETTINGS` is returned, with the user's stored
    overrides (``User.plan_settings``) layered on top. When ``session`` or
    ``user_id`` is ``None`` (lower-level callers) the plain defaults are
    returned.
    """

    settings = dict(DEFAULT_PLAN_SETTINGS)
    if session is not None and user_id is not None:
        user = session.get(User, user_id)
        if user is not None:
            settings.update(user.plan_settings or {})
    return settings


def set_plan_settings(
    session: Session, user_id: int, overrides: Dict[str, Any]
) -> Dict[str, Any]:
    """Persist ``overrides`` as ``user_id``'s plan settings and return the merge.

    Only keys present in :data:`DEFAULT_PLAN_SETTINGS` are stored, so callers
    cannot inject arbitrary settings. Returns the same shape as
    :func:`get_plan_settings`.
    """

    user = session.get(User, user_id)
    if user is None:
        raise ValueError("Unknown user")
    user.plan_settings = {
        key: value
        for key, value in overrides.items()
        if key in DEFAULT_PLAN_SETTINGS
    }
    session.commit()
    return get_plan_settings(session, user_id)


def _get_meal(
    session: Session,
    plan_date: date,
    meal_number: int,
    user_id: int | None = None,
) -> Optional[Meal]:
    """Return a single meal by date/number, scoped to ``user_id`` when given."""

    stmt = _scope(
        select(Meal).where(
            Meal.plan_date == plan_date, Meal.meal_number == meal_number
        ),
        Meal.user_id,
        user_id,
    )
    return session.execute(stmt).scalar_one_or_none()


def mark_meal_accepted(
    session: Session,
    plan_date: date,
    meal_number: int,
    accepted: bool,
    user_id: int | None = None,
) -> Optional[Meal]:
    """Update the acceptance status of a specific meal."""

    meal = _get_meal(session, plan_date, meal_number, user_id)
    if meal is None:
        return None
    meal.accepted = accepted
    session.commit()
    session.refresh(meal)
    return meal


def add_meal_side(
    session: Session,
    plan_date: date,
    meal_number: int,
    side_id: int,
    user_id: int | None = None,
) -> Optional[Meal]:
    """Append a side dish to an existing meal."""

    meal = _get_meal(session, plan_date, meal_number, user_id)
    if meal is None:
        return None

    position = len(meal.sides) + 1
    meal.sides.append(MealSide(position=position, side_recipe_id=side_id))
    session.commit()
    session.refresh(meal)
    return meal


def replace_meal_side(
    session: Session,
    plan_date: date,
    meal_number: int,
    index: int,
    side_id: int,
    user_id: int | None = None,
) -> Optional[Meal]:
    """Replace a side dish at ``index`` for a meal."""

    meal = _get_meal(session, plan_date, meal_number, user_id)
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
    session: Session,
    plan_date: date,
    meal_number: int,
    index: int,
    user_id: int | None = None,
) -> Optional[Meal]:
    """Remove a side dish at ``index`` from a meal."""

    meal = _get_meal(session, plan_date, meal_number, user_id)
    if meal is None or index >= len(meal.sides):
        return None

    meal.sides.pop(index)
    for pos, side in enumerate(meal.sides, start=1):
        side.position = pos

    session.commit()
    session.refresh(meal)
    return meal


def accept_recipe(
    session: Session, title: str, consumed_date: date, user_id: int | None = None
) -> Optional[Recipe]:
    """Increment ``title``'s score and update ``date_last_consumed``.

    Scoped to ``user_id`` when given so feedback only touches owned recipes.
    """

    # ``scalar_one_or_none`` raises ``MultipleResultsFound`` if more than one
    # recipe shares the same title. While titles should ideally be unique,
    # user data might contain duplicates.  Fetch the first matching recipe
    # instead to gracefully handle such cases.
    stmt = _scope(
        select(Recipe).where(Recipe.title == title), Recipe.user_id, user_id
    )
    recipe = session.scalars(stmt).first()
    if recipe is None:
        return None
    recipe.score = (recipe.score or 0) + 1
    recipe.date_last_consumed = consumed_date
    session.commit()
    session.refresh(recipe)
    return recipe


def reject_recipe(
    session: Session, title: str, user_id: int | None = None
) -> Optional[Recipe]:
    """Decrement ``title``'s score (scoped to ``user_id`` when given)."""

    stmt = _scope(
        select(Recipe).where(Recipe.title == title), Recipe.user_id, user_id
    )
    recipe = session.scalars(stmt).first()
    if recipe is None:
        return None
    recipe.score = (recipe.score or 0) - 1
    recipe.date_last_rejected = date.today()
    session.commit()
    session.refresh(recipe)
    return recipe


def list_recipe_titles(
    session: Session,
    courses: Sequence[str] | None = None,
    user_id: int | None = None,
) -> List[str]:
    """Return recipe titles from the database.

    Parameters
    ----------
    session:
        SQLAlchemy session used for the query.
    courses:
        Optional sequence of course names. If provided, only recipes whose
        ``course`` attribute is one of these values will be returned.
    user_id:
        When given, only titles owned by that user are returned.
    """

    stmt = select(Recipe.title)
    if courses:
        stmt = stmt.where(Recipe.course.in_(courses))
    stmt = _scope(stmt, Recipe.user_id, user_id)
    return session.scalars(stmt).all()


def list_planned_titles(session: Session, user_id: int | None = None) -> set[str]:
    """Return the distinct set of main-recipe titles across persisted plans.

    This replaces the former in-memory ``_PLAN_CACHE`` lookup used when
    suggesting rejection replacements: the DB is the single source of truth.
    Scoped to ``user_id`` when given.
    """

    stmt = (
        select(Recipe.title)
        .join(Meal, Meal.recipe_id == Recipe.id)
        .distinct()
    )
    stmt = _scope(stmt, Recipe.user_id, user_id)
    return set(session.scalars(stmt).all())


def clear_data(session: Session, user_id: int | None) -> None:
    """Remove application data from the database.

    Scoped to ``user_id`` so a caller only wipes its own recipes, ingredients,
    tags, and plans; system tags are cleared too so a re-import / reset starts
    empty. Passing ``None`` removes *every* user's rows — it has no default
    precisely because forgetting the argument must not silently do that.
    """

    # Association / child rows are keyed by recipe rather than by owner, so they
    # are matched through a subquery over the owned recipes (a correlated
    # subquery, not a materialized id list, to keep it to one statement each).
    owned_recipe_ids = _scope(select(Recipe.id), Recipe.user_id, user_id)
    session.execute(
        recipe_tag_table.delete().where(
            recipe_tag_table.c.recipe_id.in_(owned_recipe_ids)
        )
    )
    # ``synchronize_session=False`` skips the SELECT each DELETE would otherwise
    # issue just to evict rows from the identity map: the ``commit`` below
    # expires every object in the session anyway (``expire_on_commit`` is on),
    # so nothing can be read back stale.
    session.query(RecipeIngredient).filter(
        RecipeIngredient.recipe_id.in_(owned_recipe_ids)
    ).delete(synchronize_session=False)

    # Meals and their sides cascade from MealPlan via the composite FK.
    for model in (MealPlan, Ingredient, Tag, Recipe):
        _scope(session.query(model), model.user_id, user_id).delete(
            synchronize_session=False
        )
    session.commit()


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
    file_obj: Any,
    session: Optional[Session] = None,
    mode: str = "overwrite",
    *,
    user_id: int | None,
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
    user_id:
        Owner stamped on every imported recipe / ingredient / tag / plan. In
        ``"overwrite"`` mode only that user's data is cleared first. Keyword-only
        and without a default, so an unscoped import is always deliberate;
        ``None`` cannot import meal plans (their ``user_id`` is not nullable).
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
            clear_data(session, user_id)

        tag_map: Dict[int, Tag] = {}
        for tag_info in data.get("tags", []):
            tag_id = tag_info.get("id")
            if mode == "merge":
                tag = get_or_create_tag(session, tag_info["name"], user_id)
            else:
                tag = session.get(Tag, tag_id) if tag_id is not None else None
                if tag is None:
                    tag = Tag(id=tag_id, name=tag_info["name"], user_id=user_id)
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
            recipe.user_id = user_id
            session.add(recipe)
            session.flush()
            if rec_id is not None:
                recipe_id_map[rec_id] = recipe.id

            for ing_info in rec_info.get("ingredients", []):
                months = ing_info.get("season_months")
                if isinstance(months, str):
                    months = [int(m) for m in months.split(",") if m.strip()]
                ingredient_obj = get_or_create_ingredient(
                    session, ing_info.get("id"), ing_info.get("name"),
                    user_id=user_id,
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
            meal_plan = session.get(MealPlan, (user_id, pdate))
            if meal_plan is None:
                meal_plan = MealPlan(plan_date=pdate, user_id=user_id)
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

        _assign_leftover_sources(imported_meals, user_id=user_id)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise ValueError("Malformed import data") from exc
    finally:
        if close_session:
            session.close()


def export_data(session: Optional[Session], user_id: int | None) -> str:
    """Export application data and return a serialized representation.

    Parameters
    ----------
    session:
        SQLAlchemy session. If ``None`` a new session is created using
        :func:`~database.SessionLocal`.
    user_id:
        Only that user's recipes / tags / plans are exported. Has no default so
        that exporting every user's data cannot happen by omission; pass ``None``
        to do it deliberately.
    """

    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    # Ensure database tables exist for this session's engine
    Base.metadata.create_all(bind=session.get_bind())

    try:
        recipes_data = []
        recipe_stmt = _scope(select(Recipe), Recipe.user_id, user_id)
        for recipe in session.execute(recipe_stmt).scalars().all():
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
            for tag in session.execute(
                _scope(select(Tag), Tag.user_id, user_id)
            ).scalars().all()
        ]

        meal_plans_data = []
        plan_stmt = _scope(select(MealPlan), MealPlan.user_id, user_id)
        for plan in session.execute(plan_stmt).scalars().all():
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
