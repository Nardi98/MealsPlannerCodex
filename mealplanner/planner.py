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
    }


def generate_plan(
    session: Session,
    start: date,
    days: int,
    meals_per_day: int,
    epsilon: float = 0.0,
    tags: Iterable[str] | None = None,
) -> Dict[str, List[str]]:
    """Generate a meal plan mapping dates to recipe titles.

    Recipes are filtered and scored using :func:`filter_recipes` and
    :func:`scoring.score_recipe` before being passed to
    :func:`generate_weekly_plan`.  The resulting recipes populate the requested
    timeslots.
    """

    recipes = session.query(Recipe).all()
    total_slots = days * meals_per_day
    selections: List[Recipe] = []
    week = 0
    while len(selections) < total_slots:
        week_start = start + timedelta(days=7 * week)
        season = week_start.month
        available = filter_recipes(recipes, season=season, tags=tags)
        scored = sorted(
            available,
            key=lambda r: score_recipe(_recipe_to_dict(r), today=week_start)
            + (random.uniform(-epsilon, epsilon) if epsilon else 0.0),
            reverse=True,
        )
        weekly = generate_weekly_plan(scored)
        selections.extend(weekly)
        week += 1

    schedule: Dict[str, List[str]] = {}
    for day_offset in range(days):
        current = start + timedelta(days=day_offset)
        key = current.isoformat()
        schedule[key] = []
        for meal_idx in range(meals_per_day):
            idx = day_offset * meals_per_day + meal_idx
            schedule[key].append(selections[idx].title)
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
) -> List[Recipe]:
    """Filter ``recipes`` according to ``season`` and ``tags``.

    Args:
        recipes: Collection of :class:`~mealplanner.models.Recipe` objects.
        season: Optional month number (``1-12``). Only recipes with at least one
            ingredient available in that month are kept.
        tags: Optional iterable of tag names. A recipe must contain at least one
            of these tags to be included.
    """

    tag_set: Set[str] | None = set(tags) if tags else None
    filtered: List[Recipe] = []
    for recipe in recipes:
        if tag_set:
            if not {t.name for t in recipe.tags}.intersection(tag_set):
                continue
        if season is not None:
            if recipe.ingredients and not any(
                _ingredient_in_season(ing, season) for ing in recipe.ingredients
            ):
                continue
        filtered.append(recipe)
    return filtered


def generate_weekly_plan(
    recipes: Sequence[Recipe],
    season: int | None = None,
    tags: Iterable[str] | None = None,
) -> List[Recipe]:
    """Generate a list of seven recipes for the week.

    Recipes are filtered by ``season`` and ``tags`` before planning. Non bulk
    prep recipes appear at most once in the returned list while recipes flagged
    with ``bulk_prep`` may be repeated to fill any remaining days.

    Raises:
        ValueError: If there are insufficient recipes (including repeats of
            ``bulk_prep`` recipes) to create a seven day plan.
    """

    available = filter_recipes(recipes, season=season, tags=tags)
    plan: List[Recipe] = []

    # First use non bulk-prep recipes exactly once
    for recipe in available:
        if not recipe.bulk_prep and recipe not in plan:
            plan.append(recipe)
        if len(plan) == 7:
            return plan

    # Fill remaining slots with bulk-prep recipes allowing repeats
    bulk_recipes = [r for r in available if r.bulk_prep]
    idx = 0
    while len(plan) < 7 and bulk_recipes:
        plan.append(bulk_recipes[idx % len(bulk_recipes)])
        idx += 1

    if len(plan) < 7:
        raise ValueError("Not enough recipes to generate a full weekly plan")

    return plan


__all__ = ["generate_plan", "filter_recipes", "generate_weekly_plan"]

