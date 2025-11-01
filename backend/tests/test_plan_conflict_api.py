"""Tests for detecting conflicts when posting meal plans."""

import os
from datetime import date

import crud
from mealplanner.models import MealPlan, Meal


def test_post_meal_plan_conflict_requires_force(
    client, db_session, user_token_factory
):
    auth = user_token_factory()
    user_id = auth.user["id"]
    r1 = crud.create_recipe(
        db_session, title="A", servings_default=1, course="main", user=user_id
    )
    r2 = crud.create_recipe(
        db_session, title="B", servings_default=1, course="main", user=user_id
    )
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(
        db_session, {plan_date.isoformat(): [r1.id]}, user=user_id
    )

    os.makedirs("data", exist_ok=True)

    payload = {
        "plan_date": plan_date.isoformat(),
        "plan": {plan_date.isoformat(): [{"main_id": r2.id}]},
    }
    resp = client.post("/meal-plans", json=payload, headers=auth.headers)
    assert resp.status_code == 409
    assert resp.json()["conflicts"] == [plan_date.isoformat()]

    resp2 = client.post(
        "/meal-plans?force=true", json=payload, headers=auth.headers
    )
    assert resp2.status_code == 200
    resp3 = client.get(
        "/plan",
        params={"plan_date": plan_date.isoformat()},
        headers=auth.headers,
    )
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
    meal = db_session.get(Meal, (user_id, plan_date, 1))
    assert meal is not None and meal.recipe_id == r2.id


def test_plan_conflict_requires_authentication(client):
    payload = {
        "plan_date": "2024-01-01",
        "plan": {"2024-01-01": [{"main_id": 1}]},
    }
    assert client.post("/meal-plans", json=payload).status_code == 401
