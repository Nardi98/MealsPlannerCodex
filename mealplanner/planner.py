"""Meal planning logic for the Meals Planner Codex application."""

from __future__ import annotations

from typing import Iterable, List, Sequence, Set

from .models import Ingredient, Recipe, Tag


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


__all__ = ["filter_recipes", "generate_weekly_plan"]

