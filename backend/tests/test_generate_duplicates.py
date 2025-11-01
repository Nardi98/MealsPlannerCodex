"""Ensure meal plan generation handles duplicate recipe titles."""

import os

import crud


def test_generate_endpoint_handles_duplicate_titles(
    client, db_session, user_token_factory
):
    auth = user_token_factory()
    user_id = auth.user["id"]

    for _ in range(2):
        crud.create_recipe(
            db_session,
            title="Dup",
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
    assert isinstance(data["2024-01-01"][0]["title"], str)
