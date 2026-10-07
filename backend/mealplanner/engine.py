"""The selection engine every recipe-proposing path goes through.

Fixed stages, each testable on its own with plain values (no database, no ORM):

1. :func:`hard_filter` removes candidates outright and says why
   (``excluded``, ``avoid_tag``, ``out_of_season``, ``banned``, ``min_gap``).
2. :func:`score` sums named terms into a :class:`Breakdown`, reusing
   :mod:`mealplanner.scoring`'s term functions, plus the leftover ``hold``.
3. :func:`select` takes the top score, or with probability ε draws by
   :func:`~mealplanner.scoring.exploration_weight`.

Randomness comes only from the injected ``rng``, so tests pass a seed.
"""

from __future__ import annotations

import random
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from . import scoring

__all__ = [
    "BAN_DAYS",
    "MIN_GAP_DAYS",
    "Candidate",
    "Weights",
    "SlotContext",
    "Breakdown",
    "Choice",
    "is_strictly_seasonal",
    "hard_filter",
    "base_stats",
    "score",
    "score_all",
    "select",
]

#: A rejected dish is banned from slots in ``[rejected_slot, rejected_slot + BAN_DAYS - 1]``.
BAN_DAYS = 4
#: A main is not repeated within this many days of another serving of it.
MIN_GAP_DAYS = 5


@dataclass(frozen=True)
class Candidate:
    """A recipe as the engine sees it: plain values, read once per run."""

    id: int
    title: str
    course: str = "main"
    score: Optional[float] = None
    bulk_prep: bool = False
    ingredient_ids: Tuple[int, ...] = ()
    #: ``season_months`` of each ingredient, aligned with ``ingredient_ids``.
    ingredient_season_months: Tuple[Tuple[int, ...], ...] = ()
    tags: Tuple[str, ...] = ()
    date_last_rejected: Optional[date] = None
    date_last_suggested: Optional[date] = None


@dataclass(frozen=True)
class Weights:
    seasonality: float = 1.0
    recency: float = 1.0
    tag_penalty: float = 1.0
    bulk_bonus: float = 1.0
    ingredient_repeat: float = 1.0
    tag_repeat: float = 1.0


@dataclass
class SlotContext:
    """Everything the stages need to know about one slot and its surroundings."""

    date: date
    meal_number: int = 1
    #: Sorted dates each recipe was (or will be) eaten fresh -- leftovers excluded.
    eaten_dates: Mapping[int, Sequence[date]] = field(default_factory=dict)
    ingredient_last_used: Mapping[int, date] = field(default_factory=dict)
    tag_last_used: Mapping[str, date] = field(default_factory=dict)
    penalized_tags: Set[str] = field(default_factory=set)
    #: Fridge ingredient id -> slots still wanting it.
    fridge_remaining: Mapping[int, int] = field(default_factory=dict)
    held_recipe_id: Optional[int] = None
    #: Dates each recipe sits on a plan in any form, leftovers included.
    kept_dates: Mapping[int, Sequence[date]] = field(default_factory=dict)
    exclude_ids: Set[int] = field(default_factory=set)
    avoid_tags: Set[str] = field(default_factory=set)
    reduce_tags: Set[str] = field(default_factory=set)
    weights: Weights = field(default_factory=Weights)
    hold_margin: float = 15.0
    #: Whether the minimum repeat gap applies (mains yes, sides no).
    min_gap: bool = True


@dataclass
class Breakdown:
    """The named score terms of one candidate, in a fixed order."""

    terms: Dict[str, float]

    @property
    def total(self) -> float:
        return sum(self.terms.values())

    def as_dict(self, digits: int = 3) -> Dict[str, float]:
        out = {k: round(v, digits) for k, v in self.terms.items()}
        out["total"] = round(self.total, digits)
        return out


@dataclass
class Choice:
    candidate: Candidate
    breakdown: Breakdown
    #: Position of the pick in the score ranking (0 = top score).
    rank: int
    mode: str  # "exploit" or "explore"
    #: Candidate id -> explore weight; empty unless the explore draw fired.
    explore_weights: Dict[int, float] = field(default_factory=dict)


def _is_seasonal_data(months: Sequence[int]) -> bool:
    return 0 < len(months) < 12


def is_strictly_seasonal(c: Candidate, month: int) -> bool:
    """At least one ingredient has seasonal data, and every such one is in season."""
    seasonal = [m for m in c.ingredient_season_months if _is_seasonal_data(m)]
    return bool(seasonal) and all(month in m for m in seasonal)


def _out_of_season(c: Candidate, month: int) -> bool:
    """No ingredient is available this month (no data counts as all-year)."""
    months = c.ingredient_season_months
    return bool(months) and not any(not m or month in m for m in months)


def _banned(c: Candidate, slot: date) -> bool:
    if c.date_last_rejected is None:
        return False
    return 0 <= (slot - c.date_last_rejected).days < BAN_DAYS


def _breaks_min_gap(c: Candidate, ctx: SlotContext) -> bool:
    if not ctx.min_gap or c.id == ctx.held_recipe_id:
        return False
    if not any(abs((ctx.date - d).days) < MIN_GAP_DAYS for d in ctx.eaten_dates.get(c.id, ())):
        return False
    uses_fridge = any(i in ctx.fridge_remaining for i in c.ingredient_ids)
    return not (uses_fridge or is_strictly_seasonal(c, ctx.date.month))


def hard_filter(
    candidates: Sequence[Candidate], ctx: SlotContext
) -> Tuple[List[Candidate], Dict[int, str]]:
    """Split ``candidates`` into the eligible ones and ``{id: reason}`` for the rest."""
    eligible: List[Candidate] = []
    excluded: Dict[int, str] = {}
    month = ctx.date.month
    for c in candidates:
        if c.id in ctx.exclude_ids:
            reason = "excluded"
        elif ctx.avoid_tags and ctx.avoid_tags.intersection(c.tags):
            reason = "avoid_tag"
        elif _out_of_season(c, month):
            reason = "out_of_season"
        elif _banned(c, ctx.date):
            reason = "banned"
        elif _breaks_min_gap(c, ctx):
            reason = "min_gap"
        else:
            eligible.append(c)
            continue
        excluded[c.id] = reason
    return eligible, excluded


def base_stats(pool: Sequence[Candidate]) -> Tuple[float, float]:
    """The pool's raw-score statistics that normalise every candidate's base term."""
    return scoring.base_stats(c.score or 0.0 for c in pool)


def _last_on_or_before(dates: Sequence[date], slot: date) -> Optional[date]:
    """R5: the latest date not after ``slot`` in sorted ``dates``."""
    i = bisect_right(dates, slot)
    return dates[i - 1] if i else None


def score(c: Candidate, ctx: SlotContext, stats: Tuple[float, float]) -> Breakdown:
    """The candidate's named score terms on this slot.

    ``stats`` is :func:`base_stats` of the pool, so the base term is normalised
    against the candidates it competes with. On its held slot a leftover gets
    the ``hold`` term and is exempt from its own recency and repetition terms.
    """
    w = ctx.weights
    held = c.id == ctx.held_recipe_id
    recipe = {
        "bulk_prep": c.bulk_prep,
        "ingredients": [{"season_months": list(m)} for m in c.ingredient_season_months],
        "ingredient_ids": list(c.ingredient_ids),
        "tags": list(c.tags),
    }
    last_eaten = _last_on_or_before(ctx.eaten_dates.get(c.id, ()), ctx.date)

    recency = 0.0
    if last_eaten is not None and not held:
        recency = w.recency * scoring.recency_penalty({"date_last_planned": last_eaten}, ctx.date)
    ingredient_repeat = tag_repeat = 0.0
    if not held:
        ingredient_repeat = w.ingredient_repeat * scoring.ingredient_repetition_penalty(
            recipe, ctx.date, ctx.ingredient_last_used
        )
        tag_repeat = w.tag_repeat * scoring.tag_repetition_penalty(
            recipe, ctx.date, ctx.tag_last_used, ctx.penalized_tags
        )

    return Breakdown({
        "base": scoring.squashed_base(c.score, stats),
        "seasonality": w.seasonality * scoring.seasonality_bonus(recipe, ctx.date),
        "recency": recency,
        "bulk": w.bulk_bonus * scoring.bulk_bonus(recipe),
        "fridge": scoring.fridge_bonus(recipe, ctx.fridge_remaining.keys()),
        "reduce_tags": w.tag_penalty * scoring.tag_penalty(recipe, ctx.reduce_tags),
        "ingredient_repeat": ingredient_repeat,
        "tag_repeat": tag_repeat,
        "hold": ctx.hold_margin if held else 0.0,
    })


def score_all(
    eligible: Sequence[Candidate],
    ctx: SlotContext,
    stats: Optional[Tuple[float, float]] = None,
) -> List[Tuple[Candidate, Breakdown]]:
    """Score every eligible candidate, in input order, against one set of pool statistics.

    Pass the whole course pool's ``stats`` so a dish's base term does not shift
    when the hard rules remove another; they default to the eligible pool's.
    """
    stats = stats or base_stats(eligible)
    return [(c, score(c, ctx, stats)) for c in eligible]


def select(
    scored: Sequence[Tuple[Candidate, Breakdown]],
    ctx: SlotContext,
    epsilon: float,
    rng: random.Random,
) -> Choice:
    """The top score, or with probability ``epsilon`` an exploration-weighted draw."""
    if not scored:
        raise ValueError("No recipes available")
    ranked = sorted(scored, key=lambda pair: (-pair[1].total, pair[0].id))
    weights: Dict[int, float] = {}
    if epsilon and rng.random() < epsilon:
        mode = "explore"
        weights = {
            c.id: scoring.exploration_weight(
                slot_date=ctx.date,
                date_last_suggested=c.date_last_suggested,
                kept_dates=ctx.kept_dates.get(c.id, ()),
            )
            for c, _ in ranked
        }
        values = list(weights.values())
        if any(values):
            rank = rng.choices(range(len(ranked)), weights=values, k=1)[0]
        else:
            # Everything is on cooldown: fall back to a uniform draw.
            rank = rng.randrange(len(ranked))
    else:
        mode, rank = "exploit", 0
    c, breakdown = ranked[rank]
    return Choice(candidate=c, breakdown=breakdown, rank=rank, mode=mode, explore_weights=weights)
