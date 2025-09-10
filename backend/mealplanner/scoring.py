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
from typing import Callable, Dict, Iterable, Optional

RecipeDict = Dict[str, object]


def seasonality_bonus(recipe: RecipeDict, today: Optional[date] = None) -> float:
    """Return a bonus based on the fraction of in-season ingredients.

    The function accepts either a mapping as produced by
    :func:`mealplanner.planner._recipe_to_dict` or an object providing a
    ``recipe_ingredients`` attribute.  Each recipe ingredient must link to an
    :class:`~mealplanner.models.Ingredient` supplying ``season_months`` data.

    Parameters
    ----------
    recipe:
        Mapping or object describing the recipe.
    today:
        Date used to determine the current month.  Defaults to
        :func:`date.today` if not provided.
    """

    today = today or date.today()

    items = getattr(recipe, "recipe_ingredients", None)
    if items is None and hasattr(recipe, "get"):
        items = recipe.get("ingredients") or []
    items = list(items or [])
    if not items:
        return 0.0
    month = today.month
    in_season = 0
    for ri in items:
        if hasattr(ri, "ingredient"):
            months = getattr(ri.ingredient, "season_months", []) or []
        else:
            months = ri.get("season_months") or []  # type: ignore[assignment]
        if month in months:
            in_season += 1
    return in_season / len(items)


def recency_penalty(recipe: RecipeDict, today: Optional[date] = None) -> float:
    """Return a negative penalty based on how recently the recipe was eaten.

    The penalty is computed as ``-10 / days`` where ``days`` is the number of
    days since the recipe was last planned.  A minimum of one day is enforced
    to avoid division by zero and to ensure future dates still incur the
    maximum penalty of ``-10``.
    """

    today = today or date.today()
    last: Optional[date] = recipe.get("date_last_planned")  # type: ignore[assignment]
    if not last:
        return 0.0
    days = max((today - last).days, 1)
    return -10.0 / days


def bulk_bonus(recipe: RecipeDict) -> float:
    """Small bonus if the recipe is marked as bulk-prep."""

    return 0.2 if recipe.get("bulk_prep") else 0.0


def tag_penalty(
    recipe: RecipeDict,
    reduce_tags: Iterable[str],
    penalty: float = 0.5,
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
    today: Optional[date] = None,
    *,
    seasonality_weight: float = 1.0,
    recency_weight: float = 1.0,
    tag_penalty_weight: float = 1.0,
    bulk_bonus_weight: float = 1.0,
    reduce_tags: Iterable[str] | None = None,
    base_scores: Iterable[float] | None = None,
    squash_mode: str = "zscore",
    B: float = 3.0,
    k: float = 1.0,
    recency_penalty_fn: Callable[[RecipeDict, Optional[date]], float] | None = None,
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
    today:
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

    today = today or date.today()
    recency_penalty_fn = recency_penalty_fn or recency_penalty

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
    total += seasonality_weight * seasonality_bonus(recipe, today)
    total += recency_weight * recency_penalty_fn(recipe, today)
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

