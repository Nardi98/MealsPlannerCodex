"""Tests for deleting meal plans via the API."""

import os
from datetime import date, timedelta

import crud
from mealplanner import planner
from mealplanner.models import Meal, MealPlan, User


def test_delete_meal_plans_requires_authentication(client):
    response = client.delete(
        "/meal-plans",
        params={"start_date": "2024-01-01", "end_date": "2024-01-02"},
    )
    assert response.status_code == 401


def test_delete_meal_plans_removes_rows_and_cache(
    client, db_session, user_token_factory
):
    auth = user_token_factory()
    user_id = auth.user["id"]

    main = crud.create_recipe(
        db_session, title="Main", servings_default=1, course="main", user=user_id
    )
    alt = crud.create_recipe(
        db_session, title="Alt", servings_default=1, course="main", user=user_id
    )
    side = crud.create_recipe(
        db_session, title="Side", servings_default=1, course="side", user=user_id
    )

    start = date(2024, 1, 1)
    second = start + timedelta(days=1)

    crud.set_meal_plan(
        db_session,
        {
            start.isoformat(): [{"main_id": main.id, "side_ids": [side.id]}],
            second.isoformat(): [{"main_id": alt.id}],
        },
        user=user_id,
    )

    user_obj = db_session.get(User, user_id)
    assert user_obj is not None
    crud.save_plan(
        {
            start.isoformat(): [
                {
                    "recipe": "Main",
                    "side_recipes": ["Side"],
                    "accepted": False,
                    "leftover": False,
                }
            ],
            second.isoformat(): [
                {
                    "recipe": "Alt",
                    "side_recipes": [],
                    "accepted": False,
                    "leftover": False,
                }
            ],
        },
        user=user_obj,
    )

    assert db_session.query(MealPlan).count() == 2

    os.makedirs("data", exist_ok=True)

    resp = client.delete(
        "/meal-plans",
        params={"start_date": start.isoformat(), "end_date": second.isoformat()},
        headers=auth.headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"deleted": 2}

    assert db_session.query(MealPlan).count() == 0
    assert db_session.query(Meal).count() == 0
    assert crud.get_plan(user=user_obj) == {}

    generated = planner.generate_plan(
        db_session,
        start=start,
        days=1,
        meals_per_day=1,
        user_id=user_id,
        keep_days=7,
        bulk_leftovers=False,
        epsilon=0.0,
        avoid_tags=[],
        reduce_tags=[],
        seasonality_weight=1.0,
        recency_weight=1.0,
        tag_penalty_weight=1.0,
        bulk_bonus_weight=1.0,
    )
    assert start.isoformat() in generated
    assert generated[start.isoformat()]


def test_delete_meal_plans_legacy_route(client, db_session, user_token_factory):
    auth = user_token_factory()
    user_id = auth.user["id"]

    main = crud.create_recipe(
        db_session, title="Main", servings_default=1, course="main", user=user_id
    )

    start = date(2024, 1, 1)

    crud.set_meal_plan(
        db_session,
        {start.isoformat(): [{"main_id": main.id}]},
        user=user_id,
    )

    user_obj = db_session.get(User, user_id)
    assert user_obj is not None
    crud.save_plan(
        {
            start.isoformat(): [
                {
                    "recipe": "Main",
                    "side_recipes": [],
                    "accepted": False,
                    "leftover": False,
                }
            ]
        },
        user=user_obj,
    )

    os.makedirs("data", exist_ok=True)

    resp = client.delete(
        "/plan",
        params={"start_date": start.isoformat(), "end_date": start.isoformat()},
        headers=auth.headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"deleted": 1}
