import pytest
import random
from datetime import date

from mealplanner.models import Recipe, Ingredient, RecipeIngredient, Tag
from mealplanner.planner import generate_plan


def make_recipe(name, bulk=False, tags=None, season=None):
    r = Recipe(title=name, servings_default=2, bulk_prep=bulk, course="main")
    if tags:
        r.tags = [Tag(name=t) for t in tags]
    if season:
        base = Ingredient(name=f"{name}-ing", season_months=list(season))
        r.recipe_ingredients = [RecipeIngredient(ingredient=base, recipe=r)]
    return r




def test_generate_plan_avoid_tags_from_ui(db_session):
    """Avoid tags supplied as a list should exclude recipes."""
    good = Recipe(title="Good", servings_default=1, score=1.0, bulk_prep=True, course="main")
    bad = Recipe(title="Bad", servings_default=1, score=1.5, bulk_prep=True, course="main")
    bad.tags = [Tag(name="avoid")]
    db_session.add_all([good, bad])
    db_session.commit()
    start = date(2024, 1, 1)
    plan = generate_plan(
        db_session,
        start,
        days=1,
        meals_per_day=1,
        epsilon=0.0,
        avoid_tags=["avoid"],
    )
    assert plan["2024-01-01"] == ["Good"]


def test_recency_weight(db_session):
    fresh = Recipe(
        title="Fresh",
        servings_default=1,
        score=1.0,
        bulk_prep=True,
        course="main",
        date_last_consumed=date(2023, 12, 1),
    )
    recent = Recipe(
        title="Recent",
        servings_default=1,
        score=1.2,
        bulk_prep=True,
        course="main",
        date_last_consumed=date(2024, 1, 2),
    )
    db_session.add_all([fresh, recent])
    db_session.commit()
    start = date(2024, 1, 1)
    plan = generate_plan(
        db_session,
        start,
        days=1,
        meals_per_day=1,
        epsilon=0.0,
        recency_weight=0.0,
    )
    # Without recency penalty, higher base score wins
    assert plan["2024-01-01"] == ["Recent"]
    plan = generate_plan(
        db_session,
        start,
        days=1,
        meals_per_day=1,
        epsilon=0.0,
        recency_weight=2.0,
    )
    # Heavier penalty pushes the fresher recipe to the top
    assert plan["2024-01-01"] == ["Fresh"]


def test_generate_plan_epsilon_randomness(db_session):
    """With epsilon > 0 the selection may choose lower scoring recipes."""
    recipes = [
        Recipe(title="Top", servings_default=1, score=2.0, bulk_prep=True, course="main"),
        Recipe(title="Low", servings_default=1, score=1.0, bulk_prep=True, course="main"),
    ]
    db_session.add_all(recipes)
    db_session.commit()
    start = date(2024, 1, 1)
    random.seed(0)
    plan = generate_plan(
        db_session,
        start,
        days=1,
        meals_per_day=1,
        epsilon=1.0,
    )
    assert plan["2024-01-01"] == ["Low"]


def test_generate_plan_leftover_expiry(db_session):
    recipe = Recipe(title="Bulk", servings_default=1, bulk_prep=True, score=1.0, course="main")
    db_session.add(recipe)
    db_session.commit()
    start = date(2024, 1, 1)
    plan = generate_plan(
        db_session,
        start,
        days=4,
        meals_per_day=1,
        epsilon=0.0,
        keep_days=2,
    )
    expected = {
        "2024-01-01": ["Bulk"],
        "2024-01-02": ["Bulk (leftover)"],
        "2024-01-03": ["Bulk"],
        "2024-01-04": ["Bulk (leftover)"],
    }
    assert plan == expected


def test_generate_plan_bulk_leftovers_disabled(db_session):
    recipe = Recipe(title="Bulk", servings_default=1, bulk_prep=True, score=1.0, course="main")
    db_session.add(recipe)
    db_session.commit()
    start = date(2024, 1, 1)
    plan = generate_plan(
        db_session,
        start,
        days=2,
        meals_per_day=1,
        epsilon=0.0,
        keep_days=2,
        bulk_leftovers=False,
    )
    assert plan == {
        "2024-01-01": ["Bulk"],
        "2024-01-02": ["Bulk"],
    }


def test_generate_plan_respects_meals_per_day(db_session):
    first = Recipe(title="MealA", servings_default=1, score=1.0, course="main")
    second = Recipe(title="MealB", servings_default=1, score=1.0, course="main")
    db_session.add_all([first, second])
    db_session.commit()
    start = date(2024, 1, 1)
    plan = generate_plan(db_session, start, days=1, meals_per_day=2, epsilon=0.0)
    assert len(plan["2024-01-01"]) == 2
