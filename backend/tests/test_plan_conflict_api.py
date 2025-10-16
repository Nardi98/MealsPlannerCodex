import os
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select

import crud
from main import app, get_db
from mealplanner.models import MealPlan, Meal, MealSide


def override_get_db(session):
    def _override():
        try:
            yield session
        finally:
            pass
    return _override


def test_post_meal_plan_conflict_requires_force(db_session):
    r1 = crud.create_recipe(db_session, title="A", servings_default=1, course="main")
    r2 = crud.create_recipe(db_session, title="B", servings_default=1, course="main")
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [r1.id]})

    os.makedirs("data", exist_ok=True)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

    payload = {
        "plan_date": plan_date.isoformat(),
        "plan": {plan_date.isoformat(): [{"main_id": r2.id}]},
    }
    resp = client.post("/meal-plans", json=payload)
    assert resp.status_code == 409
    assert resp.json()["conflicts"] == [plan_date.isoformat()]

    resp2 = client.post("/meal-plans?force=true", json=payload)
    assert resp2.status_code == 200
    resp3 = client.get("/plan", params={"plan_date": plan_date.isoformat()})
    assert resp3.status_code == 200
    assert resp3.json() == {
        plan_date.isoformat(): [
            {
                "recipe": "B",
                "side_recipes": [],
                "accepted": False,
                "leftover": False,
            }
        ]
    }
    assert db_session.query(MealPlan).count() == 1
    meal = db_session.get(Meal, (plan_date, 1))
    assert meal is not None and meal.recipe_id == r2.id

    app.dependency_overrides.clear()


def test_force_overwrite_only_removes_conflicting_dates(db_session):
    r1 = crud.create_recipe(db_session, title="A", servings_default=1, course="main")
    r2 = crud.create_recipe(db_session, title="B", servings_default=1, course="main")
    r3 = crud.create_recipe(db_session, title="C", servings_default=1, course="main")

    target_date = date(2024, 1, 1)
    keep_date = date(2024, 1, 2)
    crud.set_meal_plan(
        db_session,
        {
            target_date.isoformat(): [r1.id],
            keep_date.isoformat(): [r3.id],
        },
    )

    os.makedirs("data", exist_ok=True)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

    payload = {
        "plan_date": target_date.isoformat(),
        "plan": {target_date.isoformat(): [{"main_id": r2.id}]},
    }

    resp = client.post("/meal-plans?force=true", json=payload)
    assert resp.status_code == 200

    replaced_meal = db_session.get(Meal, (target_date, 1))
    assert replaced_meal is not None and replaced_meal.recipe_id == r2.id

    kept_meal = db_session.get(Meal, (keep_date, 1))
    assert kept_meal is not None and kept_meal.recipe_id == r3.id

    app.dependency_overrides.clear()


def test_delete_meal_plans_for_dates_clears_all_tables(db_session):
    main = crud.create_recipe(db_session, title="Main", servings_default=1, course="main")
    side = crud.create_recipe(db_session, title="Side", servings_default=1, course="main")

    plan_date = date(2024, 1, 3)
    crud.set_meal_plan(
        db_session,
        {
            plan_date.isoformat(): [
                {
                    "main_id": main.id,
                    "side_ids": [side.id],
                }
            ]
        },
    )

    assert db_session.get(MealPlan, plan_date) is not None
    assert db_session.get(Meal, (plan_date, 1)) is not None
    assert db_session.execute(
        select(MealSide).where(MealSide.plan_date == plan_date)
    ).first() is not None

    deleted = crud.delete_meal_plans_for_dates(db_session, [plan_date])
    assert deleted == 1

    assert db_session.get(MealPlan, plan_date) is None
    assert db_session.get(Meal, (plan_date, 1)) is None
    side_rows = db_session.execute(
        select(MealSide).where(MealSide.plan_date == plan_date)
    ).scalars().all()
    assert side_rows == []
