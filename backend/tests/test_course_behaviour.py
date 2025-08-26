"""Tests covering course handling and side dish relationships in meal plans."""

from datetime import date
import random

from sqlalchemy import select

from mealplanner.planner import generate_plan
from mealplanner.crud import create_recipe, set_meal_plan
from mealplanner.models import Meal, MealSideDish, Recipe


def test_plan_includes_side_dishes_with_main_course(db_session):
    """A generated plan should attach side dishes to main courses."""

    main = Recipe(title="Main", servings_default=1, score=1.0, course="main course")
    side_a = Recipe(title="SideA", servings_default=1, score=1.0, course="side dish")
    side_b = Recipe(title="SideB", servings_default=1, score=1.0, course="side dish")
    db_session.add_all([main, side_a, side_b])
    db_session.commit()

    start = date(2024, 1, 1)
    random.seed(0)
    plan = generate_plan(db_session, start, days=1, meals_per_day=1, epsilon=0.0)

    titles = plan[start.isoformat()][0]
    assert titles[0] == "Main"
    assert set(titles[1:]) == {"SideA", "SideB"}


def test_removing_main_course_deletes_side_dishes(db_session):
    """Deleting a main course meal should cascade to its side dishes."""

    main = create_recipe(
        db_session, title="Mains", servings_default=1, course="main course"
    )
    side = create_recipe(
        db_session, title="Sides", servings_default=1, course="side dish"
    )
    plan_date = date(2024, 1, 2)
    set_meal_plan(
        db_session, {plan_date.isoformat(): [{"main": main.id, "sides": [side.id]}]}
    )

    meal = db_session.get(Meal, (plan_date, 1))
    assert meal is not None and meal.side_dishes
    db_session.delete(meal)
    db_session.commit()

    remaining = db_session.execute(
        select(MealSideDish).where(MealSideDish.plan_date == plan_date)
    ).scalars().all()
    assert remaining == []


def test_generate_plan_selects_only_first_and_main_courses(db_session):
    """Recipes with other course types should not appear as main plan entries."""

    main = Recipe(title="Main", servings_default=1, score=5.0, course="main course")
    first = Recipe(title="Starter", servings_default=1, score=4.0, course="first course")
    side = Recipe(title="Side", servings_default=1, score=10.0, course="side dish")
    dessert = Recipe(title="Dessert", servings_default=1, score=9.0, course="dessert")
    db_session.add_all([main, first, side, dessert])
    db_session.commit()

    start = date(2024, 1, 3)
    random.seed(0)
    plan = generate_plan(db_session, start, days=2, meals_per_day=1, epsilon=0.0)

    chosen = {plan_day[0][0] for plan_day in plan.values()}
    assert chosen == {"Main", "Starter"}
    assert "Dessert" not in chosen
    assert "Side" not in chosen


def test_course_names_case_insensitive(db_session):
    """Mixed-case course names should be treated the same as lower-case."""

    main = Recipe(title="Main", servings_default=1, score=2.0, course="Main Course")
    first = Recipe(title="Starter", servings_default=1, score=1.0, course="First Course")
    side = Recipe(title="Side", servings_default=1, score=1.0, course="Side Dish")
    db_session.add_all([main, first, side])
    db_session.commit()

    start = date(2024, 1, 1)
    random.seed(0)
    plan = generate_plan(db_session, start, days=2, meals_per_day=1, epsilon=0.0)

    assert plan["2024-01-01"][0][0] == "Main"
    assert plan["2024-01-01"][0][1:] == ["Side"]
    assert plan["2024-01-02"][0][0] == "Starter"


def test_course_name_variants(db_session):
    """Hyphenated or short course names are normalised for planning."""

    main = Recipe(title="Main", servings_default=1, score=2.0, course="main")
    first = Recipe(
        title="Starter", servings_default=1, score=1.0, course="first-course"
    )
    side = Recipe(title="Side", servings_default=1, score=1.0, course="side")
    db_session.add_all([main, first, side])
    db_session.commit()

    start = date(2024, 1, 1)
    random.seed(0)
    plan = generate_plan(db_session, start, days=2, meals_per_day=1, epsilon=0.0)

    assert plan["2024-01-01"][0][0] == "Main"
    assert plan["2024-01-01"][0][1:] == ["Side"]
    assert plan["2024-01-02"][0][0] == "Starter"

