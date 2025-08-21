import pytest

from mealplanner.models import Recipe, Ingredient, Tag
from mealplanner.planner import generate_weekly_plan


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
