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
    Recipes planned recently receive a negative penalty.  The penalty is
    strongest (``-RECENCY_MAX_PENALTY``) for a recipe planned today, decays
    exponentially with a ``HALF_LIFE_DAYS`` half-life, and disappears once the
    gap reaches ``RECENCY_WINDOW_DAYS``.  A recipe last planned *after* the
    planning date is not yet consumed and receives no penalty.

``bulk bonus``
    Bulk-prepared recipes get a small positive bonus.

The goal of these functions is to keep the logic very lightweight so that unit
tests can exercise edge cases such as missing fields or extreme values.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Dict, Iterable, Optional

RecipeDict = Dict[str, object]

# Tunables
RECENCY_WINDOW_DAYS = 15.0        # no penalty once the gap reaches this many days
RECENCY_MAX_PENALTY = 30.0        # strength of the penalty when planned today
HALF_LIFE_DAYS = 4.0              # penalty halves every this many days
SEASONALITY_BONUS_SCALE = 10.0    # magnitude of a fully in/out-of-season recipe
BULK_PREP_BONUS = 10.0            # bonus applied to bulk-prep recipes
DEFAULT_TAG_PENALTY = 3.0         # default penalty for a matching reduce-tag


def recency_penalty(recipe: RecipeDict, planned_date: date) -> float:
    """Penalise recipes planned recently relative to ``planned_date``.

    ``date_last_planned`` must be an actual :class:`date` (not ``None``). The
    penalty is ``-RECENCY_MAX_PENALTY`` on the planning day itself, decays with
    a ``HALF_LIFE_DAYS`` half-life, and is ``0`` once the gap reaches
    ``RECENCY_WINDOW_DAYS``. A recipe last planned *after* ``planned_date`` has
    not been consumed yet, so it receives no penalty.
    """

    # Days between the last time the recipe was planned and this slot. Negative
    # means it is planned in the future relative to this slot -> not consumed.
    days = (planned_date - recipe.get("date_last_planned")).days
    if days < 0:
        return 0.0

    # Same-day: strongest penalty.
    if days == 0:
        return -RECENCY_MAX_PENALTY

    # No penalty after the recency window.
    if days >= RECENCY_WINDOW_DAYS:
        return 0.0

    # Exponential decay toward 0 as days increase.
    penalty = RECENCY_MAX_PENALTY * math.exp(-math.log(2) * days / HALF_LIFE_DAYS)
    return -max(penalty, 0.0)


def seasonality_bonus(recipe: RecipeDict, today: Optional[date] = None) -> float:
    """Reward recipes whose ingredients are in season for ``today``'s month.

    Each ingredient with meaningful seasonal data (``0 < len(season_months) <
    12``) votes ``+1`` when in season and ``-1`` when out of season. Ingredients
    with no data or available all year round are neutral (they contribute ``0``,
    matching the module docstring). The net vote is scaled by
    ``SEASONALITY_BONUS_SCALE`` and averaged over all ingredients, so a recipe
    that is fully in season scores ``+SEASONALITY_BONUS_SCALE`` and one fully
    out of season scores ``-SEASONALITY_BONUS_SCALE``.
    """

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
    net = 0
    for ri in items:
        # Works with ORM association objects or mapping dicts
        if hasattr(ri, "ingredient"):
            months = getattr(ri.ingredient, "season_months", []) or []
        else:
            months = ri.get("season_months") or []
        # Skip ingredients without meaningful seasonal data (missing or all-year).
        if not months or len(months) >= 12:
            continue
        net += 1 if month in months else -1
    return SEASONALITY_BONUS_SCALE * net / len(items)


def bulk_bonus(recipe: RecipeDict) -> float:
    """Small bonus if the recipe is marked as bulk-prep."""

    return BULK_PREP_BONUS if recipe.get("bulk_prep") else 0.0


def tag_penalty(
    recipe: RecipeDict,
    reduce_tags: Iterable[str],
    penalty: float = DEFAULT_TAG_PENALTY,
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
    "SEASONALITY_BONUS_SCALE",
    "BULK_PREP_BONUS",
    "DEFAULT_TAG_PENALTY",
]
