import pytest
from datetime import date

from mealplanner.models import Recipe, Ingredient, Tag
from mealplanner.planner import generate_weekly_plan, generate_plan


def make_recipe(name, bulk=False, tags=None, season=None):
    r = Recipe(title=name, servings_default=2, bulk_prep=bulk)
    if tags:
        r.tags = [Tag(name=t) for t in tags]
    if season:
        months = ",".join(str(m) for m in season)
        r.ingredients = [Ingredient(name=f"{name}-ing", season_months=months)]
    return r


def test_non_repetition_and_bulk_prep():
    recipes = [make_recipe(f"R{i}") for i in range(4)]
    bulk_recipe = make_recipe("Bulk", bulk=True)
    recipes.append(bulk_recipe)
    plan = generate_weekly_plan(recipes)
    assert len(plan) == 7
    counts = {r.title: plan.count(r) for r in recipes}
    for r in recipes:
        if r.bulk_prep:
            assert counts[r.title] > 1
        else:
            assert counts[r.title] == 1


def test_seasonal_filtering():
    summer = make_recipe("Summer", bulk=True, season=[6, 7])
    winter = make_recipe("Winter", season=[12])
    plan = generate_weekly_plan([summer, winter], season=6)
    assert {r.title for r in plan} == {"Summer"}


def test_tag_filtering():
    vegan = make_recipe("VeganNB", tags=["vegan"])
    vegan_bulk = make_recipe("VeganBulk", bulk=True, tags=["vegan"])
    meat = make_recipe("Meat", tags=["meat"])
    plan = generate_weekly_plan([vegan, vegan_bulk, meat], tags={"vegan"})
    assert {r.title for r in plan} == {"VeganNB", "VeganBulk"}
    assert sum(1 for r in plan if r.title == "VeganNB") == 1


def test_avoid_tags_filtering():
    good = make_recipe("Good", bulk=True)
    bad = make_recipe("Bad", bulk=True, tags=["avoid"])
    plan = generate_weekly_plan([good, bad], avoid_tags={"avoid"})
    assert {r.title for r in plan} == {"Good"}


def test_reduce_tags_penalty(db_session):
    good = Recipe(title="Good", servings_default=1, score=1.0, bulk_prep=True)
    reduce = Recipe(title="Less", servings_default=1, score=1.4, bulk_prep=True)
    reduce.tags = [Tag(name="reduce")]
    db_session.add_all([good, reduce])
    db_session.commit()
    start = date(2024, 1, 1)
    plan = generate_plan(
        db_session,
        start,
        days=1,
        meals_per_day=1,
        epsilon=0.0,
        reduce_tags={"reduce"},
    )
    assert plan["2024-01-01"] == ["Good"]


def test_recency_weight(db_session):
    fresh = Recipe(
        title="Fresh",
        servings_default=1,
        score=1.0,
        bulk_prep=True,
        date_last_consumed=date(2023, 12, 1),
    )
    recent = Recipe(
        title="Recent",
        servings_default=1,
        score=1.2,
        bulk_prep=True,
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


def test_generate_plan_repeatable(db_session):
    for i, score in enumerate(range(7, 0, -1), start=1):
        db_session.add(Recipe(title=f"R{i}", servings_default=1, score=score))
    db_session.commit()
    start = date(2024, 1, 1)
    expected = {
        "2024-01-01": ["R1"],
        "2024-01-02": ["R2"],
        "2024-01-03": ["R3"],
    }
    plan1 = generate_plan(db_session, start, days=3, meals_per_day=1, epsilon=0.0)
    plan2 = generate_plan(db_session, start, days=3, meals_per_day=1, epsilon=0.0)
    assert plan1 == expected
    assert plan1 == plan2


def test_generate_weekly_plan_insufficient_recipes():
    """Generating a plan without enough recipes should raise an error."""
    recipes = [make_recipe("OnlyOne")]
    with pytest.raises(ValueError):
        generate_weekly_plan(recipes)
