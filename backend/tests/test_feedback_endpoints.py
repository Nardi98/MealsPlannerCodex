"""Tests for feedback endpoints that adjust recipe scores."""

from datetime import date

import crud


def test_feedback_endpoints_require_authentication(client):
    consumed = {"title": "A", "consumed_date": "2024-01-01"}
    assert client.post("/feedback/accept", json=consumed).status_code == 401
    assert client.post("/feedback/reject", json=consumed).status_code == 401


def test_feedback_endpoints_return_unique_replacement(
    client, db_session, user_token_factory
):
    auth = user_token_factory()
    user_id = auth.user["id"]
    a = crud.create_recipe(
        db_session, title="A", servings_default=1, course="main", score=0, user=user_id
    )
    crud.create_recipe(
        db_session, title="B", servings_default=1, course="main", score=0, user=user_id
    )
    crud.create_recipe(
        db_session, title="C", servings_default=1, course="main", score=0, user=user_id
    )
    crud.save_plan(
        {
            "2024-01-01": [
                {
                    "recipe": "A",
                    "side_recipes": [],
                    "accepted": False,
                    "leftover": False,
                },
                {
                    "recipe": "C",
                    "side_recipes": [],
                    "accepted": False,
                    "leftover": True,
                },
            ]
        },
        user=user_id,
    )

    consumed = date(2024, 1, 1)
    resp = client.post(
        "/feedback/accept",
        json={"title": "A", "consumed_date": consumed.isoformat()},
        headers=auth.headers,
    )
    assert resp.status_code == 200
    db_session.refresh(a)
    assert a.score == 1
    assert a.date_last_consumed == consumed

    resp = client.post(
        "/feedback/reject",
        json={"title": "A", "consumed_date": consumed.isoformat()},
        headers=auth.headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["replacement"] == "B"

    crud._PLAN_CACHE.clear()
    crud._PLAN_SETTINGS.clear()


def test_reject_replacement_limited_to_main_courses(
    client, db_session, user_token_factory
):
    auth = user_token_factory()
    user_id = auth.user["id"]
    crud.create_recipe(
        db_session, title="A", servings_default=1, course="main", score=0, user=user_id
    )
    crud.create_recipe(
        db_session, title="B", servings_default=1, course="main", score=0, user=user_id
    )
    crud.create_recipe(
        db_session, title="C", servings_default=1, course="dessert", score=0, user=user_id
    )
    crud.save_plan(
        {
            "2024-01-01": [
                {
                    "recipe": "A",
                    "side_recipes": [],
                    "accepted": False,
                    "leftover": False,
                }
            ]
        },
        user=user_id,
    )

    consumed = date(2024, 1, 1)
    resp = client.post(
        "/feedback/reject",
        json={"title": "A", "consumed_date": consumed.isoformat()},
        headers=auth.headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["replacement"] == "B"
    assert data["replacement"] != "C"

    crud._PLAN_CACHE.clear()
    crud._PLAN_SETTINGS.clear()
