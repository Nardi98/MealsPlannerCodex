"""Scoring utilities for meal plans.

This module contains small helper functions used to calculate a score for a
recipe.  The intent is not to be a perfect representation of real world
preferences, but to provide deterministic behaviour that can be unit tested.

The :func:`score_recipe` function combines several simple signals:

``base score``
    A starting score stored on the recipe.  Missing values default to ``0``.

``seasonality``
    Fraction of ingredients that are in season for the given month.  Each
    ingredient is expected to provide a ``season_months`` list.  Missing data
    contributes ``0``.

``recency``
    Recipes eaten recently receive a negative penalty.  Within 7 days the
    penalty is ``-1``; within 30 days ``-0.5``; older recipes have no penalty.

``bulk bonus``
    Bulk-prepared recipes get a small positive bonus.

The goal of these functions is to keep the logic very lightweight so that unit
tests can exercise edge cases such as missing fields or extreme values.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, Iterable, Optional

RecipeDict = Dict[str, object]


def seasonality_bonus(recipe: RecipeDict, today: Optional[date] = None) -> float:
    """Return a bonus based on the fraction of in-season ingredients.

    Parameters
    ----------
    recipe:
        Mapping describing the recipe.  Ingredients are expected under the
        ``"ingredients"`` key as a sequence of mappings each containing a
        ``"season_months"`` list.
    today:
        Date used to determine the current month.  Defaults to
        :func:`date.today` if not provided.
    """

    today = today or date.today()
    ingredients: Iterable[Dict[str, Iterable[int]]] = recipe.get("ingredients") or []
    ingredients = list(ingredients)
    if not ingredients:
        return 0.0
    month = today.month
    in_season = 0
    for ing in ingredients:
        months = ing.get("season_months") or []
        if month in months:
            in_season += 1
    return in_season / len(ingredients)


def recency_penalty(recipe: RecipeDict, today: Optional[date] = None) -> float:
    """Return a negative penalty based on how recently the recipe was eaten."""

    today = today or date.today()
    last: Optional[date] = recipe.get("date_last_consumed")  # type: ignore[assignment]
    if not last:
        return 0.0
    days = (today - last).days
    if days < 7:
        return -1.0
    if days < 30:
        return -0.5
    return 0.0


def bulk_bonus(recipe: RecipeDict) -> float:
    """Small bonus if the recipe is marked as bulk-prep."""

    return 0.2 if recipe.get("bulk_prep") else 0.0


def tag_penalty(
    recipe: RecipeDict, reduce_tags: Optional[Iterable[str]] = None
) -> float:
    """Return a negative penalty if ``recipe`` contains ``reduce`` tags."""

    if not reduce_tags:
        return 0.0
    recipe_tags = set(recipe.get("tags") or [])
    if recipe_tags.intersection(set(reduce_tags)):
        return -1.0
    return 0.0


def score_recipe(
    recipe: RecipeDict,
    today: Optional[date] = None,
    *,
    weights: Optional[Dict[str, float]] = None,
    reduce_tags: Optional[Iterable[str]] = None,
) -> float:
    """Compute the overall score for ``recipe``.

    The scoring is intentionally straightforward: add the base score to the
    weighted results of :func:`seasonality_bonus`, :func:`recency_penalty`,
    :func:`bulk_bonus` and :func:`tag_penalty`.
    """

    today = today or date.today()
    weights = weights or {}
    base = recipe.get("score") or 0.0
    total = float(base)
    total += weights.get("seasonality", 1.0) * seasonality_bonus(recipe, today)
    total += weights.get("recency", 1.0) * recency_penalty(recipe, today)
    total += weights.get("bulk", 1.0) * bulk_bonus(recipe)
    total += weights.get("tags", 1.0) * tag_penalty(recipe, reduce_tags)
    return total


__all__ = [
    "seasonality_bonus",
    "recency_penalty",
    "bulk_bonus",
    "tag_penalty",
    "score_recipe",
]

