"""Tests for side dish generation endpoints."""

import os
from datetime import date, timedelta

import crud
from mealplanner.models import Tag


def test_generate_side_dish_requires_authentication(client):
    response = client.post("/side-dishes/generate", json={})
    assert response.status_code == 401


def test_generate_side_dish_endpoint_returns_side(
    client, db_session, user_token_factory
):
    auth = user_token_factory()
    user_id = auth.user["id"]

    for i in range(3):
        crud.create_recipe(
            db_session,
            title=f"Side {i}",
            servings_default=1,
            course="side",
            user=user_id,
        )

    os.makedirs("data", exist_ok=True)

    resp = client.post("/side-dishes/generate", json={}, headers=auth.headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"].startswith("Side")
    assert isinstance(data["id"], int)


def test_generate_side_dish_respects_tag_weight(
    client, db_session, user_token_factory
):
    auth = user_token_factory()
    user_id = auth.user["id"]
    today = date.today()

    good = crud.create_recipe(
        db_session,
        title="Good",
        servings_default=1,
        course="side",
        score=1.0,
        bulk_prep=True,
        user=user_id,
    )
    recent = crud.create_recipe(
        db_session,
        title="Recent",
        servings_default=1,
        course="side",
        score=2.0,
        bulk_prep=True,
        user=user_id,
    )

    old_day = today - timedelta(days=60)
    recent_day = today - timedelta(days=1)

    crud.set_meal_plan(
        db_session,
        {old_day.isoformat(): [{"main_id": good.id}]},
        user=user_id,
    )
    crud.add_meal_side(db_session, old_day, 1, good.id, user=user_id)

    crud.set_meal_plan(
        db_session,
        {recent_day.isoformat(): [{"main_id": recent.id}]},
        user=user_id,
    )
    crud.add_meal_side(db_session, recent_day, 1, recent.id, user=user_id)

    crud.create_recipe(
        db_session,
        title="Avoid",
        servings_default=1,
        course="side",
        score=5.0,
        tags=[Tag(name="avoid")],
        user=user_id,
    )

    os.makedirs("data", exist_ok=True)

    resp = client.post(
        "/side-dishes/generate",
        json={"avoid_tags": ["avoid"], "recency_weight": 0.0},
        headers=auth.headers,
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Recent"

    resp2 = client.post(
        "/side-dishes/generate",
        json={"avoid_tags": ["avoid"], "recency_weight": 2.0},
        headers=auth.headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["title"] == "Good"


def test_generate_side_dish_avoids_titles(client, db_session, user_token_factory):
    auth = user_token_factory()
    user_id = auth.user["id"]

    crud.create_recipe(
        db_session,
        title="Keep",
        servings_default=1,
        course="side",
        score=1.0,
        user=user_id,
    )
    crud.create_recipe(
        db_session,
        title="Skip",
        servings_default=1,
        course="side",
        score=10.0,
        user=user_id,
    )

    os.makedirs("data", exist_ok=True)

    resp = client.post(
        "/side-dishes/generate",
        json={"avoid_titles": ["Skip"]},
        headers=auth.headers,
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Keep"
