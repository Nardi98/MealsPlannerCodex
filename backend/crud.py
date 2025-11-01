"""CRUD operations for the Meals Planner Codex application."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from uuid import uuid4
from typing import Any, Dict, Iterable, List, Optional, Sequence

from fastapi import HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import Base, SessionLocal
from migration_runner import upgrade as run_migrations
from mealplanner.config import DEFAULT_PLAN_SETTINGS
from models import (
    Ingredient,
    MealPlan,
    Meal,
    MealSide,
    Recipe,
    RecipeIngredient,
    Tag,
    UnitEnum,
    User,
    recipe_tag_table,
)

_PLAN_CACHE: Dict[int, Dict[str, List[Dict[str, Any]]]] = {}
_PLAN_SETTINGS: Dict[str, Any] = {}

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

_DEFAULT_USER_EMAIL = os.getenv("DEFAULT_USER_EMAIL", "legacy@example.com")
_DEFAULT_USERNAME = os.getenv("DEFAULT_USERNAME", "legacy")
_DEFAULT_USER_PASSWORD = os.getenv("DEFAULT_USER_PASSWORD", "not-set")

__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "get_user_by_email",
    "get_user_by_username",
    "create_user",
    "authenticate_user",
    "create_recipe",
    "create_ingredient",
    "get_or_create_tag",
    "get_or_create_ingredient",
    "get_recipe",
    "get_ingredient",
    "get_recipes_by_ingredient",
    "get_recipes",
    "update_recipe",
    "delete_recipe",
    "delete_ingredient",
    "set_meal_plan",
    "save_plan",
    "get_plan",
    "delete_meal_plans",
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


def hash_password(password: str) -> str:
    """Hash ``password`` using the configured password context."""

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify ``plain_password`` against ``hashed_password``."""

    if not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except ValueError:  # pragma: no cover - defensive guard
        return False


def create_access_token(
    data: Dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    """Create a signed JWT access token for ``data``."""

    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_user_by_email(session: Session, email: str) -> User | None:
    """Return the user with ``email`` if present."""

    if not email:
        return None
    stmt = select(User).where(User.email == email)
    return session.execute(stmt).scalar_one_or_none()


def get_user_by_username(session: Session, username: str) -> User | None:
    """Return the user with ``username`` if present."""

    if not username:
        return None
    stmt = select(User).where(User.username == username)
    return session.execute(stmt).scalar_one_or_none()


def create_user(session: Session, *, email: str, username: str, password: str) -> User:
    """Create a new :class:`User` enforcing uniqueness constraints."""

    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(password),
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:  # pragma: no cover - exercised in API tests
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with that email or username already exists.",
        ) from exc
    session.refresh(user)
    return user


def authenticate_user(session: Session, identifier: str, password: str) -> User:
    """Authenticate a user via ``identifier`` which may be email or username."""

    user = get_user_by_email(session, identifier)
    if user is None:
        user = get_user_by_username(session, identifier)
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password.",
        )
    return user


def _ensure_user(session: Session, user: User | int | None) -> User:
    """Resolve ``user`` to a persistent :class:`User` instance."""

    if isinstance(user, User):
        if user.id is None:
            session.add(user)
            session.commit()
            session.refresh(user)
        return user
    if isinstance(user, int):
        existing = session.get(User, user)
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return existing

    default = get_user_by_email(session, _DEFAULT_USER_EMAIL)
    if default is None:
        default = User(
            email=_DEFAULT_USER_EMAIL,
            username=_DEFAULT_USERNAME,
            hashed_password=hash_password(_DEFAULT_USER_PASSWORD),
        )
        session.add(default)
        session.commit()
        session.refresh(default)
    return default


def _create_shadow_user(session: Session) -> User:
    """Create an auxiliary user to house legacy duplicate data."""

    legacy_user = _ensure_user(session, None)
    local, _, domain = _DEFAULT_USER_EMAIL.partition("@")
    if not domain:
        domain = "example.com"
    suffix = uuid4().hex
    email = f"{local}+{suffix}@{domain}"
    username = f"{_DEFAULT_USERNAME}-{suffix}"
    shadow = User(
        email=email,
        username=username,
        hashed_password=legacy_user.hashed_password,
    )
    session.add(shadow)
    session.commit()
    session.refresh(shadow)
    return shadow


def _run_migrations_for_session(session: Session) -> None:
    """Ensure the database schema matches the latest Alembic revision."""

    bind = session.get_bind()
    if bind is None:
        return

    run_migrations(bind)


def create_recipe(session: Session, user: User | int | None = None, **data: Any) -> Recipe:
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

    user_obj = _ensure_user(session, user)
    title = data.get("title")
    if user is None and title:
        conflict = session.execute(
            select(Recipe.id).where(Recipe.user_id == user_obj.id, Recipe.title == title)
        ).first()
        if conflict is not None:
            user_obj = _create_shadow_user(session)
    ingredients = data.pop("ingredients", None)
    tags = data.pop("tags", None)

    recipe = Recipe(user_id=user_obj.id, **data)
    if ingredients:
        for item in ingredients:
            item.user_id = user_obj.id
            if item.ingredient is not None:
                item.ingredient.user_id = user_obj.id
            recipe.ingredients.append(item)
    if tags:
        for tag in tags:
            if tag.user_id is None:
                tag.user_id = user_obj.id
            recipe.tags.append(tag)
    session.add(recipe)
    session.commit()
    session.refresh(recipe)
    return recipe


def create_ingredient(
    session: Session,
    name: str,
    unit: UnitEnum | None,
    season_months: List[int],
    *,
    user: User | int | None = None,
) -> Ingredient:
    """Create and persist a new :class:`Ingredient`."""

    user_obj = _ensure_user(session, user)
    ingredient = Ingredient(
        name=name,
        unit=unit,
        season_months=season_months,
        user_id=user_obj.id,
    )
    session.add(ingredient)
    session.commit()
    session.refresh(ingredient)
    return ingredient


def get_recipe(
    session: Session, recipe_id: int, *, user: User | int | None = None
) -> Optional[Recipe]:
    """Return a recipe by primary key or ``None`` if not found."""

    user_obj = _ensure_user(session, user)
    stmt = select(Recipe).where(
        Recipe.id == recipe_id,
        Recipe.user_id == user_obj.id,
    )
    return session.execute(stmt).scalar_one_or_none()


def update_recipe(
    session: Session,
    recipe_id: int,
    *,
    user: User | int | None = None,
    **data: Any,
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

    user_obj = _ensure_user(session, user)
    stmt = select(Recipe).where(
        Recipe.id == recipe_id,
        Recipe.user_id == user_obj.id,
    )
    recipe = session.execute(stmt).scalar_one_or_none()
    if recipe is None:
        return None
    for attr, value in data.items():
        if attr == "ingredients":
            _update_recipe_ingredients(recipe, value, user_obj.id)
        else:
            setattr(recipe, attr, value)

    session.commit()
    session.refresh(recipe)
    return recipe


def _update_recipe_ingredients(
    recipe: Recipe, new_items: List[RecipeIngredient], user_id: int
) -> None:
    """Synchronise ``recipe.ingredients`` with ``new_items``.

    Existing associations are updated in-place when possible to avoid
    unnecessary deletions. Any ingredients missing from ``new_items`` are
    removed from the recipe.
    """

    existing = {ri.ingredient_id: ri for ri in recipe.ingredients}
    for item in new_items:
        item.user_id = user_id
        if item.ingredient is not None:
            item.ingredient.user_id = user_id
        current = existing.pop(item.ingredient_id, None)
        if current is not None:
            current.quantity = item.quantity
            current.unit = item.unit
        else:
            recipe.ingredients.append(item)
    for leftover in existing.values():
        recipe.ingredients.remove(leftover)


def delete_recipe(
    session: Session, recipe_id: int, *, user: User | int | None = None
) -> bool:
    """Delete a recipe by primary key.

    Returns ``True`` if a recipe was deleted, ``False`` if the id was not
    present in the database."""

    user_obj = _ensure_user(session, user)
    stmt = select(Recipe).where(
        Recipe.id == recipe_id,
        Recipe.user_id == user_obj.id,
    )
    recipe = session.execute(stmt).scalar_one_or_none()
    if recipe is None:
        return False

    session.delete(recipe)
    session.commit()
    return True


def get_or_create_tag(
    session: Session, name: str, *, user: User | int | None = None
) -> Tag:
    """Return a :class:`~mealplanner.models.Tag` with ``name``.

    The tag is created and added to the session if it does not already exist.
    The session is flushed so that tags added earlier in the transaction are
    visible to the lookup query.
    """

    user_obj = _ensure_user(session, user)
    session.flush()
    tag = session.execute(
        select(Tag).where(Tag.user_id == user_obj.id, Tag.name == name)
    ).scalar_one_or_none()
    if tag is None:
        tag = Tag(name=name, user_id=user_obj.id)
        session.add(tag)
    return tag


def get_or_create_ingredient(
    session: Session,
    ingredient_id: int | None,
    name: str | None,
    unit: UnitEnum | None = None,
    *,
    user: User | int | None = None,
) -> Ingredient:
    """Return an :class:`Ingredient` looked up by ``ingredient_id`` or ``name``.

    The ingredient is created and added to the session if it does not already
    exist. The session is flushed so that ingredients added earlier in the
    transaction are visible to lookup queries.
    """

    user_obj = _ensure_user(session, user)
    session.flush()
    if ingredient_id is None and not name:
        raise ValueError("Ingredient requires an id or name")
    ingredient: Ingredient | None = None
    if ingredient_id is not None:
        stmt = select(Ingredient).where(
            Ingredient.id == ingredient_id,
            Ingredient.user_id == user_obj.id,
        )
        ingredient = session.execute(stmt).scalar_one_or_none()
    if ingredient is None and name is not None:
        ingredient = session.execute(
            select(Ingredient).where(
                Ingredient.user_id == user_obj.id, Ingredient.name == name
            )
        ).scalar_one_or_none()
    if ingredient is None:
        ingredient = Ingredient(name=name, unit=unit, user_id=user_obj.id)
        session.add(ingredient)
    elif ingredient.unit is None and unit is not None:
        ingredient.unit = unit
    return ingredient


def get_ingredient(
    session: Session, ingredient_id: int, *, user: User | int | None = None
) -> Ingredient | None:
    """Return an ingredient by primary key or ``None`` if not found."""

    user_obj = _ensure_user(session, user)
    stmt = select(Ingredient).where(
        Ingredient.id == ingredient_id,
        Ingredient.user_id == user_obj.id,
    )
    return session.execute(stmt).scalar_one_or_none()


def get_recipes_by_ingredient(
    session: Session, ingredient_id: int, *, user: User | int | None = None
) -> List[Recipe]:
    """Return all recipes that reference ``ingredient_id``."""

    user_obj = _ensure_user(session, user)
    stmt = (
        select(Recipe)
        .join(RecipeIngredient)
        .where(
            RecipeIngredient.ingredient_id == ingredient_id,
            Recipe.user_id == user_obj.id,
            RecipeIngredient.user_id == user_obj.id,
        )
        .order_by(Recipe.title)
    )
    return session.execute(stmt).scalars().all()


def delete_ingredient(
    session: Session,
    ingredient_id: int,
    *,
    force: bool = False,
    user: User | int | None = None,
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

    user_obj = _ensure_user(session, user)
    stmt = select(Ingredient).where(
        Ingredient.id == ingredient_id,
        Ingredient.user_id == user_obj.id,
    )
    ingredient = session.execute(stmt).scalar_one_or_none()
    if ingredient is None:
        return None

    if not force:
        count = session.scalar(
            select(func.count(RecipeIngredient.recipe_id)).where(
                RecipeIngredient.ingredient_id == ingredient_id,
                RecipeIngredient.user_id == user_obj.id,
            )
        )
        if count:
            return False

    session.delete(ingredient)
    session.commit()
    return True


def get_recipes(user: User | int | None = None) -> List[str]:
    """Return a list of recipe names.

    Titles are loaded directly from the database using a lightweight query.
    ``tests.test_app`` replaces this function with a stub to avoid the database
    dependency during tests, but in normal operation we should perform a real
    query.
    """

    with SessionLocal() as session:
        user_obj = _ensure_user(session, user)
        stmt = (
            select(Recipe.title)
            .where(Recipe.user_id == user_obj.id)
            .order_by(Recipe.title)
        )
        return session.execute(stmt).scalars().all()


def set_meal_plan(
    session: Session,
    plan: Dict[str, Iterable[Any]],
    *,
    user: User | int | None = None,
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

    user_obj = _ensure_user(session, user)
    plans: Dict[str, MealPlan] = {}
    for day, meals in plan.items():
        plan_date = day if isinstance(day, date) else date.fromisoformat(day)
        stmt = select(MealPlan).where(
            MealPlan.plan_date == plan_date,
            MealPlan.user_id == user_obj.id,
        )
        meal_plan = session.execute(stmt).scalar_one_or_none()
        if meal_plan is None:
            meal_plan = MealPlan(plan_date=plan_date, user_id=user_obj.id)
            session.add(meal_plan)
            session.flush()
        else:
            meal_plan.meals = []

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

            meal_plan.meals.append(
                Meal(
                    user_id=user_obj.id,
                    plan_date=plan_date,
                    meal_number=index,
                    recipe_id=main_id,
                    accepted=False,
                    leftover=leftover,
                    sides=[
                        MealSide(
                            user_id=user_obj.id,
                            plan_date=plan_date,
                            meal_number=index,
                            position=i + 1,
                            side_recipe_id=sid,
                        )
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
    leftover_repeat_default: int | None = None,
    leftover_repeat_by_recipe: Dict[int, int] | None = None,
    leftover_spacing_gap: int | None = None,
    max_leftovers_per_day: int | None = None,
    max_leftovers_per_week: int | None = None,
    leftover_accept_weight: float | None = None,
    leftover_daypart_pref: Dict[str, float] | None = None,
    leftover_daypart_weight: float | None = None,
    protect_explore_slots: bool | None = None,
    soft_hold_penalty: float | None = None,
    explore_protection_cost: float | None = None,
    meal_number_to_daypart: Dict[int, str] | None = None,
    user: User | int | None = None,
) -> None:
    """Persist ``plan`` and optional metadata in memory for later retrieval."""

    with SessionLocal() as session:
        user_obj = _ensure_user(session, user)
        user_id = user_obj.id

    _PLAN_CACHE[user_id] = {}
    normalised: Dict[str, List[Dict[str, Any]]] = {}
    for day, meals in plan.items():
        items: List[Dict[str, Any]] = []
        for meal in meals:
            if isinstance(meal, str):
                items.append({
                    "recipe": meal,
                    "side_recipes": [],
                    "accepted": False,
                    "leftover": False,
                })
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
                        "leftover": bool(meal.get("leftover", False)),
                    }
                )
        normalised[day] = items
    _PLAN_CACHE[user_id].update(normalised)
    settings: Dict[str, Any] = {
        "bulk_leftovers": bulk_leftovers,
        "keep_days": keep_days,
        "LEFTOVER_REPEAT_DEFAULT": leftover_repeat_default,
        "LEFTOVER_REPEAT_BY_RECIPE": leftover_repeat_by_recipe,
        "LEFTOVER_SPACING_GAP": leftover_spacing_gap,
        "MAX_LEFTOVERS_PER_DAY": max_leftovers_per_day,
        "MAX_LEFTOVERS_PER_WEEK": max_leftovers_per_week,
        "LEFTOVER_ACCEPT_WEIGHT": leftover_accept_weight,
        "LEFTOVER_DAYPART_PREF": leftover_daypart_pref,
        "LEFTOVER_DAYPART_WEIGHT": leftover_daypart_weight,
        "PROTECT_EXPLORE_SLOTS": protect_explore_slots,
        "SOFT_HOLD_PENALTY": soft_hold_penalty,
        "EXPLORE_PROTECTION_COST": explore_protection_cost,
        "MEAL_NUMBER_TO_DAYPART": meal_number_to_daypart,
    }
    for key, value in settings.items():
        if value is not None:
            _PLAN_SETTINGS[key] = value


def delete_meal_plans(
    session: Session,
    start_date: date,
    end_date: date,
    *,
    user: User | int | None = None,
) -> int:
    """Delete meal plans within ``start_date`` and ``end_date`` inclusive."""

    user_obj = _ensure_user(session, user)
    stmt = select(MealPlan).where(
        MealPlan.user_id == user_obj.id,
        MealPlan.plan_date.between(start_date, end_date),
    )
    meal_plans = session.execute(stmt).scalars().all()
    deleted = len(meal_plans)

    for meal_plan in meal_plans:
        session.delete(meal_plan)

    session.commit()

    user_cache = _PLAN_CACHE.get(user_obj.id, {})
    for key in list(user_cache.keys()):
        try:
            key_date = date.fromisoformat(key)
        except ValueError:
            continue
        if start_date <= key_date <= end_date:
            user_cache.pop(key, None)

    if not user_cache:
        _PLAN_CACHE.pop(user_obj.id, None)

    return deleted


def get_plan(
    session: Session | None = None,
    plan_date: Optional[date] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    *,
    user: User | int | None = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Return the cached plan or fetch from the database if a session is given.

    When ``start_date`` and ``end_date`` are provided, all plans within the
    inclusive date range are returned.
    """

    if session is None:
        with SessionLocal() as tmp_session:
            user_obj = _ensure_user(tmp_session, user)
        user_cache = _PLAN_CACHE.get(user_obj.id, {})
        return {
            day: [dict(item) for item in meals] for day, meals in user_cache.items()
        }

    user_obj = _ensure_user(session, user)

    if start_date is not None and end_date is not None:
        stmt = (
            select(MealPlan)
            .where(
                MealPlan.user_id == user_obj.id,
                MealPlan.plan_date.between(start_date, end_date),
            )
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

    stmt = select(MealPlan).where(
        MealPlan.plan_date == plan_date,
        MealPlan.user_id == user_obj.id,
    )
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


def get_plan_settings() -> Dict[str, Any]:
    """Return plan settings merged with defaults.

    Settings are populated by :func:`save_plan` and stored in-memory only.
    Defaults from :mod:`mealplanner.config` are merged to ensure all known
    configuration options are represented.
    """

    return {**DEFAULT_PLAN_SETTINGS, **_PLAN_SETTINGS}


def mark_meal_accepted(
    session: Session,
    plan_date: date,
    meal_number: int,
    accepted: bool,
    *,
    user: User | int | None = None,
) -> Optional[Meal]:
    """Update the acceptance status of a specific meal."""

    user_obj = _ensure_user(session, user)
    stmt = select(Meal).where(
        Meal.plan_date == plan_date,
        Meal.meal_number == meal_number,
        Meal.user_id == user_obj.id,
    )
    meal = session.execute(stmt).scalar_one_or_none()
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
    *,
    user: User | int | None = None,
) -> Optional[Meal]:
    """Append a side dish to an existing meal."""

    user_obj = _ensure_user(session, user)
    stmt = select(Meal).where(
        Meal.plan_date == plan_date,
        Meal.meal_number == meal_number,
        Meal.user_id == user_obj.id,
    )
    meal = session.execute(stmt).scalar_one_or_none()
    if meal is None:
        return None

    position = len(meal.sides) + 1
    meal.sides.append(
        MealSide(
            user_id=user_obj.id,
            plan_date=plan_date,
            meal_number=meal_number,
            position=position,
            side_recipe_id=side_id,
        )
    )
    session.commit()
    session.refresh(meal)

    key = plan_date.isoformat()
    user_cache = _PLAN_CACHE.setdefault(user_obj.id, {})
    meals = user_cache.get(key)
    if meals and 0 < meal_number <= len(meals):
        meals[meal_number - 1]["side_recipes"] = [
            ms.side_recipe.title for ms in meal.sides if ms.side_recipe
        ]
    return meal


def replace_meal_side(
    session: Session,
    plan_date: date,
    meal_number: int,
    index: int,
    side_id: int,
    *,
    user: User | int | None = None,
) -> Optional[Meal]:
    """Replace a side dish at ``index`` for a meal."""

    user_obj = _ensure_user(session, user)
    stmt = select(Meal).where(
        Meal.plan_date == plan_date,
        Meal.meal_number == meal_number,
        Meal.user_id == user_obj.id,
    )
    meal = session.execute(stmt).scalar_one_or_none()
    if meal is None or index >= len(meal.sides):
        return None

    old_side_id = meal.sides[index].side_recipe_id
    if old_side_id != side_id:
        old_side = session.execute(
            select(Recipe).where(
                Recipe.id == old_side_id,
                Recipe.user_id == user_obj.id,
            )
        ).scalar_one_or_none()
        if old_side is not None:
            old_side.score = (old_side.score or 0) - 1

    meal.sides[index].side_recipe_id = side_id
    meal.sides[index].user_id = user_obj.id
    session.commit()
    session.refresh(meal)

    key = plan_date.isoformat()
    user_cache = _PLAN_CACHE.setdefault(user_obj.id, {})
    meals = user_cache.get(key)
    if meals and 0 < meal_number <= len(meals):
        meals[meal_number - 1]["side_recipes"] = [
            ms.side_recipe.title for ms in meal.sides if ms.side_recipe
        ]
    return meal


def remove_meal_side(
    session: Session,
    plan_date: date,
    meal_number: int,
    index: int,
    *,
    user: User | int | None = None,
) -> Optional[Meal]:
    """Remove a side dish at ``index`` from a meal."""

    user_obj = _ensure_user(session, user)
    stmt = select(Meal).where(
        Meal.plan_date == plan_date,
        Meal.meal_number == meal_number,
        Meal.user_id == user_obj.id,
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
    user_cache = _PLAN_CACHE.setdefault(user_obj.id, {})
    meals = user_cache.get(key)
    if meals and 0 < meal_number <= len(meals):
        meals[meal_number - 1]["side_recipes"] = [
            ms.side_recipe.title for ms in meal.sides if ms.side_recipe
        ]
    return meal


def accept_recipe(
    session: Session,
    title: str,
    consumed_date: date,
    *,
    user: User | int | None = None,
) -> Optional[Recipe]:
    """Increment ``title``'s score and update ``date_last_consumed``."""

    # ``scalar_one_or_none`` raises ``MultipleResultsFound`` if more than one
    # recipe shares the same title. While titles should ideally be unique,
    # user data might contain duplicates.  Fetch the first matching recipe
    # instead to gracefully handle such cases.
    user_obj = _ensure_user(session, user)
    stmt = select(Recipe).where(
        Recipe.title == title,
        Recipe.user_id == user_obj.id,
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
    session: Session, title: str, *, user: User | int | None = None
) -> Optional[Recipe]:
    """Decrement ``title``'s score."""

    user_obj = _ensure_user(session, user)
    stmt = select(Recipe).where(
        Recipe.title == title,
        Recipe.user_id == user_obj.id,
    )
    recipe = session.scalars(stmt).first()
    if recipe is None:
        return None
    recipe.score = (recipe.score or 0) - 1
    session.commit()
    session.refresh(recipe)
    return recipe


def list_recipe_titles(
    session: Session,
    courses: Sequence[str] | None = None,
    *,
    user: User | int | None = None,
) -> List[str]:
    """Return recipe titles from the database.

    Parameters
    ----------
    session:
        SQLAlchemy session used for the query.
    courses:
        Optional sequence of course names. If provided, only recipes whose
        ``course`` attribute is one of these values will be returned.
    """

    user_obj = _ensure_user(session, user)
    stmt = select(Recipe.title).where(Recipe.user_id == user_obj.id)
    if courses:
        stmt = stmt.where(Recipe.course.in_(courses))
    return session.scalars(stmt).all()


def clear_data(session: Session, *, user: User | int | None = None) -> None:
    """Remove application data from the database."""

    if user is None:
        session.execute(recipe_tag_table.delete())
        session.query(Meal).delete()
        session.query(MealPlan).delete()
        session.query(RecipeIngredient).delete()
        session.query(Ingredient).delete()
        session.query(Tag).delete()
        session.query(Recipe).delete()
        session.commit()
        session.expunge_all()
        return

    user_obj = _ensure_user(session, user)
    session.execute(
        recipe_tag_table.delete().where(recipe_tag_table.c.user_id == user_obj.id)
    )
    session.query(MealSide).filter(MealSide.user_id == user_obj.id).delete(
        synchronize_session=False
    )
    session.query(Meal).filter(Meal.user_id == user_obj.id).delete(
        synchronize_session=False
    )
    session.query(MealPlan).filter(MealPlan.user_id == user_obj.id).delete(
        synchronize_session=False
    )
    session.query(RecipeIngredient).filter(
        RecipeIngredient.user_id == user_obj.id
    ).delete(synchronize_session=False)
    session.query(Ingredient).filter(Ingredient.user_id == user_obj.id).delete(
        synchronize_session=False
    )
    session.query(Tag).filter(Tag.user_id == user_obj.id).delete(
        synchronize_session=False
    )
    session.query(Recipe).filter(Recipe.user_id == user_obj.id).delete(
        synchronize_session=False
    )
    session.commit()


def import_data(
    file_obj: Any,
    session: Optional[Session] = None,
    mode: str = "overwrite",
    *,
    user: User | int | None = None,
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
    _run_migrations_for_session(session)

    user_obj = _ensure_user(session, user)

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
            clear_data(session, user=user_obj)

        tag_map: Dict[int, Tag] = {}
        for tag_info in data.get("tags", []):
            tag_id = tag_info.get("id")
            if mode == "merge":
                tag = get_or_create_tag(session, tag_info["name"], user=user_obj)
            else:
                tag = (
                    session.execute(
                        select(Tag).where(
                            Tag.id == tag_id,
                            Tag.user_id == user_obj.id,
                        )
                    ).scalar_one_or_none()
                    if tag_id is not None
                    else None
                )
                if tag is None:
                    tag = Tag(
                        id=tag_id,
                        name=tag_info["name"],
                        user_id=user_obj.id,
                    )
                    session.add(tag)
                else:
                    tag.name = tag_info["name"]
            tag_map[tag_id] = tag

        recipe_id_map: Dict[int, int] = {}
        for rec_info in data.get("recipes", []):
            rec_id = rec_info.get("id")
            if mode == "merge":
                recipe = Recipe(
                    user_id=user_obj.id,
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
                existing = (
                    session.execute(
                        select(Recipe).where(
                            Recipe.id == rec_id,
                            Recipe.user_id == user_obj.id,
                        )
                    ).scalar_one_or_none()
                    if rec_id is not None
                    else None
                )
                if existing is None:
                    recipe = Recipe(
                        user_id=user_obj.id,
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
                        user_id=user_obj.id,
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
                    session,
                    ing_info.get("id"),
                    ing_info.get("name"),
                    user=user_obj,
                )
                if months is not None:
                    ingredient_obj.season_months = months
                unit_val = ing_info.get("unit")
                unit = UnitEnum(unit_val) if unit_val else None
                recipe.ingredients.append(
                    RecipeIngredient(
                        user_id=user_obj.id,
                        ingredient=ingredient_obj,
                        quantity=ing_info.get("quantity"),
                        unit=unit,
                    )
                )

            for tag_id in rec_info.get("tags", []):
                tag = tag_map.get(tag_id)
                if tag is not None:
                    if tag.user_id != user_obj.id:
                        continue
                    recipe.tags.append(tag)

        for plan_info in data.get("meal_plans", []):
            pdate = date.fromisoformat(plan_info["plan_date"])
            meal_plan = session.execute(
                select(MealPlan).where(
                    MealPlan.plan_date == pdate,
                    MealPlan.user_id == user_obj.id,
                )
            ).scalar_one_or_none()
            if meal_plan is None:
                meal_plan = MealPlan(plan_date=pdate, user_id=user_obj.id)
                session.add(meal_plan)
            else:
                meal_plan.meals.clear()
                session.flush()

            for meal_info in plan_info.get("meals", []):
                rid = meal_info.get("recipe_id")
                rid = recipe_id_map.get(rid, rid)
                meal = Meal(
                    user_id=user_obj.id,
                    plan_date=pdate,
                    meal_number=meal_info["meal_number"],
                    recipe_id=rid,
                    accepted=meal_info.get("accepted", False),
                    leftover=meal_info.get("leftover", False),
                )
                meal_plan.meals.append(meal)

        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise ValueError("Malformed import data") from exc
    finally:
        if close_session:
            session.close()


def export_data(
    session: Optional[Session] = None, *, user: User | int | None = None
) -> str:
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
    _run_migrations_for_session(session)
    user_obj = _ensure_user(session, user)

    try:
        recipes_data = []
        for recipe in session.execute(
            select(Recipe).where(Recipe.user_id == user_obj.id)
        ).scalars().all():
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
            for tag in session.execute(
                select(Tag).where(Tag.user_id == user_obj.id)
            ).scalars().all()
        ]

        meal_plans_data = []
        for plan in session.execute(
            select(MealPlan).where(MealPlan.user_id == user_obj.id)
        ).scalars().all():
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
