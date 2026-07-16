from datetime import date

import crud
from models import MealPlan, Meal


def test_post_meal_plan_conflict_requires_force(db_session, user, auth_client):
    r1 = crud.create_recipe(db_session, user_id=user.id, title="A", servings_default=1, course="main")
    r2 = crud.create_recipe(db_session, user_id=user.id, title="B", servings_default=1, course="main")
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [r1.id]}, user.id)

    client = auth_client

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
    meal = db_session.get(Meal, (user.id, plan_date, 1))
    assert meal is not None and meal.recipe_id == r2.id
