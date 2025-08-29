import os
from datetime import date
from fastapi.testclient import TestClient

import crud
from main import app, get_db
from mealplanner.models import MealPlan, Meal


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
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [{"main": r1.id, "sides": []}]})

    os.makedirs("data", exist_ok=True)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

    payload = {
        "plan_date": plan_date.isoformat(),
        "plan": {plan_date.isoformat(): [{"main": r2.id, "sides": []}]},
    }
    resp = client.post("/meal-plans", json=payload)
    assert resp.status_code == 409
    assert resp.json()["conflicts"] == [plan_date.isoformat()]

    resp2 = client.post("/meal-plans?force=true", json=payload)
    assert resp2.status_code == 200
    resp3 = client.get("/plan", params={"plan_date": plan_date.isoformat()})
    assert resp3.status_code == 200
    assert resp3.json() == {
        plan_date.isoformat(): [{"main": "B", "sides": [], "accepted": False}]
    }
    assert db_session.query(MealPlan).count() == 1
    meal = db_session.get(Meal, (plan_date, 1))
    assert meal is not None and meal.main_recipe_id == r2.id

    app.dependency_overrides.clear()
