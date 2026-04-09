"""Meal planning logic for the Meals Planner Codex application."""

from __future__ import annotations

from datetime import date, timedelta
import random
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Set

from sqlalchemy import func, false
from sqlalchemy.orm import Session, joinedload

from .models import Ingredient, Recipe, RecipeIngredient, Meal, MealSide
from .scoring import score_recipe
from .config import DEFAULT_PLAN_SETTINGS


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


def _recipe_to_dict(recipe: Recipe, last_planned: date | None) -> Dict[str, object]:
    if last_planned is None:
        last_planned = date.today() - timedelta(days=10_000)

    # Your ORM exposes Recipe.ingredients -> List[RecipeIngredient]
    ingredients = [
        {"season_months": (ri.ingredient.season_months or [])}
        for ri in getattr(recipe, "ingredients", [])  # <- fixed
    ]

    return {
        "score": recipe.score,
        "bulk_prep": recipe.bulk_prep,
        "date_last_planned": last_planned,
        "ingredients": ingredients,
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
    min_recipe_gap: int = 5,
    plan_settings: Dict[str, object] | None = None,
    return_slots: bool = False,
) -> Dict[str, List[str]] | List[Slot]:
    """Generate a meal plan.

    When ``return_slots`` is ``True`` a list of :class:`Slot` objects is
    returned instead of a mapping for callers that require detailed metadata.
    """

    settings = {**DEFAULT_PLAN_SETTINGS, **(plan_settings or {})}

    recipes = (
        session.query(Recipe)
        .options(
            joinedload(Recipe.ingredients).joinedload(RecipeIngredient.ingredient),
            joinedload(Recipe.tags),
        )
        .filter(Recipe.course.in_(["main", "first-course"]))
        .all()
    )

    last_planned: Dict[int, date] = dict(
        session.query(Meal.recipe_id, func.max(Meal.plan_date))
        .filter(Meal.leftover == false())
        .group_by(Meal.recipe_id)
    )

    slots: List[Slot] = []
    for day_offset in range(days):
        current = start + timedelta(days=day_offset)
        for meal_number in range(1, meals_per_day + 1):
            slots.append(Slot(date=current, meal_number=meal_number))

    leftovers: List[Dict[str, object]] = []

    for idx, slot in enumerate(slots):
        _apply_soft_holds(slots, idx, leftovers, settings)

        available = filter_recipes(
            recipes,
            season=slot.date.month,
            tags=tags,
            avoid_tags=avoid_tags,
            reduce_tags=reduce_tags,
        )
        if not available:
            raise ValueError("No recipes available")
        base_scores = [r.score or 0.0 for r in available]
        scored: List[tuple[Recipe, float]] = []
        print(f"planning date: {slot.date} (meal {slot.meal_number}) \n\n ")
        for r in available:
            print("\033[31m  recipe: \033[0m", r.title )
            score = score_recipe(
                _recipe_to_dict(r, last_planned.get(r.id)),
                planning_date=slot.date,
                seasonality_weight=seasonality_weight,
                recency_weight=0.0
                if slot.soft_hold_recipe_id == r.id
                else recency_weight,
                tag_penalty_weight=tag_penalty_weight,
                bulk_bonus_weight=bulk_bonus_weight,
                reduce_tags=reduce_tags or [],
                base_scores=base_scores,
            )
            print( "score: ", score)
            if slot.soft_hold_recipe_id and r.id != slot.soft_hold_recipe_id:
                score -= settings.get("SOFT_HOLD_PENALTY", 0.0)
            scored.append((r, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        if epsilon and random.random() < epsilon:
            choice_idx = random.randrange(len(scored))
            slot.selection_mode = "explore"
        else:
            choice_idx = 0
            slot.selection_mode = "exploit"
        slot.candidate_rank = choice_idx

        chosen = scored[choice_idx][0]
        slot.recipe = chosen
        slot.leftover = slot.soft_hold_recipe_id == getattr(chosen, "id", None)

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
        else:
            last_planned[chosen.id] = slot.date
            if chosen.bulk_prep and bulk_leftovers:
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
        title = slot.recipe.title + (" (leftover)" if slot.leftover else "")
        schedule.setdefault(key, []).append(title)
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
) -> Recipe:
    """Select a single side dish using the planner's scoring logic."""

    recipes = session.query(Recipe).filter(Recipe.course == "side").all()
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
        session.query(MealSide.side_recipe_id, func.max(MealSide.plan_date)).group_by(
            MealSide.side_recipe_id
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
        recipe_ingredients = getattr(recipe, "recipe_ingredients", [])
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
    "generate_plan",
    "generate_side_dish",
    "filter_recipes",
]

