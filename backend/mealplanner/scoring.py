"""Scoring utilities for meal plans.

This module contains small helper functions used to calculate a score for a
recipe.  The intent is not to be a perfect representation of real world
preferences, but to provide deterministic behaviour that can be unit tested.

The :func:`score_recipe` function combines several simple signals:

``base score``
    A starting score stored on the recipe.  The raw value is normalised against
    per-user statistics and then squashed into a bounded contribution so that
    extreme values cannot overwhelm the other components.

``seasonality``
    Fraction of ingredients that are in season for the given month.  Each
    ingredient is expected to provide a ``season_months`` list.  Missing data
    contributes ``0``.

``recency``
    Recipes eaten recently receive a negative penalty.  The penalty starts at
    ``-10`` for a recipe eaten today and decreases in magnitude proportionally
    to the number of days since it was last consumed.

``bulk bonus``
    Bulk-prepared recipes get a small positive bonus.

The goal of these functions is to keep the logic very lightweight so that unit
tests can exercise edge cases such as missing fields or extreme values.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Callable, Dict, Iterable, Optional, Any

RecipeDict = Dict[str, object]

# Tunables
RECENCY_WINDOW_DAYS = 15.0        # after 30 days, no penalty
RECENCY_MAX_PENALTY = 30.0        # strength of the penalty when very recent
HALF_LIFE_DAYS = 4.0              # penalty halves every 7 days


def recency_penalty(recipe: RecipeDict, planned_date: date) -> float:
    """
    Compute a penalty if a recipe was used too recently compared to the planned date.
    Both last_date and planned_date must be actual date objects (not None).
    """

    # Days since recipe was last used relative to planned date
    days = (planned_date - recipe.get("date_last_planned")).days
    days = abs(days)
    # If planning in the past or same day, force strong penalty
    if days == 0:
        return -RECENCY_MAX_PENALTY * 2.0

    # No penalty after the recency window
    if days >= RECENCY_WINDOW_DAYS:
        return 0.0

    # Exponential decay toward 0 as days increase
    penalty = RECENCY_MAX_PENALTY * math.exp(-math.log(2) * days / HALF_LIFE_DAYS)
    return -max(penalty, 0.0)



def seasonality_bonus(recipe: RecipeDict, today: Optional[date] = None) -> float:
    today = today or date.today()

    # Try ORM attributes first: prefer 'ingredients' (your model), then fallback
    items = getattr(recipe, "ingredients", None)
    if items is None:
        items = getattr(recipe, "recipe_ingredients", None)

    # Mapping fallback
    if items is None and hasattr(recipe, "get"):
        items = recipe.get("ingredients") or []

    items = list(items or [])
    if not items:
        return 0.0

    month = today.month
    in_season = 0
    for ri in items:
        # Works with ORM association objects or mapping dicts
        if hasattr(ri, "ingredient"):
            months = getattr(ri.ingredient, "season_months", []) or []
        else:
            months = ri.get("season_months") or []
        if len(months) < 12:
            if month in months:
                print("it is in season")
                in_season += 1
            else:
                in_season -=2
    return 10 * in_season / len(items)




def bulk_bonus(recipe: RecipeDict) -> float:
    """Small bonus if the recipe is marked as bulk-prep."""

    return 10 if recipe.get("bulk_prep") else 0.0


def tag_penalty(
    recipe: RecipeDict,
    reduce_tags: Iterable[str],
    penalty: float = 3,
) -> float:
    """Return a negative penalty if ``recipe`` contains any ``reduce_tags``.

    Parameters
    ----------
    recipe:
        Mapping describing the recipe.  Tags are expected under the ``"tags"``
        key as a sequence of strings.
    reduce_tags:
        Iterable of tag names that should incur a penalty if present.
    penalty:
        Amount to subtract from the score when a matching tag is found.
    """

    recipe_tags = {t.lower() for t in recipe.get("tags", [])}
    targets = {t.lower() for t in reduce_tags}
    if recipe_tags.intersection(targets):
        return -float(penalty)
    return 0.0


def score_recipe(
    recipe: RecipeDict,
    planning_date: date,
    *,
    seasonality_weight: float = 1.0,
    recency_weight: float = 1.0,
    tag_penalty_weight: float = 1.0,
    bulk_bonus_weight: float = 1.0,
    reduce_tags: Iterable[str] | None = None,
    base_scores: Iterable[float] | None = None,
    squash_mode: str = "zscore",
    B: float = 3.0,
    k: float = 1.0
) -> float:
    """Compute the overall score for ``recipe``.

    Individual components are scaled by weights allowing callers to influence
    their impact on the final score.  The raw ``recipe['score']`` is normalised
    according to ``squash_mode`` using ``base_scores`` and then squashed via a
    ``tanh`` function into ``[-B, B]`` before being combined with the other
    signals.

    Parameters
    ----------
    recipe:
        Mapping describing the recipe.
    planning_date:
        Date used for seasonality and recency calculations.
    seasonality_weight, recency_weight, tag_penalty_weight, bulk_bonus_weight:
        Multipliers applied to their respective components.
    reduce_tags:
        Tags that should incur a penalty if present.
    base_scores:
        Iterable of historical base scores for the user.  Used to compute
        normalisation statistics.
    squash_mode:
        Normalisation strategy: ``"zscore"`` or ``"percentile"``.
    B:
        Maximum absolute contribution from the base score after squashing.
    k:
        Sharpness of the ``tanh`` squashing function.
    """

    planning_date = planning_date


    # Normalise the raw base score using per-user statistics then squash into a
    # bounded contribution so that extreme values cannot dominate the final
    # score.
    raw_base = float(recipe.get("score") or 0.0)
    data = list(base_scores or [])
    if squash_mode == "zscore":
        mean = sum(data) / len(data) if data else 0.0
        if data and len(data) > 1:
            variance = sum((s - mean) ** 2 for s in data) / len(data)
            std = variance ** 0.5
        else:
            std = 1.0
        norm = (raw_base - mean) / std if std else 0.0
    elif squash_mode == "percentile":
        if data:
            data.sort()
            from bisect import bisect_left

            idx = bisect_left(data, raw_base)
            percentile = idx / len(data)
            norm = 2 * percentile - 1
        else:
            norm = 0.0
    else:
        raise ValueError(f"Unknown squash_mode: {squash_mode}")

    base = B * math.tanh(k * norm)

    total = base
    total += seasonality_weight * seasonality_bonus(recipe, planning_date)
    total += recency_weight * recency_penalty(recipe, planning_date)
    total += bulk_bonus_weight * bulk_bonus(recipe)
    total += tag_penalty_weight * tag_penalty(recipe, reduce_tags or [])
    return total


__all__ = [
    "seasonality_bonus",
    "recency_penalty",
    "bulk_bonus",
    "tag_penalty",
    "score_recipe",
]

