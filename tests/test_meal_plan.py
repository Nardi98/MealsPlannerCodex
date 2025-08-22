from datetime import date

from sqlalchemy import select

from mealplanner.crud import create_recipe, set_meal_plan, get_plan
from mealplanner.models import MealPlan, MealSlot


def test_meal_plan_model_relationships(db_session):
    recipe = create_recipe(db_session, title="Toast", servings_default=1)
    plan = MealPlan(plan_date=date(2024, 1, 1))
    slot = MealSlot(meal_time="breakfast", recipe=recipe)
    plan.slots.append(slot)
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)

    assert plan.id is not None
    assert slot.meal_plan_id == plan.id
    assert plan.slots[0].recipe_id == recipe.id


def test_set_and_get_plan(db_session):
    r1 = create_recipe(db_session, title="Porridge", servings_default=1)
    r2 = create_recipe(db_session, title="Salad", servings_default=2)
    plan_date = date(2024, 5, 17)

    set_meal_plan(db_session, plan_date, {"breakfast": [r1.id], "lunch": [r2.id]})
    fetched = get_plan(db_session, plan_date)
    assert fetched == {"breakfast": ["Porridge"], "lunch": ["Salad"]}

    r3 = create_recipe(db_session, title="Soup", servings_default=2)
    set_meal_plan(db_session, plan_date, {"dinner": [r3.id]})
    fetched = get_plan(db_session, plan_date)
    assert fetched == {"dinner": ["Soup"]}


def test_delete_plan_cascades_slots(db_session):
    """Deleting a meal plan should remove associated slots."""
    recipe = create_recipe(db_session, title="Stew", servings_default=2)
    plan = MealPlan(plan_date=date(2024, 6, 1))
    slot = MealSlot(meal_time="dinner", recipe=recipe)
    plan.slots.append(slot)
    db_session.add(plan)
    db_session.commit()
    pid = plan.id

    db_session.delete(plan)
    db_session.commit()

    assert db_session.get(MealPlan, pid) is None
    remaining = db_session.execute(
        select(MealSlot).where(MealSlot.meal_plan_id == pid)
    ).first()
    assert remaining is None
