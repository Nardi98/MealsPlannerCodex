"""Tests for side dish management endpoints."""

import os
from datetime import date

import crud


def test_meal_plan_side_routes_require_authentication(client):
    plan_date = "2024-01-01"
    payload = {plan_date: [{"main_id": 1, "side_ids": [2]}]}
    assert client.post(
        "/meal-plans", json={"plan_date": plan_date, "plan": payload}
    ).status_code == 401
    assert (
        client.post(
            "/meal-plans/side",
            json={"plan_date": plan_date, "meal_number": 1, "side_id": 1},
        ).status_code
        == 401
    )


def test_post_plan_with_side_recipe(client, db_session, user_token_factory):
    auth = user_token_factory()
    user_id = auth.user["id"]
    main = crud.create_recipe(
        db_session, title="Main", servings_default=1, course="main", user=user_id
    )
    side = crud.create_recipe(
        db_session, title="Side", servings_default=1, course="main", user=user_id
    )
    plan_date = date(2024, 1, 1)
    payload = {
        "plan_date": plan_date.isoformat(),
        "plan": {plan_date.isoformat(): [{"main_id": main.id, "side_ids": [side.id]}]},
    }

    os.makedirs("data", exist_ok=True)

    resp = client.post("/meal-plans", json=payload, headers=auth.headers)
    assert resp.status_code == 200
    expected = {
        plan_date.isoformat(): [
            {
                "recipe": "Main",
                "side_recipes": ["Side"],
                "accepted": False,
                "leftover": False,
            }
        ]
    }
    assert resp.json() == expected

    resp2 = client.get(
        "/plan",
        params={"plan_date": plan_date.isoformat()},
        headers=auth.headers,
    )
    assert resp2.status_code == 200
    assert resp2.json() == expected


def test_add_side_dish_endpoint(client, db_session, user_token_factory):
    auth = user_token_factory()
    user_id = auth.user["id"]
    main = crud.create_recipe(
        db_session, title="Main", servings_default=1, course="main", user=user_id
    )
    side = crud.create_recipe(
        db_session, title="Side", servings_default=1, course="main", user=user_id
    )
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(
        db_session, {plan_date.isoformat(): [main.id]}, user=user_id
    )

    os.makedirs("data", exist_ok=True)

    resp = client.post(
        "/meal-plans/side",
        json={"plan_date": plan_date.isoformat(), "meal_number": 1, "side_id": side.id},
        headers=auth.headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "recipe": "Main",
        "side_recipes": ["Side"],
        "accepted": False,
        "leftover": False,
    }

    resp2 = client.get(
        "/plan",
        params={"plan_date": plan_date.isoformat()},
        headers=auth.headers,
    )
    assert resp2.status_code == 200
    assert resp2.json() == {
        plan_date.isoformat(): [
            {
                "recipe": "Main",
                "side_recipes": ["Side"],
                "accepted": False,
                "leftover": False,
            }
        ]
    }


def test_replace_and_remove_side_dish_scores(db_session, user_token_factory):
    auth = user_token_factory()
    user_id = auth.user["id"]
    main = crud.create_recipe(
        db_session, title="Main", servings_default=1, course="main", user=user_id
    )
    side1 = crud.create_recipe(
        db_session, title="Side1", servings_default=1, course="side", score=0, user=user_id
    )
    side2 = crud.create_recipe(
        db_session, title="Side2", servings_default=1, course="side", score=0, user=user_id
    )
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(
        db_session, {plan_date.isoformat(): [main.id]}, user=user_id
    )
    crud.add_meal_side(db_session, plan_date, 1, side1.id, user=user_id)
    assert crud.get_recipe(db_session, side1.id, user=user_id).score == 0
    crud.replace_meal_side(db_session, plan_date, 1, 0, side2.id, user=user_id)
    assert crud.get_recipe(db_session, side1.id, user=user_id).score == -1
    crud.remove_meal_side(db_session, plan_date, 1, 0, user=user_id)
    assert crud.get_recipe(db_session, side2.id, user=user_id).score == 0


def test_add_multiple_side_dishes(client, db_session, user_token_factory):
    auth = user_token_factory()
    user_id = auth.user["id"]
    main = crud.create_recipe(
        db_session, title="Main", servings_default=1, course="main", user=user_id
    )
    side1 = crud.create_recipe(
        db_session, title="Side1", servings_default=1, course="side", user=user_id
    )
    side2 = crud.create_recipe(
        db_session, title="Side2", servings_default=1, course="side", user=user_id
    )
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(
        db_session, {plan_date.isoformat(): [main.id]}, user=user_id
    )

    os.makedirs("data", exist_ok=True)

    resp1 = client.post(
        "/meal-plans/side",
        json={"plan_date": plan_date.isoformat(), "meal_number": 1, "side_id": side1.id},
        headers=auth.headers,
    )
    assert resp1.status_code == 200
    resp2 = client.post(
        "/meal-plans/side",
        json={"plan_date": plan_date.isoformat(), "meal_number": 1, "side_id": side2.id},
        headers=auth.headers,
    )
    assert resp2.status_code == 200

    plan_resp = client.get(
        "/plan",
        params={"plan_date": plan_date.isoformat()},
        headers=auth.headers,
    )
    assert plan_resp.status_code == 200
    assert plan_resp.json() == {
        plan_date.isoformat(): [
            {
                "recipe": "Main",
                "side_recipes": ["Side1", "Side2"],
                "accepted": False,
                "leftover": False,
            }
        ]
    }


def test_swap_specific_side_dish_endpoint(client, db_session, user_token_factory):
    auth = user_token_factory()
    user_id = auth.user["id"]
    main = crud.create_recipe(
        db_session, title="Main", servings_default=1, course="main", user=user_id
    )
    side1 = crud.create_recipe(
        db_session, title="Side1", servings_default=1, course="side", score=0, user=user_id
    )
    side2 = crud.create_recipe(
        db_session, title="Side2", servings_default=1, course="side", score=0, user=user_id
    )
    side3 = crud.create_recipe(
        db_session, title="Side3", servings_default=1, course="side", score=0, user=user_id
    )
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(
        db_session, {plan_date.isoformat(): [main.id]}, user=user_id
    )
    crud.add_meal_side(db_session, plan_date, 1, side1.id, user=user_id)
    crud.add_meal_side(db_session, plan_date, 1, side2.id, user=user_id)

    os.makedirs("data", exist_ok=True)

    resp = client.post(
        "/meal-plans/side",
        json={
            "plan_date": plan_date.isoformat(),
            "meal_number": 1,
            "side_id": side3.id,
            "index": 1,
        },
        headers=auth.headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "recipe": "Main",
        "side_recipes": ["Side1", "Side3"],
        "accepted": False,
        "leftover": False,
    }
    assert crud.get_recipe(db_session, side2.id, user=user_id).score == -1

    plan_resp = client.get(
        "/plan",
        params={"plan_date": plan_date.isoformat()},
        headers=auth.headers,
    )
    assert plan_resp.status_code == 200
    assert plan_resp.json()[plan_date.isoformat()][0]["side_recipes"] == [
        "Side1",
        "Side3",
    ]


def test_remove_side_dish_endpoint_no_score_change(
    client, db_session, user_token_factory
):
    auth = user_token_factory()
    user_id = auth.user["id"]
    main = crud.create_recipe(
        db_session, title="Main", servings_default=1, course="main", user=user_id
    )
    side1 = crud.create_recipe(
        db_session, title="Side1", servings_default=1, course="side", score=0, user=user_id
    )
    side2 = crud.create_recipe(
        db_session, title="Side2", servings_default=1, course="side", score=0, user=user_id
    )
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(
        db_session, {plan_date.isoformat(): [main.id]}, user=user_id
    )
    crud.add_meal_side(db_session, plan_date, 1, side1.id, user=user_id)
    crud.add_meal_side(db_session, plan_date, 1, side2.id, user=user_id)

    os.makedirs("data", exist_ok=True)

    resp = client.request(
        "DELETE",
        "/meal-plans/side",
        json={"plan_date": plan_date.isoformat(), "meal_number": 1, "index": 1},
        headers=auth.headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "recipe": "Main",
        "side_recipes": ["Side1"],
        "accepted": False,
        "leftover": False,
    }
    assert crud.get_recipe(db_session, side2.id, user=user_id).score == 0

    plan_resp = client.get(
        "/plan",
        params={"plan_date": plan_date.isoformat()},
        headers=auth.headers,
    )
    assert plan_resp.status_code == 200
    assert plan_resp.json()[plan_date.isoformat()][0]["side_recipes"] == ["Side1"]
