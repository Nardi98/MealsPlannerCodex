"""Tests for meal acceptance endpoints."""

import os
from datetime import date

import crud


def test_toggle_meal_acceptance(client, db_session, user_token_factory):
    auth = user_token_factory()
    user_id = auth.user["id"]
    recipe = crud.create_recipe(
        db_session, title="A", servings_default=1, course="main", user=user_id
    )
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(
        db_session, {plan_date.isoformat(): [recipe.id]}, user=user_id
    )

    os.makedirs("data", exist_ok=True)

    resp = client.post(
        "/meal-plans/accept",
        json={"plan_date": "2024-01-01", "meal_number": 1, "accepted": True},
        headers=auth.headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "recipe": "A",
        "side_recipes": [],
        "accepted": True,
        "leftover": False,
    }

    resp2 = client.get(
        "/plan",
        params={"plan_date": "2024-01-01"},
        headers=auth.headers,
    )
    assert resp2.status_code == 200
    assert resp2.json() == {
        "2024-01-01": [
            {
                "recipe": "A",
                "side_recipes": [],
                "accepted": True,
                "leftover": False,
            }
        ]
    }


def test_acceptance_requires_authentication(client):
    response = client.post(
        "/meal-plans/accept",
        json={"plan_date": "2024-01-01", "meal_number": 1, "accepted": True},
    )
    assert response.status_code == 401
