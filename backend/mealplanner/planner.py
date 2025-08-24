"""Meal planning logic for the Meals Planner Codex application."""

from __future__ import annotations

from datetime import date, timedelta
import random
from typing import Dict, Iterable, List, Sequence, Set

from sqlalchemy.orm import Session

from .models import Ingredient, Recipe
from .scoring import score_recipe


def _recipe_to_dict(recipe: Recipe) -> Dict[str, object]:
    """Return a mapping representation of ``recipe`` for scoring functions."""

    return {
        "score": recipe.score,
        "bulk_prep": recipe.bulk_prep,
        "date_last_consumed": recipe.date_last_consumed,
        "ingredients": [
            {
                "season_months": [
                    int(m.strip())
                    for m in (ing.season_months or "").split(",")
                    if m.strip()
                ]
            }
            for ing in recipe.ingredients
        ],
        "tags": [t.name for t in recipe.tags],
    }


def generate_plan(
    session: Session,
    start: date,
    days: int,
    meals_per_day: int,
    keep_days: int = 7,
    bulk_leftovers: bool = True,
    epsilon: float = 0.0,
    tags: Iterable[str] | None = None,
    avoid_tags: Iterable[str] | None = None,
    reduce_tags: Iterable[str] | None = None,
    seasonality_weight: float = 1.0,
    recency_weight: float = 1.0,
    tag_penalty_weight: float = 1.0,
    bulk_bonus_weight: float = 1.0,
) -> Dict[str, List[str]]:
    """Generate a meal plan mapping dates to recipe titles.

    Recipes are filtered and scored using :func:`filter_recipes` and
    :func:`scoring.score_recipe` before being passed to
    :func:`generate_weekly_plan`.  The resulting recipes populate the requested
    timeslots.  Weight parameters adjust the influence of individual scoring
    components.

    ``keep_days`` controls how many days leftover portions from a ``bulk_prep``
    recipe may appear after the initial preparation. Set ``bulk_leftovers`` to
    ``False`` to disable leftover reuse entirely. Parameters are forwarded to
    :func:`filter_recipes` allowing tag-based inclusion, exclusion and
    down-weighting of recipes.
    """

    recipes = session.query(Recipe).all()
    total_slots = days * meals_per_day
    selections: List[tuple[Recipe, bool]] = []
    week = 0
    while len(selections) < total_slots:
        week_start = start + timedelta(days=7 * week)
        season = week_start.month
        available = filter_recipes(
            recipes,
            season=season,
            tags=tags,
            avoid_tags=avoid_tags,
            reduce_tags=reduce_tags,
        )
        scored = sorted(
            available,
            key=lambda r: score_recipe(
                _recipe_to_dict(r),
                today=week_start,
                seasonality_weight=seasonality_weight,
                recency_weight=recency_weight,
                tag_penalty_weight=tag_penalty_weight,
                bulk_bonus_weight=bulk_bonus_weight,
                reduce_tags=reduce_tags or [],
            ),
            reverse=True,
        )

        ordered: List[Recipe] = []
        candidates = scored[:]
        while candidates:
            if epsilon and random.random() < epsilon:
                idx = random.randrange(len(candidates))
                ordered.append(candidates.pop(idx))
            else:
                ordered.append(candidates.pop(0))

        weekly = generate_weekly_plan(
            ordered,
            avoid_tags=avoid_tags,
            reduce_tags=reduce_tags,
            keep_days=keep_days if bulk_leftovers else 1,
            days=min(7, total_slots - len(selections)),
        )
        selections.extend(weekly)
        week += 1

    schedule: Dict[str, List[str]] = {}
    for day_offset in range(days):
        current = start + timedelta(days=day_offset)
        key = current.isoformat()
        schedule[key] = []
        for meal_idx in range(meals_per_day):
            idx = day_offset * meals_per_day + meal_idx
            recipe, leftover = selections[idx]
            title = recipe.title + (" (leftover)" if leftover else "")
            schedule[key].append(title)
    return schedule
    
def _ingredient_in_season(ingredient: Ingredient, month: int) -> bool:
    """Return ``True`` if ``ingredient`` is available in ``month``.

    ``Ingredient.season_months`` stores a comma separated list of month numbers
    (``"1,2,3"``). If the field is empty the ingredient is assumed to be
    available year round.
    """

    if not ingredient.season_months:
        return True
    months = {int(m.strip()) for m in ingredient.season_months.split(",") if m.strip()}
    return month in months


def filter_recipes(
    recipes: Sequence[Recipe],
    season: int | None = None,
    tags: Iterable[str] | None = None,
    avoid_tags: Iterable[str] | None = None,
    reduce_tags: Iterable[str] | None = None,
) -> List[Recipe]:
    """Filter ``recipes`` according to ``season`` and ``tags``.

    Args:
        recipes: Collection of :class:`~mealplanner.models.Recipe` objects.
        season: Optional month number (``1-12``). Only recipes with at least one
            ingredient available in that month are kept.
        tags: Optional iterable of tag names. A recipe must contain at least one
            of these tags to be included.
        avoid_tags: Optional iterable of tag names. Recipes containing any of
            these tags are excluded.
        reduce_tags: Optional iterable of tag names. Recipes containing these
            tags are returned after others so they are less likely to be
            selected.
    """

    tag_set: Set[str] | None = set(tags) if tags else None
    avoid_set: Set[str] = set(avoid_tags or [])
    reduce_set: Set[str] = set(reduce_tags or [])
    primary: List[Recipe] = []
    reduced: List[Recipe] = []
    for recipe in recipes:
        recipe_tags = {t.name for t in recipe.tags}
        if avoid_set and recipe_tags.intersection(avoid_set):
            continue
        if tag_set and not recipe_tags.intersection(tag_set):
            continue
        if season is not None and recipe.ingredients and not any(
            _ingredient_in_season(ing, season) for ing in recipe.ingredients
        ):
            continue
        if reduce_set and recipe_tags.intersection(reduce_set):
            reduced.append(recipe)
        else:
            primary.append(recipe)
    return primary + reduced


def generate_weekly_plan(
    recipes: Sequence[Recipe],
    season: int | None = None,
    tags: Iterable[str] | None = None,
    avoid_tags: Iterable[str] | None = None,
    reduce_tags: Iterable[str] | None = None,
    keep_days: int = 7,
    days: int = 7,
) -> List[tuple[Recipe, bool]]:
    """Generate a list of recipes for ``days`` days.

    Recipes are filtered by ``season`` and tag parameters before planning. Non
    bulk prep recipes appear at most once in the returned list while recipes
    flagged with ``bulk_prep`` may be repeated. When ``keep_days`` is greater than
    one, leftover slots for bulk recipes are inserted immediately after the
    fresh preparation up to ``keep_days - 1`` days.

    Args:
        recipes: Candidate recipes.
        season: Optional month number to filter by seasonal ingredients.
        tags: Optional iterable of required tag names.
        avoid_tags: Tags that must not appear in recipes.
        reduce_tags: Tags that are de-prioritised.
        keep_days: Number of days leftovers may persist.
        days: Number of days to plan for. Defaults to a full week (``7``).

    Raises:
        ValueError: If there are insufficient recipes (including repeats of
            ``bulk_prep`` recipes) to create a plan for ``days`` days.
    """

    available = filter_recipes(
        recipes,
        season=season,
        tags=tags,
        avoid_tags=avoid_tags,
        reduce_tags=reduce_tags,
    )

    non_bulk = [r for r in available if not r.bulk_prep]
    bulk_recipes = [r for r in available if r.bulk_prep]

    plan: List[tuple[Recipe, bool]] = []

    for recipe in non_bulk:
        if len(plan) >= days:
            break
        plan.append((recipe, False))

    if len(plan) == days:
        return plan

    if not bulk_recipes:
        raise ValueError("Not enough recipes to generate a full weekly plan")

    idx = 0
    while len(plan) < days:
        recipe = bulk_recipes[idx % len(bulk_recipes)]
        plan.append((recipe, False))
        leftover_slots = min(keep_days - 1, days - len(plan))
        for _ in range(leftover_slots):
            plan.append((recipe, True))
            if len(plan) >= days:
                break
        idx += 1

    return plan


__all__ = ["generate_plan", "filter_recipes", "generate_weekly_plan"]

