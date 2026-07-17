from datetime import date

from sqlalchemy import select

from mealplanner import planner
from crud import create_recipe, set_meal_plan, get_plan, mark_meal_accepted
from models import MealPlan, Meal, Recipe


def test_meal_plan_model_relationships(db_session, user):
    recipe = create_recipe(db_session, user_id=user.id, title="Toast", servings_default=1, course="main")
    plan = MealPlan(user_id=user.id, plan_date=date(2024, 1, 1))
    meal = Meal(meal_number=1, recipe=recipe, accepted=False)
    plan.meals.append(meal)
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)

    assert meal.plan_date == plan.plan_date
    assert plan.meals[0].recipe_id == recipe.id


def test_generate_and_persist_plan(db_session, user):
    for i in range(7):
        create_recipe(db_session, user_id=user.id, title=f"Meal {i}", servings_default=1, course="main")
    plan_date = date(2024, 5, 17)

    plan_titles = planner.generate_plan(
        db_session, start=plan_date, days=1, meals_per_day=2, user_id=user.id
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
    set_meal_plan(db_session, id_plan, user.id)
    fetched = get_plan(db_session, plan_date, user_id=user.id)
    expected = {
        day: [
            {
                "recipe": title,
                "side_recipes": [],
                "accepted": False,
                "leftover": False,
            }
            for title in meals
        ]
        for day, meals in plan_titles.items()
    }
    assert fetched == expected
    # Only one MealPlan should exist per date
    assert db_session.query(MealPlan).count() == len(plan_titles)
    for day, ids in id_plan.items():
        d = date.fromisoformat(day)
        for idx, rid in enumerate(ids, start=1):
            meal = db_session.get(Meal, (user.id, d, idx))
            assert meal is not None and meal.recipe_id == rid and meal.meal_number == idx


def test_duplicate_titles_do_not_break_plan(db_session, user):
    """Generating a plan works even if recipe titles are duplicated."""
    create_recipe(db_session, user_id=user.id, title="Dup", servings_default=1, course="main")
    # duplicate title intentionally
    create_recipe(db_session, user_id=user.id, title="Dup", servings_default=1, course="main")

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
    set_meal_plan(db_session, id_plan, user.id)
    fetched = get_plan(db_session, plan_date, user_id=user.id)
    expected = {
        day: [
            {
                "recipe": title,
                "side_recipes": [],
                "accepted": False,
                "leftover": False,
            }
            for title in meals
        ]
        for day, meals in plan_titles.items()
    }
    assert fetched == expected
    assert db_session.query(MealPlan).count() == len(plan_titles)
    for day, ids in id_plan.items():
        d = date.fromisoformat(day)
        for idx, rid in enumerate(ids, start=1):
            meal = db_session.get(Meal, (user.id, d, idx))
            assert meal is not None and meal.recipe_id == rid


def test_mark_meal_accepted(db_session, user):
    r = create_recipe(db_session, user_id=user.id, title="Meal", servings_default=1, course="main")
    plan_date = date(2024, 5, 19)
    set_meal_plan(db_session, {plan_date.isoformat(): [r.id]}, user.id)
    meal = mark_meal_accepted(db_session, plan_date, 1, True, user.id)
    assert meal is not None and meal.accepted is True
    fetched = get_plan(db_session, plan_date, user_id=user.id)
    assert fetched == {
        plan_date.isoformat(): [
            {
                "recipe": r.title,
                "side_recipes": [],
                "accepted": True,
                "leftover": False,
            }
        ]
    }
    stored = db_session.get(Meal, (user.id, plan_date, 1))
    assert stored is not None and stored.accepted is True


def test_meal_with_side_recipe(db_session, user):
    main = create_recipe(db_session, user_id=user.id, title="Main", servings_default=1, course="main")
    side = create_recipe(db_session, user_id=user.id, title="Side", servings_default=1, course="main")
    plan_date = date(2024, 9, 1)
    set_meal_plan(
        db_session,
        {plan_date.isoformat(): [{"main_id": main.id, "side_ids": [side.id]}]},
        user.id,
    )
    fetched = get_plan(db_session, plan_date, user_id=user.id)
    assert fetched == {
        plan_date.isoformat(): [
            {
                "recipe": main.title,
                "side_recipes": [side.title],
                "accepted": False,
                "leftover": False,
            }
        ]
    }
    meal = db_session.get(Meal, (user.id, plan_date, 1))
    assert (
        meal is not None
        and meal.recipe_id == main.id
        and meal.side_recipe_id == side.id
        and meal.side_recipe is not None
    )


def test_leftover_persistence(db_session, user):
    """A leftover is persisted as a link to its source meal on an earlier day."""
    main = create_recipe(db_session, user_id=user.id, title="Main", servings_default=1, course="main")
    source_date = date(2024, 9, 2)
    leftover_date = date(2024, 9, 3)
    set_meal_plan(
        db_session,
        {
            source_date.isoformat(): [{"main_id": main.id, "leftover": False}],
            leftover_date.isoformat(): [{"main_id": main.id, "leftover": True}],
        },
        user.id,
    )
    fetched = get_plan(
        db_session, start_date=source_date, end_date=leftover_date, user_id=user.id
    )
    assert fetched[source_date.isoformat()][0]["leftover"] is False
    assert fetched[leftover_date.isoformat()][0]["leftover"] is True

    leftover = db_session.get(Meal, (user.id, leftover_date, 1))
    assert leftover is not None and leftover.leftover is True
    assert leftover.leftover_source_date == source_date
    assert leftover.leftover_source_meal == 1


def test_delete_plan_cascades_meals(db_session, user):
    """Deleting a meal plan should remove associated meals."""
    recipe = create_recipe(db_session, user_id=user.id, title="Stew", servings_default=2, course="main")
    plan = MealPlan(user_id=user.id, plan_date=date(2024, 6, 1))
    meal = Meal(meal_number=1, recipe=recipe, accepted=False)
    plan.meals.append(meal)
    db_session.add(plan)
    db_session.commit()
    pdate = plan.plan_date

    db_session.delete(plan)
    db_session.commit()

    assert db_session.get(MealPlan, (user.id, pdate)) is None
    remaining = db_session.get(Meal, (user.id, pdate, 1))
    assert remaining is None


def test_delete_plan_removes_all_meals(db_session, user):
    """Deleting a plan removes all related meal entries."""
    recipe1 = create_recipe(db_session, user_id=user.id, title="Soup", servings_default=1, course="main")
    recipe2 = create_recipe(db_session, user_id=user.id, title="Salad", servings_default=1, course="main")
    plan = MealPlan(user_id=user.id, plan_date=date(2024, 8, 2))
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

    assert db_session.get(MealPlan, (user.id, pdate)) is None
    meals = db_session.execute(select(Meal).where(Meal.plan_date == pdate)).scalars().all()
    assert meals == []


def test_set_meal_plan_overwrites_existing(db_session, user):
    r1 = create_recipe(db_session, user_id=user.id, title="Old", servings_default=1, course="main")
    r2 = create_recipe(db_session, user_id=user.id, title="New", servings_default=1, course="main")
    plan_date = date(2024, 7, 1)
    set_meal_plan(db_session, {plan_date.isoformat(): [r1.id]}, user.id)
    set_meal_plan(db_session, {plan_date.isoformat(): [r2.id]}, user.id)
    assert db_session.query(MealPlan).count() == 1
    meal = db_session.get(Meal, (user.id, plan_date, 1))
    assert meal is not None and meal.recipe_id == r2.id


def test_overwriting_plan_resets_acceptance(db_session, user):
    """Replacing an existing plan clears previous acceptance status."""
    r1 = create_recipe(db_session, user_id=user.id, title="Old", servings_default=1, course="main")
    r2 = create_recipe(db_session, user_id=user.id, title="New", servings_default=1, course="main")
    plan_date = date(2024, 7, 2)
    set_meal_plan(db_session, {plan_date.isoformat(): [r1.id]}, user.id)
    mark_meal_accepted(db_session, plan_date, 1, True, user.id)
    set_meal_plan(db_session, {plan_date.isoformat(): [r2.id]}, user.id)
    meal = db_session.get(Meal, (user.id, plan_date, 1))
    assert meal is not None and meal.recipe_id == r2.id and meal.accepted is False
