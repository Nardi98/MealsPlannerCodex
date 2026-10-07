"""Meal planning logic for the Meals Planner Codex application.

The DB side of planning: :func:`load_snapshot` does every read once, then each
slot runs through the pure selection engine (:mod:`mealplanner.engine`) via
:func:`choose`, which also builds the slot's trace.
"""

from __future__ import annotations

from bisect import insort
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
import random
from typing import Any, Dict, Iterable, List, Sequence, Set

from sqlalchemy import func, literal, true
from sqlalchemy.orm import Session, selectinload

from models import (
    MAIN_COURSES,
    Ingredient,
    Recipe,
    RecipeIngredient,
    Meal,
    MealSide,
    Tag,
    takes_favorite_sides,
)
from scoping import scope
from . import engine
from .scoring import score_recipe
from .config import DEFAULT_PLAN_SETTINGS

#: Runners-up recorded per slot in the trace (Q8).
TRACE_RUNNERS_UP = 5

COURSE_GROUPS: Dict[str, Sequence[str]] = {"main": MAIN_COURSES, "side": ("side",)}


@dataclass
class Slot:
    """Representation of a single meal planning slot."""

    date: date
    meal_number: int
    recipe: Recipe | None = None
    leftover: bool = False
    selection_mode: str | None = None
    candidate_rank: int | None = None
    soft_hold_recipe_id: int | None = None
    side_ids: List[int] = field(default_factory=list)
    #: Why this dish won: chosen, mode, rank, breakdown, runners-up, exclusions.
    trace: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Snapshot:
    """Every DB read a planning run needs, done once (see :func:`load_snapshot`)."""

    recipes: Dict[int, Recipe]
    candidates: List[engine.Candidate]
    #: Recipe id -> sorted dates it was served fresh (leftovers excluded).
    eaten_dates: Dict[int, List[date]]
    #: Recipe id -> sorted dates it sits on a plan in any form.
    kept_dates: Dict[int, List[date]]
    ingredient_last_used: Dict[int, date]
    tag_last_used: Dict[str, date]
    penalized_tags: Set[str]


def _candidate(recipe: Recipe) -> engine.Candidate:
    return engine.Candidate(
        id=recipe.id,
        title=recipe.title,
        course=recipe.course,
        score=recipe.score,
        bulk_prep=bool(recipe.bulk_prep),
        ingredient_ids=tuple(ri.ingredient_id for ri in recipe.ingredients),
        ingredient_season_months=tuple(
            tuple(ri.ingredient.season_months or ()) for ri in recipe.ingredients
        ),
        tags=tuple(t.name for t in recipe.tags),
        date_last_rejected=recipe.date_last_rejected,
        date_last_suggested=recipe.date_last_suggested,
    )


def _keep_latest(latest: Dict[Any, date], key: Any, day: date) -> None:
    if key not in latest or latest[key] < day:
        latest[key] = day


def load_snapshot(
    session: Session,
    user_id: int | None,
    course_group: str,
    start: date,
    end: date,
    skip_slot: tuple[date, int] | None = None,
) -> Snapshot:
    """Read the candidates and their history for planning ``[start, end]``.

    Every query goes through :func:`scope`. Meals inside ``[start, end]`` are
    about to be overwritten, so they are not history -- except when planning a
    single slot (``skip_slot``), where the rest of the saved plan is the context
    and only that slot itself is left out. Mains read ``meals`` (fresh servings
    for eaten dates, every row for kept dates); sides read ``meal_sides``. The
    ingredient and tag maps hold the latest use before ``start``, or on/before
    the slot when planning a single one.
    """
    recipes = scope(
        session.query(Recipe)
        .options(
            selectinload(Recipe.ingredients).joinedload(RecipeIngredient.ingredient),
            selectinload(Recipe.tags),
            # pick_favorite_side reads this per slot; without it each candidate
            # main lazy-loads its pairing during planning.
            selectinload(Recipe.favorite_sides),
        )
        .filter(Recipe.course.in_(COURSE_GROUPS[course_group])),
        Recipe.user_id,
        user_id,
    ).all()
    by_id = {r.id: r for r in recipes}

    if course_group == "side":
        rows = scope(
            session.query(
                MealSide.side_recipe_id, MealSide.plan_date, MealSide.meal_number, literal(False)
            ),
            MealSide.user_id,
            user_id,
        )
    else:
        rows = scope(
            session.query(
                Meal.recipe_id, Meal.plan_date, Meal.meal_number,
                Meal.leftover_source_date.isnot(None),
            ),
            Meal.user_id,
            user_id,
        )

    penalized_tags: Set[str] = {
        name
        for (name,) in scope(
            session.query(Tag.name).filter(Tag.penalize_repetition == true()),
            Tag.user_id,
            user_id,
        )
    }

    eaten: Dict[int, List[date]] = {}
    kept: Dict[int, List[date]] = {}
    ingredient_last_used: Dict[int, date] = {}
    tag_last_used: Dict[str, date] = {}
    history_cutoff = skip_slot[0] if skip_slot else start - timedelta(days=1)
    for recipe_id, plan_date, meal_number, is_leftover in rows:
        if skip_slot is not None:
            if (plan_date, meal_number) == skip_slot:
                continue
        elif start <= plan_date <= end:
            continue
        kept.setdefault(recipe_id, []).append(plan_date)
        if is_leftover:
            continue
        eaten.setdefault(recipe_id, []).append(plan_date)
        recipe = by_id.get(recipe_id)
        if recipe is None or plan_date > history_cutoff:
            continue
        for ri in recipe.ingredients:
            _keep_latest(ingredient_last_used, ri.ingredient_id, plan_date)
        for t in recipe.tags:
            if t.name in penalized_tags:
                _keep_latest(tag_last_used, t.name, plan_date)
    for dates in (*eaten.values(), *kept.values()):
        dates.sort()

    return Snapshot(
        recipes=by_id,
        candidates=[_candidate(r) for r in recipes],
        eaten_dates=eaten,
        kept_dates=kept,
        ingredient_last_used=ingredient_last_used,
        tag_last_used=tag_last_used,
        penalized_tags=penalized_tags,
    )


def choose(
    candidates: Sequence[engine.Candidate],
    ctx: engine.SlotContext,
    epsilon: float,
    rng: random.Random,
) -> tuple[engine.Choice, Dict[str, Any]]:
    """Run the engine's stages on one slot; return the choice and its trace.

    If the hard rules leave nothing while the minimum gap applies, the slot is
    re-run without it (a small library could not fill a week otherwise) and the
    trace records ``relaxed: ["min_gap"]``. Still nothing is a ``ValueError``.
    """
    relaxed: List[str] = []
    eligible, excluded = engine.hard_filter(candidates, ctx)
    if not eligible and ctx.min_gap:
        ctx.min_gap = False
        relaxed.append("min_gap")
        eligible, excluded = engine.hard_filter(candidates, ctx)
    if not eligible:
        raise ValueError("No recipes available")

    scored = engine.score_all(eligible, ctx, engine.base_stats(candidates))
    choice = engine.select(scored, ctx, epsilon, rng)
    runners_up = sorted(
        (pair for pair in scored if pair[0].id != choice.candidate.id),
        key=lambda pair: (-pair[1].total, pair[0].id),
    )[:TRACE_RUNNERS_UP]
    trace = {
        "date": ctx.date,
        "meal_number": ctx.meal_number,
        "chosen": {"id": choice.candidate.id, "title": choice.candidate.title},
        "mode": choice.mode,
        "rank": choice.rank,
        "breakdown": choice.breakdown.as_dict(),
        "runners_up": [
            {"id": c.id, "title": c.title, "breakdown": b.as_dict()} for c, b in runners_up
        ],
        "excluded": dict(Counter(excluded.values())),
        "hold": ctx.held_recipe_id,
        "relaxed": relaxed,
    }
    if choice.mode == "explore":
        trace["explore_weight"] = choice.explore_weights.get(choice.candidate.id)
    return choice, trace


def stamp_suggested(recipe: Recipe, slot_date: date) -> None:
    """Record that ``recipe`` was proposed for ``slot_date``; never moves backwards."""
    if recipe.date_last_suggested is None or recipe.date_last_suggested < slot_date:
        recipe.date_last_suggested = slot_date


def pick_favorite_side(
    recipe: Recipe, rng: random.Random | None = None
) -> int | None:
    """Return the id of one of ``recipe``'s favorite sides, chosen uniformly.

    ``None`` when the recipe has no favorites -- or isn't a course that takes
    one -- which leaves the meal bare for the user to fill in by hand: the
    behaviour that predates favorites. The course check also means a first
    course carrying a stale pairing (from before sides became main-only) is
    ignored rather than acted on.
    """
    if not takes_favorite_sides(recipe.course):
        return None
    favorites = getattr(recipe, "favorite_sides", None) or []
    if not favorites:
        return None
    return (rng or random).choice(favorites).id


def generate_plan(
    session: Session,
    start: date,
    days: int,
    meals_per_day: int,
    keep_days: int = 7,
    bulk_leftovers: bool = True,
    epsilon: float = 0.0,
    avoid_tags: Iterable[str] | None = None,
    reduce_tags: Iterable[str] | None = None,
    seasonality_weight: float = 1.0,
    recency_weight: float = 1.0,
    tag_penalty_weight: float = 1.0,
    bulk_bonus_weight: float = 1.0,
    ingredient_repeat_weight: float = 1.0,
    tag_repeat_weight: float = 1.0,
    fridge_ingredients: Dict[int, int] | None = None,
    plan_settings: Dict[str, object] | None = None,
    return_slots: bool = False,
    user_id: int | None = None,
    rng: random.Random | None = None,
) -> Dict[str, List[str]] | List[Slot]:
    """Generate a meal plan slot by slot through the selection engine.

    When ``return_slots`` is ``True`` a list of :class:`Slot` objects (each with
    its ``trace``) is returned instead of a ``{date: [titles]}`` mapping. When
    ``user_id`` is given every read is scoped to that account so a plan only
    draws on its own data. ``rng`` is the only source of randomness.
    """

    settings = {**DEFAULT_PLAN_SETTINGS, **(plan_settings or {})}
    rng = rng or random.Random()
    snap = load_snapshot(session, user_id, "main", start, start + timedelta(days=days - 1))
    weights = engine.Weights(
        seasonality=seasonality_weight,
        recency=recency_weight,
        tag_penalty=tag_penalty_weight,
        bulk_bonus=bulk_bonus_weight,
        ingredient_repeat=ingredient_repeat_weight,
        tag_repeat=tag_repeat_weight,
    )

    slots: List[Slot] = []
    for day_offset in range(days):
        current = start + timedelta(days=day_offset)
        for meal_number in range(1, meals_per_day + 1):
            slots.append(Slot(date=current, meal_number=meal_number))

    leftovers: List[Dict[str, object]] = []
    # Side chosen for each recipe's current cooking batch, so its leftovers can
    # reuse it. A later fresh cook of the same recipe overwrites the entry and
    # therefore draws again. This mirrors, at generation time, the source ->
    # leftover link that ``crud._assign_leftover_sources`` persists later.
    batch_sides: Dict[int, int | None] = {}

    # Mutable count of each fridge ingredient still wanting a slot. Recipes using
    # a still-wanted ingredient get a scoring boost; each use (fresh or leftover)
    # decrements the count until it stops boosting.
    fridge_remaining: Dict[int, int] = {
        int(k): int(v) for k, v in (fridge_ingredients or {}).items() if int(v) > 0
    }

    for idx, slot in enumerate(slots):
        _apply_soft_holds(slots, idx, leftovers, settings)

        ctx = engine.SlotContext(
            date=slot.date,
            meal_number=slot.meal_number,
            eaten_dates=snap.eaten_dates,
            ingredient_last_used=snap.ingredient_last_used,
            tag_last_used=snap.tag_last_used,
            penalized_tags=snap.penalized_tags,
            fridge_remaining=fridge_remaining,
            held_recipe_id=slot.soft_hold_recipe_id,
            kept_dates=snap.kept_dates,
            avoid_tags=set(avoid_tags or ()),
            reduce_tags=set(reduce_tags or ()),
            weights=weights,
            hold_margin=float(settings["LEFTOVER_HOLD_MARGIN"]),
        )
        choice, slot.trace = choose(snap.candidates, ctx, epsilon, rng)
        slot.selection_mode = choice.mode
        slot.candidate_rank = choice.rank

        chosen = snap.recipes[choice.candidate.id]
        slot.recipe = chosen
        slot.leftover = slot.soft_hold_recipe_id == chosen.id

        if slot.leftover:
            # Reheating what was cooked earlier: the side came with it.
            side_id = batch_sides.get(chosen.id)
        else:
            side_id = batch_sides[chosen.id] = pick_favorite_side(chosen, rng)
        slot.side_ids = [] if side_id is None else [side_id]

        # The pick is now on the plan: it counts for the explore cooldown and,
        # when cooked fresh, for recency and the minimum gap of later slots.
        insort(snap.kept_dates.setdefault(chosen.id, []), slot.date)
        if not slot.leftover:
            insort(snap.eaten_dates.setdefault(chosen.id, []), slot.date)

        # The chosen recipe's ingredients / penalized tags are eaten on this
        # date regardless of leftover status, so update the diversity maps.
        for ri in chosen.ingredients:
            snap.ingredient_last_used[ri.ingredient_id] = slot.date
            # Using a fridge ingredient (fresh cook or leftover day) consumes one
            # unit of its requested count; once exhausted it's dropped so it no
            # longer boosts scores.
            if ri.ingredient_id in fridge_remaining:
                fridge_remaining[ri.ingredient_id] -= 1
                if fridge_remaining[ri.ingredient_id] <= 0:
                    del fridge_remaining[ri.ingredient_id]
        for t in chosen.tags:
            if t.name in snap.penalized_tags:
                snap.tag_last_used[t.name] = slot.date

        if slot.leftover:
            for record in leftovers[:]:
                if record["recipe_id"] == chosen.id:
                    record["repeats_remaining"] = int(record["repeats_remaining"]) - 1
                    record["next_date"] = slot.date + timedelta(
                        days=settings.get("LEFTOVER_SPACING_GAP", 1)
                    )
                    if (
                        record["repeats_remaining"] <= 0
                        or slot.date >= record["window_end"]
                    ):
                        leftovers.remove(record)
                    break
        elif chosen.bulk_prep and bulk_leftovers:
            repeats = settings.get("LEFTOVER_REPEAT_BY_RECIPE", {}).get(
                chosen.id, settings.get("LEFTOVER_REPEAT_DEFAULT", 0)
            )
            if repeats:
                leftovers.append(
                    {
                        "recipe_id": chosen.id,
                        "source_date": slot.date,
                        "repeats_remaining": int(repeats),
                        "window_end": slot.date + timedelta(days=keep_days - 1),
                        "next_date": slot.date
                        + timedelta(days=settings.get("LEFTOVER_SPACING_GAP", 1)),
                    }
                )

    if return_slots:
        return slots

    schedule: Dict[str, List[str]] = {}
    for slot in slots:
        key = slot.date.isoformat()
        schedule.setdefault(key, []).append(slot.recipe.title)
    return schedule


def _apply_soft_holds(
    slots: List[Slot],
    start_idx: int,
    leftovers: List[Dict[str, object]],
    settings: Dict[str, object],
) -> None:
    """Assign soft holds for leftovers to future slots."""

    # Clear existing soft holds for future slots
    for s in slots[start_idx:]:
        s.soft_hold_recipe_id = None

    spacing = int(settings.get("LEFTOVER_SPACING_GAP", 1))
    per_day_limit = int(settings.get("MAX_LEFTOVERS_PER_DAY", 1))
    daypart_pref = settings.get("LEFTOVER_DAYPART_PREF", {})
    daypart_map = settings.get("MEAL_NUMBER_TO_DAYPART", {})

    counts = Counter()
    for s in slots[:start_idx]:
        if s.soft_hold_recipe_id:
            counts[s.date] += 1

    for record in leftovers:
        repeats = int(record["repeats_remaining"])
        next_date = record.get("next_date", record["source_date"])
        for s in slots[start_idx:]:
            if repeats <= 0:
                break
            if s.date < next_date:
                continue
            if s.date > record["window_end"]:
                break
            if counts[s.date] >= per_day_limit:
                continue
            pref = daypart_pref.get(record["recipe_id"])
            if pref and daypart_map.get(s.meal_number) != pref:
                continue
            s.soft_hold_recipe_id = int(record["recipe_id"])
            counts[s.date] += 1
            repeats -= 1
            next_date = s.date + timedelta(days=spacing)


def _recipe_to_dict(recipe: Recipe, last_planned: date | None) -> Dict[str, object]:
    if last_planned is None:
        last_planned = date.today() - timedelta(days=10_000)
    return {
        "score": recipe.score,
        "bulk_prep": recipe.bulk_prep,
        "date_last_planned": last_planned,
        "ingredients": [
            {"season_months": (ri.ingredient.season_months or [])}
            for ri in getattr(recipe, "ingredients", [])
        ],
        "ingredient_ids": [ri.ingredient_id for ri in recipe.ingredients],
        "tags": [t.name for t in recipe.tags],
    }


def generate_side_dish(
    session: Session,
    tags: Iterable[str] | None = None,
    avoid_tags: Iterable[str] | None = None,
    reduce_tags: Iterable[str] | None = None,
    avoid_titles: Iterable[str] | None = None,
    epsilon: float = 0.0,
    keep_days: int = 7,
    bulk_leftovers: bool = True,
    seasonality_weight: float = 1.0,
    recency_weight: float = 1.0,
    tag_penalty_weight: float = 1.0,
    bulk_bonus_weight: float = 1.0,
    user_id: int | None = None,
) -> Recipe:
    """Select a single side dish using the planner's scoring logic.

    Scoped to ``user_id`` when given, so only the caller's own side recipes and
    side-dish history are considered.
    """

    recipes = scope(
        session.query(Recipe).filter(Recipe.course == "side"),
        Recipe.user_id,
        user_id,
    ).all()
    if avoid_titles:
        avoid_set = set(avoid_titles)
        recipes = [r for r in recipes if r.title not in avoid_set]
    today = date.today()
    available = filter_recipes(
        recipes,
        season=today.month,
        tags=tags,
        avoid_tags=avoid_tags,
        reduce_tags=reduce_tags,
    )
    if not available:
        raise ValueError("No side dishes available")

    last_planned: Dict[int, date] = dict(
        scope(
            session.query(MealSide.side_recipe_id, func.max(MealSide.plan_date))
            .group_by(MealSide.side_recipe_id),
            MealSide.user_id,
            user_id,
        )
    )

    base_scores = [r.score or 0.0 for r in available]
    scored: List[tuple[Recipe, float]] = []
    for r in available:
        score = score_recipe(
            _recipe_to_dict(r, last_planned.get(r.id)),
            planning_date=today,
            seasonality_weight=seasonality_weight,
            recency_weight=recency_weight,
            tag_penalty_weight=tag_penalty_weight,
            bulk_bonus_weight=bulk_bonus_weight,
            reduce_tags=reduce_tags or [],
            base_scores=base_scores,
        )
        scored.append((r, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    if epsilon and random.random() < epsilon:
        idx = random.randrange(len(scored))
    else:
        idx = 0
    return scored[idx][0]


def _ingredient_in_season(ingredient: Ingredient, month: int) -> bool:
    """Return ``True`` if ``ingredient`` is available in ``month``.

    ``Ingredient.season_months`` stores a list of month numbers. If the field is
    empty the ingredient is assumed to be available year round.
    """

    months = ingredient.season_months or []
    return not months or month in months


def filter_recipes(
    recipes: Sequence[Recipe],
    season: int | None = None,
    tags: Iterable[str] | None = None,
    avoid_tags: Iterable[str] | None = None,
    reduce_tags: Iterable[str] | None = None,
) -> List[Recipe]:
    """Filter ``recipes`` according to ``season`` and ``tags``.

    Args:
        recipes: Collection of :class:`~models.Recipe` objects.
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
        recipe_ingredients = getattr(recipe, "ingredients", [])
        if season is not None and recipe_ingredients and not any(
            _ingredient_in_season(ri.ingredient, season)
            for ri in recipe_ingredients
        ):
            continue
        if reduce_set and recipe_tags.intersection(reduce_set):
            reduced.append(recipe)
        else:
            primary.append(recipe)
    return primary + reduced


__all__ = [
    "Slot",
    "Snapshot",
    "load_snapshot",
    "choose",
    "stamp_suggested",
    "generate_plan",
    "generate_side_dish",
    "filter_recipes",
]
