from datetime import date

from sqlalchemy import select

from mealplanner import planner
from mealplanner.crud import create_recipe, set_meal_plan, get_plan, mark_meal_accepted
from mealplanner.models import MealPlan, Meal, Recipe


def test_meal_plan_model_relationships(db_session):
    recipe = create_recipe(db_session, title="Toast", servings_default=1)
    plan = MealPlan(plan_date=date(2024, 1, 1))
    meal = Meal(meal_number=1, recipe=recipe, accepted=False)
    plan.meals.append(meal)
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)

    assert meal.plan_date == plan.plan_date
    assert plan.meals[0].recipe_id == recipe.id


def test_generate_and_persist_plan(db_session):
    for i in range(7):
        create_recipe(db_session, title=f"Meal {i}", servings_default=1)
    plan_date = date(2024, 5, 17)

    plan_titles = planner.generate_plan(
        db_session, start=plan_date, days=1, meals_per_day=2
    )
    id_plan = {}
    for day, meals in plan_titles.items():
        ids: list[int] = []
        for meal in meals:
            recipe_id = (
                db_session.execute(
                    select(Recipe.id).where(Recipe.title == meal)
                )
                .scalars()
                .first()
            )
            assert recipe_id is not None
            ids.append(recipe_id)
        id_plan[day] = ids
    set_meal_plan(db_session, id_plan)
    fetched = get_plan(db_session, plan_date)
    expected = {
        day: [{"recipe": title, "accepted": False} for title in meals]
        for day, meals in plan_titles.items()
    }
    assert fetched == expected
    # Only one MealPlan should exist per date
    assert db_session.query(MealPlan).count() == len(plan_titles)
    for day, ids in id_plan.items():
        d = date.fromisoformat(day)
        for idx, rid in enumerate(ids, start=1):
            meal = db_session.get(Meal, (d, idx))
            assert meal is not None and meal.recipe_id == rid and meal.meal_number == idx


def test_duplicate_titles_do_not_break_plan(db_session):
    """Generating a plan works even if recipe titles are duplicated."""
    create_recipe(db_session, title="Dup", servings_default=1)
    # duplicate title intentionally
    create_recipe(db_session, title="Dup", servings_default=1)

    plan_date = date(2024, 5, 18)
    plan_titles = {plan_date.isoformat(): ["Dup"]}

    id_plan: dict[str, list[int]] = {}
    for day, meals in plan_titles.items():
        ids: list[int] = []
        for meal in meals:
            recipe_id = (
                db_session.execute(
                    select(Recipe.id).where(Recipe.title == meal)
                )
                .scalars()
                .first()
            )
            assert recipe_id is not None
            ids.append(recipe_id)
        id_plan[day] = ids
    set_meal_plan(db_session, id_plan)
    fetched = get_plan(db_session, plan_date)
    expected = {
        day: [{"recipe": title, "accepted": False} for title in meals]
        for day, meals in plan_titles.items()
    }
    assert fetched == expected
    assert db_session.query(MealPlan).count() == len(plan_titles)
    for day, ids in id_plan.items():
        d = date.fromisoformat(day)
        for idx, rid in enumerate(ids, start=1):
            meal = db_session.get(Meal, (d, idx))
            assert meal is not None and meal.recipe_id == rid


def test_mark_meal_accepted(db_session):
    r = create_recipe(db_session, title="Meal", servings_default=1)
    plan_date = date(2024, 5, 19)
    set_meal_plan(db_session, {plan_date.isoformat(): [r.id]})
    meal = mark_meal_accepted(db_session, plan_date, 1, True)
    assert meal is not None and meal.accepted is True
    fetched = get_plan(db_session, plan_date)
    assert fetched == {plan_date.isoformat(): [{"recipe": r.title, "accepted": True}]}
    stored = db_session.get(Meal, (plan_date, 1))
    assert stored is not None and stored.accepted is True


def test_delete_plan_cascades_meals(db_session):
    """Deleting a meal plan should remove associated meals."""
    recipe = create_recipe(db_session, title="Stew", servings_default=2)
    plan = MealPlan(plan_date=date(2024, 6, 1))
    meal = Meal(meal_number=1, recipe=recipe, accepted=False)
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
    recipe1 = create_recipe(db_session, title="Soup", servings_default=1)
    recipe2 = create_recipe(db_session, title="Salad", servings_default=1)
    plan = MealPlan(plan_date=date(2024, 8, 2))
    plan.meals.extend(
        [
            Meal(meal_number=1, recipe=recipe1, accepted=False),
            Meal(meal_number=2, recipe=recipe2, accepted=False),
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
    r1 = create_recipe(db_session, title="Old", servings_default=1)
    r2 = create_recipe(db_session, title="New", servings_default=1)
    plan_date = date(2024, 7, 1)
    set_meal_plan(db_session, {plan_date.isoformat(): [r1.id]})
    set_meal_plan(db_session, {plan_date.isoformat(): [r2.id]})
    assert db_session.query(MealPlan).count() == 1
    meal = db_session.get(Meal, (plan_date, 1))
    assert meal is not None and meal.recipe_id == r2.id
