from datetime import date

from sqlalchemy import select

from mealplanner import planner
from mealplanner.crud import create_recipe, set_meal_plan, get_plan
from mealplanner.models import MealPlan, MealSlot, Recipe


def test_meal_plan_model_relationships(db_session):
    recipe = create_recipe(db_session, title="Toast", servings_default=1)
    plan = MealPlan(plan_date=date(2024, 1, 1))
    slot = MealSlot(meal_time="breakfast", recipe=recipe)
    plan.slots.append(slot)
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)

    assert slot.plan_date == plan.plan_date
    assert plan.slots[0].recipe_id == recipe.id


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
    set_meal_plan(db_session, plan_date, id_plan)
    fetched = get_plan(db_session, plan_date)
    assert fetched == plan_titles


def test_duplicate_titles_do_not_break_plan(db_session):
    """Generating a plan works even if recipe titles are duplicated."""
    create_recipe(db_session, title="Dup", servings_default=1)
    # duplicate title intentionally
    create_recipe(db_session, title="Dup", servings_default=1)

    plan_date = date(2024, 5, 18)
    plan_titles = {"Mon": ["Dup"]}

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
    set_meal_plan(db_session, plan_date, id_plan)
    fetched = get_plan(db_session, plan_date)
    assert fetched == plan_titles


def test_delete_plan_cascades_slots(db_session):
    """Deleting a meal plan should remove associated slots."""
    recipe = create_recipe(db_session, title="Stew", servings_default=2)
    plan = MealPlan(plan_date=date(2024, 6, 1))
    slot = MealSlot(meal_time="dinner", recipe=recipe)
    plan.slots.append(slot)
    db_session.add(plan)
    db_session.commit()
    pid = plan.plan_date

    db_session.delete(plan)
    db_session.commit()

    assert db_session.get(MealPlan, pid) is None
    remaining = db_session.execute(
        select(MealSlot).where(MealSlot.plan_date == pid)
    ).first()
    assert remaining is None


def test_set_meal_plan_overwrites_existing(db_session):
    """Setting a plan for an existing date replaces the previous one."""
    r1 = create_recipe(db_session, title="First", servings_default=1)
    r2 = create_recipe(db_session, title="Second", servings_default=1)
    plan_date = date(2024, 7, 1)

    set_meal_plan(db_session, plan_date, {"breakfast": [r1.id]})
    set_meal_plan(db_session, plan_date, {"breakfast": [r2.id]})

    assert db_session.query(MealPlan).count() == 1
    assert get_plan(db_session, plan_date) == {"breakfast": ["Second"]}
