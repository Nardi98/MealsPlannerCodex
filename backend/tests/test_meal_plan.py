from datetime import date
from uuid import uuid4

from sqlalchemy import select

from mealplanner import planner
from mealplanner.crud import (
    create_recipe,
    create_user,
    get_plan,
    mark_meal_accepted,
    set_meal_plan,
)
from mealplanner.models import MealPlan, Meal, Recipe


def test_meal_plan_model_relationships(db_session):
    recipe = create_recipe(db_session, title="Toast", servings_default=1, course="main")
    plan = MealPlan(plan_date=date(2024, 1, 1), user_id=recipe.user_id)
    meal = Meal(
        user_id=recipe.user_id,
        plan_date=plan.plan_date,
        meal_number=1,
        recipe=recipe,
        accepted=False,
    )
    plan.meals.append(meal)
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)

    assert meal.plan_date == plan.plan_date
    assert plan.meals[0].recipe_id == recipe.id


def test_generate_and_persist_plan(db_session):
    recipes = [
        create_recipe(db_session, title=f"Meal {i}", servings_default=1, course="main")
        for i in range(7)
    ]
    assert recipes, "Expected at least one recipe to generate a plan"
    user_id = recipes[0].user_id
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
            meal = db_session.get(Meal, (user_id, d, idx))
            assert meal is not None and meal.recipe_id == rid and meal.meal_number == idx


def test_duplicate_titles_do_not_break_plan(db_session):
    """Generating a plan works even if recipe titles are duplicated."""
    first = create_recipe(db_session, title="Dup", servings_default=1, course="main")
    # duplicate title intentionally
    create_recipe(db_session, title="Dup", servings_default=1, course="main")
    user_id = first.user_id

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
            meal = db_session.get(Meal, (user_id, d, idx))
            assert meal is not None and meal.recipe_id == rid


def test_mark_meal_accepted(db_session):
    r = create_recipe(db_session, title="Meal", servings_default=1, course="main")
    plan_date = date(2024, 5, 19)
    set_meal_plan(db_session, {plan_date.isoformat(): [r.id]})
    meal = mark_meal_accepted(db_session, plan_date, 1, True)
    assert meal is not None and meal.accepted is True
    fetched = get_plan(db_session, plan_date)
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
    stored = db_session.get(Meal, (r.user_id, plan_date, 1))
    assert stored is not None and stored.accepted is True


def test_meal_with_side_recipe(db_session):
    main = create_recipe(db_session, title="Main", servings_default=1, course="main")
    side = create_recipe(db_session, title="Side", servings_default=1, course="main")
    user_id = main.user_id
    plan_date = date(2024, 9, 1)
    set_meal_plan(
        db_session,
        {plan_date.isoformat(): [{"main_id": main.id, "side_ids": [side.id]}]},
    )
    fetched = get_plan(db_session, plan_date)
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
    meal = db_session.get(Meal, (user_id, plan_date, 1))
    assert (
        meal is not None
        and meal.recipe_id == main.id
        and meal.side_recipe_id == side.id
        and meal.side_recipe is not None
    )


def test_leftover_persistence(db_session):
    main = create_recipe(db_session, title="Main", servings_default=1, course="main")
    plan_date = date(2024, 9, 2)
    set_meal_plan(
        db_session,
        {plan_date.isoformat(): [{"main_id": main.id, "leftover": True}]},
    )
    fetched = get_plan(db_session, plan_date)
    assert fetched == {
        plan_date.isoformat(): [
            {
                "recipe": main.title,
                "side_recipes": [],
                "accepted": False,
                "leftover": True,
            }
        ]
    }
    meal = db_session.get(Meal, (main.user_id, plan_date, 1))
    assert meal is not None and meal.leftover is True


def test_delete_plan_cascades_meals(db_session):
    """Deleting a meal plan should remove associated meals."""
    recipe = create_recipe(db_session, title="Stew", servings_default=2, course="main")
    plan = MealPlan(plan_date=date(2024, 6, 1), user_id=recipe.user_id)
    meal = Meal(
        user_id=recipe.user_id,
        plan_date=plan.plan_date,
        meal_number=1,
        recipe=recipe,
        accepted=False,
    )
    plan.meals.append(meal)
    db_session.add(plan)
    db_session.commit()
    pdate = plan.plan_date

    db_session.delete(plan)
    db_session.commit()

    assert db_session.get(MealPlan, (recipe.user_id, pdate)) is None
    remaining = db_session.get(Meal, (recipe.user_id, pdate, 1))
    assert remaining is None


def test_delete_plan_removes_all_meals(db_session):
    """Deleting a plan removes all related meal entries."""
    recipe1 = create_recipe(db_session, title="Soup", servings_default=1, course="main")
    recipe2 = create_recipe(db_session, title="Salad", servings_default=1, course="main")
    user_id = recipe1.user_id
    plan = MealPlan(plan_date=date(2024, 8, 2), user_id=user_id)
    plan.meals.extend(
        [
            Meal(
                user_id=user_id,
                plan_date=plan.plan_date,
                meal_number=1,
                recipe=recipe1,
                accepted=False,
            ),
            Meal(
                user_id=user_id,
                plan_date=plan.plan_date,
                meal_number=2,
                recipe=recipe2,
                accepted=False,
            ),
        ]
    )
    db_session.add(plan)
    db_session.commit()
    pdate = plan.plan_date

    db_session.delete(plan)
    db_session.commit()

    assert db_session.get(MealPlan, (user_id, pdate)) is None
    meals = (
        db_session.execute(
            select(Meal).where(Meal.plan_date == pdate, Meal.user_id == user_id)
        )
        .scalars()
        .all()
    )
    assert meals == []


def test_set_meal_plan_overwrites_existing(db_session):
    r1 = create_recipe(db_session, title="Old", servings_default=1, course="main")
    r2 = create_recipe(db_session, title="New", servings_default=1, course="main")
    plan_date = date(2024, 7, 1)
    set_meal_plan(db_session, {plan_date.isoformat(): [r1.id]})
    set_meal_plan(db_session, {plan_date.isoformat(): [r2.id]})
    assert db_session.query(MealPlan).count() == 1
    meal = db_session.get(Meal, (r2.user_id, plan_date, 1))
    assert meal is not None and meal.recipe_id == r2.id


def test_overwriting_plan_resets_acceptance(db_session):
    """Replacing an existing plan clears previous acceptance status."""
    r1 = create_recipe(db_session, title="Old", servings_default=1, course="main")
    r2 = create_recipe(db_session, title="New", servings_default=1, course="main")
    plan_date = date(2024, 7, 2)
    set_meal_plan(db_session, {plan_date.isoformat(): [r1.id]})
    mark_meal_accepted(db_session, plan_date, 1, True)
    set_meal_plan(db_session, {plan_date.isoformat(): [r2.id]})
    meal = db_session.get(Meal, (r2.user_id, plan_date, 1))
    assert meal is not None and meal.recipe_id == r2.id and meal.accepted is False


def test_meal_plan_isolation_between_users(db_session):
    suffix1 = uuid4().hex
    suffix2 = uuid4().hex
    user1 = create_user(
        db_session,
        email=f"planner-{suffix1}@example.com",
        username=f"planner-{suffix1}",
        password="Password123!",
    )
    user2 = create_user(
        db_session,
        email=f"planner-{suffix2}@example.com",
        username=f"planner-{suffix2}",
        password="Password123!",
    )

    plan_date = date(2024, 10, 1)
    recipe1 = create_recipe(
        db_session,
        title="User1 Meal",
        servings_default=1,
        course="main",
        user=user1,
    )
    recipe2 = create_recipe(
        db_session,
        title="User2 Meal",
        servings_default=1,
        course="main",
        user=user2,
    )

    set_meal_plan(db_session, {plan_date.isoformat(): [recipe1.id]}, user=user1)
    set_meal_plan(db_session, {plan_date.isoformat(): [recipe2.id]}, user=user2)

    user1_plan = get_plan(db_session, plan_date, user=user1)
    user2_plan = get_plan(db_session, plan_date, user=user2)

    expected_entry1 = {
        "recipe": recipe1.title,
        "side_recipes": [],
        "accepted": False,
        "leftover": False,
    }
    expected_entry2 = {
        "recipe": recipe2.title,
        "side_recipes": [],
        "accepted": False,
        "leftover": False,
    }

    assert user1_plan == {plan_date.isoformat(): [expected_entry1]}
    assert user2_plan == {plan_date.isoformat(): [expected_entry2]}

    overlapping = db_session.query(MealPlan).filter(MealPlan.plan_date == plan_date)
    assert overlapping.count() == 2
