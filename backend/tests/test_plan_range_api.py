"""Tests for retrieving meal plans over a date range."""

import os
from datetime import date, timedelta

import crud


def test_get_plan_range_requires_authentication(client):
    response = client.get(
        "/plan",
        params={"start_date": "2024-01-01", "end_date": "2024-01-02"},
    )
    assert response.status_code == 401


def test_get_plan_range(client, db_session, user_token_factory):
    auth = user_token_factory()
    user_id = auth.user["id"]

    r1 = crud.create_recipe(
        db_session, title="A", servings_default=1, course="main", user=user_id
    )
    r2 = crud.create_recipe(
        db_session, title="B", servings_default=1, course="main", user=user_id
    )
    start = date(2024, 1, 1)
    second = start + timedelta(days=1)
    crud.set_meal_plan(
        db_session,
        {
            start.isoformat(): [r1.id],
            second.isoformat(): [r2.id],
        },
        user=user_id,
    )

    os.makedirs("data", exist_ok=True)

    resp = client.get(
        "/plan",
        params={"start_date": start.isoformat(), "end_date": second.isoformat()},
        headers=auth.headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {
        start.isoformat(): [
            {
                "recipe": "A",
                "side_recipes": [],
                "accepted": False,
                "leftover": False,
            }
        ],
        second.isoformat(): [
            {
                "recipe": "B",
                "side_recipes": [],
                "accepted": False,
                "leftover": False,
            }
        ],
    }
