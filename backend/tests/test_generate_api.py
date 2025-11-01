"""Tests for the meal plan generation endpoint."""

import os

import crud


def test_generate_endpoint_requires_authentication(client):
    response = client.post(
        "/meal-plans/generate",
        json={"start": "2024-01-01", "end": "2024-01-01", "meals_per_day": 1},
    )
    assert response.status_code == 401


def test_generate_endpoint_returns_plan(client, db_session, user_token_factory):
    auth = user_token_factory()
    user_id = auth.user["id"]

    for i in range(3):
        crud.create_recipe(
            db_session,
            title=f"Meal {i}",
            servings_default=1,
            course="main",
            user=user_id,
        )

    os.makedirs("data", exist_ok=True)

    response = client.post(
        "/meal-plans/generate",
        json={"start": "2024-01-01", "end": "2024-01-01", "meals_per_day": 1},
        headers=auth.headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "2024-01-01" in data
    assert isinstance(data["2024-01-01"][0]["id"], int)
    assert data["2024-01-01"][0]["title"].startswith("Meal")
    assert data["2024-01-01"][0]["leftover"] is False
