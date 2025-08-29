from datetime import date

from sqlalchemy import select
from typing import Dict, List

from mealplanner import planner
from mealplanner.crud import create_recipe, set_meal_plan, get_plan, mark_meal_accepted
from mealplanner.models import MealPlan, Meal, Recipe


def test_meal_plan_model_relationships(db_session):
    recipe = create_recipe(db_session, title="Toast", servings_default=1, course="main")
    plan = MealPlan(plan_date=date(2024, 1, 1))
    meal = Meal(meal_number=1, main_recipe=recipe, accepted=False)
    plan.meals.append(meal)
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)

    assert meal.plan_date == plan.plan_date
    assert plan.meals[0].main_recipe_id == recipe.id


def test_generate_and_persist_plan(db_session):
    for i in range(7):
        create_recipe(db_session, title=f"Meal {i}", servings_default=1, course="main")
    plan_date = date(2024, 5, 17)

    plan_titles = planner.generate_plan(
        db_session, start=plan_date, days=1, meals_per_day=2
    )
    id_plan: Dict[str, List[Dict[str, int]]] = {}
    for day, meals in plan_titles.items():
        meal_entries: List[Dict[str, int]] = []
        for meal in meals:
            recipe_id = (
                db_session.execute(
                    select(Recipe.id).where(Recipe.title == meal["main"])
                )
                .scalars()
                .first()
            )
            assert recipe_id is not None
            meal_entries.append({"main": recipe_id, "sides": []})
        id_plan[day] = meal_entries
    set_meal_plan(db_session, id_plan)
    fetched = get_plan(db_session, plan_date)
    expected = {
        day: [
            {"main": meal["main"], "sides": [], "accepted": False}
            for meal in meals
        ]
        for day, meals in plan_titles.items()
    }
    assert fetched == expected
    # Only one MealPlan should exist per date
    assert db_session.query(MealPlan).count() == len(plan_titles)
    for day, meals_info in id_plan.items():
        d = date.fromisoformat(day)
        for idx, meal_info in enumerate(meals_info, start=1):
            meal = db_session.get(Meal, (d, idx))
            assert (
                meal is not None
                and meal.main_recipe_id == meal_info["main"]
                and meal.meal_number == idx
            )


def test_duplicate_titles_do_not_break_plan(db_session):
    """Generating a plan works even if recipe titles are duplicated."""
    create_recipe(db_session, title="Dup", servings_default=1, course="main")
    # duplicate title intentionally
    create_recipe(db_session, title="Dup", servings_default=1, course="main")

    plan_date = date(2024, 5, 18)
    plan_titles = {plan_date.isoformat(): [{"main": "Dup", "sides": []}]}

    id_plan: dict[str, list[dict[str, int]]] = {}
    for day, meals in plan_titles.items():
        entries: list[dict[str, int]] = []
        for meal in meals:
            recipe_id = (
                db_session.execute(
                    select(Recipe.id).where(Recipe.title == meal["main"])
                )
                .scalars()
                .first()
            )
            assert recipe_id is not None
            entries.append({"main": recipe_id, "sides": []})
        id_plan[day] = entries
    set_meal_plan(db_session, id_plan)
    fetched = get_plan(db_session, plan_date)
    expected = {
        day: [
            {"main": meal["main"], "sides": [], "accepted": False}
            for meal in meals
        ]
        for day, meals in plan_titles.items()
    }
    assert fetched == expected
    assert db_session.query(MealPlan).count() == len(plan_titles)
    for day, meals in id_plan.items():
        d = date.fromisoformat(day)
        for idx, meal_info in enumerate(meals, start=1):
            meal = db_session.get(Meal, (d, idx))
            assert meal is not None and meal.main_recipe_id == meal_info["main"]


def test_mark_meal_accepted(db_session):
    r = create_recipe(db_session, title="Meal", servings_default=1, course="main")
    plan_date = date(2024, 5, 19)
    set_meal_plan(db_session, {plan_date.isoformat(): [{"main": r.id, "sides": []}]})
    meal = mark_meal_accepted(db_session, plan_date, 1, True)
    assert meal is not None and meal.accepted is True
    fetched = get_plan(db_session, plan_date)
    assert fetched == {plan_date.isoformat(): [{"main": r.title, "sides": [], "accepted": True}]}
    stored = db_session.get(Meal, (plan_date, 1))
    assert stored is not None and stored.accepted is True


def test_save_and_retrieve_with_sides(db_session):
    main = create_recipe(db_session, title="Main", servings_default=1, course="main")
    side1 = create_recipe(db_session, title="Side1", servings_default=1, course="side")
    side2 = create_recipe(db_session, title="Side2", servings_default=1, course="side")
    plan_date = date(2024, 6, 1)
    set_meal_plan(
        db_session,
        {plan_date.isoformat(): [{"main": main.id, "sides": [side1.id, side2.id]}]},
    )
    fetched = get_plan(db_session, plan_date)
    assert fetched == {
        plan_date.isoformat(): [
            {"main": "Main", "sides": ["Side1", "Side2"], "accepted": False}
        ]
    }


def test_delete_plan_cascades_meals(db_session):
    """Deleting a meal plan should remove associated meals."""
    recipe = create_recipe(db_session, title="Stew", servings_default=2, course="main")
    plan = MealPlan(plan_date=date(2024, 6, 1))
    meal = Meal(meal_number=1, main_recipe=recipe, accepted=False)
    plan.meals.append(meal)
    db_session.add(plan)
    db_session.commit()
    pdate = plan.plan_date

    db_session.delete(plan)
    db_session.commit()

    assert db_session.get(MealPlan, pdate) is None
    remaining = db_session.get(Meal, (pdate, 1))
    assert remaining is None


def test_delete_plan_removes_all_meals(db_session):
    """Deleting a plan removes all related meal entries."""
    recipe1 = create_recipe(db_session, title="Soup", servings_default=1, course="main")
    recipe2 = create_recipe(db_session, title="Salad", servings_default=1, course="main")
    plan = MealPlan(plan_date=date(2024, 8, 2))
    plan.meals.extend(
        [
            Meal(meal_number=1, main_recipe=recipe1, accepted=False),
            Meal(meal_number=2, main_recipe=recipe2, accepted=False),
        ]
    )
    db_session.add(plan)
    db_session.commit()
    pdate = plan.plan_date

    db_session.delete(plan)
    db_session.commit()

    assert db_session.get(MealPlan, pdate) is None
    meals = db_session.execute(select(Meal).where(Meal.plan_date == pdate)).scalars().all()
    assert meals == []


def test_set_meal_plan_overwrites_existing(db_session):
    r1 = create_recipe(db_session, title="Old", servings_default=1, course="main")
    r2 = create_recipe(db_session, title="New", servings_default=1, course="main")
    plan_date = date(2024, 7, 1)
    set_meal_plan(db_session, {plan_date.isoformat(): [{"main": r1.id, "sides": []}]})
    set_meal_plan(db_session, {plan_date.isoformat(): [{"main": r2.id, "sides": []}]})
    assert db_session.query(MealPlan).count() == 1
    meal = db_session.get(Meal, (plan_date, 1))
    assert meal is not None and meal.main_recipe_id == r2.id
