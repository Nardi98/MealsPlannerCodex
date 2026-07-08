import pytest
import random
from datetime import date

from models import Recipe, Ingredient, RecipeIngredient, Tag, MealPlan, Meal
from mealplanner.planner import generate_plan, filter_recipes


def test_filter_recipes_excludes_out_of_season(db_session):
    """A recipe whose only ingredient is out of season is filtered out."""
    winter = Recipe(title="Winter", servings_default=1, course="main")
    winter_ing = Ingredient(name="winter-veg", season_months=[12, 1, 2])
    winter.ingredients = [RecipeIngredient(ingredient=winter_ing, recipe=winter)]

    summer = Recipe(title="Summer", servings_default=1, course="main")
    summer_ing = Ingredient(name="summer-veg", season_months=[6, 7, 8])
    summer.ingredients = [RecipeIngredient(ingredient=summer_ing, recipe=summer)]

    db_session.add_all([winter, summer])
    db_session.commit()

    kept = filter_recipes([winter, summer], season=7)
    assert [r.title for r in kept] == ["Summer"]


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
    )
    recent = Recipe(
        title="Recent",
        servings_default=1,
        score=1.2,
        bulk_prep=True,
        course="main",
    )
    db_session.add_all([fresh, recent])
    db_session.commit()

    db_session.add_all(
        [
            MealPlan(plan_date=date(2023, 12, 1)),
            Meal(plan_date=date(2023, 12, 1), meal_number=1, recipe_id=fresh.id),
            MealPlan(plan_date=date(2024, 1, 1)),
            Meal(plan_date=date(2024, 1, 1), meal_number=1, recipe_id=recent.id),
        ]
    )
    db_session.commit()
    start = date(2024, 1, 1)
    plan = generate_plan(
        db_session,
        start,
        days=1,
        meals_per_day=1,
        epsilon=0.0,
        recency_weight=0.0,
        min_recipe_gap=0,
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
        min_recipe_gap=0,
    )
    # Heavier penalty pushes the fresher recipe to the top
    assert plan["2024-01-01"] == ["Fresh"]


def test_leftover_ignores_recency_penalty(db_session):
    bulk = Recipe(
        title="Bulk",
        servings_default=1,
        score=5.0,
        bulk_prep=True,
        course="main",
    )
    other = Recipe(
        title="Other",
        servings_default=1,
        score=4.0,
        bulk_prep=False,
        course="main",
    )
    db_session.add_all([bulk, other])
    db_session.commit()
    start = date(2024, 1, 1)
    kwargs = dict(
        days=2,
        meals_per_day=1,
        epsilon=0.0,
        min_recipe_gap=0,
        plan_settings={"LEFTOVER_SPACING_GAP": 1},
    )
    plan = generate_plan(db_session, start, **kwargs)
    assert plan == {
        "2024-01-01": ["Bulk"],
        "2024-01-02": ["Bulk"],
    }
    slots = generate_plan(db_session, start, return_slots=True, **kwargs)
    assert [s.leftover for s in slots] == [False, True]


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
    kwargs = dict(
        days=4,
        meals_per_day=1,
        epsilon=0.0,
        keep_days=2,
        min_recipe_gap=0,
        plan_settings={"LEFTOVER_SPACING_GAP": 1},
    )
    plan = generate_plan(db_session, start, **kwargs)
    assert plan == {
        "2024-01-01": ["Bulk"],
        "2024-01-02": ["Bulk"],
        "2024-01-03": ["Bulk"],
        "2024-01-04": ["Bulk"],
    }
    slots = generate_plan(db_session, start, return_slots=True, **kwargs)
    assert [s.leftover for s in slots] == [False, True, False, True]


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
        min_recipe_gap=0,
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


def test_generate_plan_gap_filter(db_session):
    r1 = Recipe(title="R1", servings_default=1, score=5.0, course="main")
    r2 = Recipe(title="R2", servings_default=1, score=1.0, course="main")
    db_session.add_all([r1, r2])
    db_session.commit()

    hist_date = date(2024, 1, 1)
    plan = MealPlan(plan_date=hist_date)
    meal = Meal(meal_number=1, recipe=r1, leftover=False)
    plan.meals.append(meal)
    db_session.add(plan)
    db_session.commit()

    start = date(2024, 1, 2)
    schedule = generate_plan(
        db_session,
        start,
        days=1,
        meals_per_day=1,
        epsilon=0.0,
        min_recipe_gap=5,
    )
    assert schedule["2024-01-02"] == ["R2"]


def test_generate_plan_gap_filter_fallback(db_session):
    r1 = Recipe(title="R1", servings_default=1, score=5.0, course="main")
    db_session.add(r1)
    db_session.commit()

    hist_date = date(2024, 1, 1)
    plan = MealPlan(plan_date=hist_date)
    meal = Meal(meal_number=1, recipe=r1, leftover=False)
    plan.meals.append(meal)
    db_session.add(plan)
    db_session.commit()

    start = date(2024, 1, 2)
    schedule = generate_plan(
        db_session,
        start,
        days=1,
        meals_per_day=1,
        epsilon=0.0,
        min_recipe_gap=5,
    )
    assert schedule["2024-01-02"] == ["R1"]


def _recipe_with_ingredient(title, score, ingredient, tags=None):
    r = Recipe(title=title, servings_default=1, score=score, course="main")
    r.ingredients = [RecipeIngredient(ingredient=ingredient, recipe=r)]
    if tags:
        r.tags = tags
    return r


def test_ingredient_repetition_penalty_diverges_second_day(db_session):
    """A shared ingredient should push the later slot toward a diverging dish."""
    shared = Ingredient(name="shared-veg")
    other = Ingredient(name="other-veg")
    starter = _recipe_with_ingredient("Starter", 5.0, shared)
    p = _recipe_with_ingredient("P", 1.0, shared)
    q = _recipe_with_ingredient("Q", 0.9, other)
    db_session.add_all([starter, p, q])
    db_session.commit()

    start = date(2024, 6, 1)
    kwargs = dict(days=2, meals_per_day=1, epsilon=0.0, seasonality_weight=0.0)

    # Without the ingredient penalty, day 2 keeps the higher-scoring P (shares
    # the ingredient with day 1's Starter).
    no_penalty = generate_plan(
        db_session, start, ingredient_repeat_weight=0.0, **kwargs
    )
    assert no_penalty["2024-06-02"] == ["P"]

    # With a strong penalty, day 2 diverges to Q which uses a fresh ingredient.
    with_penalty = generate_plan(
        db_session, start, ingredient_repeat_weight=10.0, **kwargs
    )
    assert with_penalty["2024-06-02"] == ["Q"]


def test_ingredient_history_influences_first_slot(db_session):
    """A recently consumed ingredient recorded in ``meals`` penalises slot 1."""
    shared = Ingredient(name="hist-veg")
    other = Ingredient(name="fresh-veg")
    consumed = _recipe_with_ingredient("Consumed", 0.5, shared)
    p = _recipe_with_ingredient("P", 1.0, shared)
    q = _recipe_with_ingredient("Q", 0.9, other)
    db_session.add_all([consumed, p, q])
    db_session.commit()

    # Consumed yesterday, recording the shared ingredient in history.
    db_session.add_all([
        MealPlan(plan_date=date(2024, 5, 31)),
        Meal(plan_date=date(2024, 5, 31), meal_number=1, recipe_id=consumed.id),
    ])
    db_session.commit()

    start = date(2024, 6, 1)
    kwargs = dict(days=1, meals_per_day=1, epsilon=0.0, seasonality_weight=0.0)

    no_penalty = generate_plan(
        db_session, start, ingredient_repeat_weight=0.0, **kwargs
    )
    assert no_penalty["2024-06-01"] == ["P"]

    with_penalty = generate_plan(
        db_session, start, ingredient_repeat_weight=10.0, **kwargs
    )
    assert with_penalty["2024-06-01"] == ["Q"]


def test_tag_repetition_penalty_only_penalized_tags(db_session):
    """Format tags penalise repetition end-to-end; attribute tags do not."""
    pasta = Tag(name="pasta", penalize_repetition=True, is_system=True)
    veggie = Tag(name="vegetarian", penalize_repetition=False, is_system=True)
    ing = Ingredient(name="tag-veg")

    starter = _recipe_with_ingredient("Starter", 5.0, ing, tags=[pasta, veggie])
    another_pasta = _recipe_with_ingredient("Pasta2", 1.0, ing, tags=[pasta])
    veg_only = _recipe_with_ingredient("Veg2", 0.9, ing, tags=[veggie])
    db_session.add_all([starter, another_pasta, veg_only])
    db_session.commit()

    start = date(2024, 6, 1)
    kwargs = dict(days=2, meals_per_day=1, epsilon=0.0, seasonality_weight=0.0)

    # Ingredient penalty off to isolate the tag effect (all share one ingredient).
    no_penalty = generate_plan(
        db_session, start, tag_repeat_weight=0.0, ingredient_repeat_weight=0.0,
        **kwargs
    )
    assert no_penalty["2024-06-02"] == ["Pasta2"]

    with_penalty = generate_plan(
        db_session, start, tag_repeat_weight=10.0, ingredient_repeat_weight=0.0,
        **kwargs
    )
    # The repeated "pasta" format is penalised, so the vegetarian-only dish wins.
    assert with_penalty["2024-06-02"] == ["Veg2"]
