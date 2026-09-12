from datetime import date

import crud


def test_post_plan_with_side_recipe(db_session, user, auth_client):
    main = crud.create_recipe(db_session, title="Main", course="main", user_id=user.id)
    side = crud.create_recipe(db_session, title="Side", course="main", user_id=user.id)
    plan_date = date(2024, 1, 1)
    payload = {
        "plan_date": plan_date.isoformat(),
        "plan": {plan_date.isoformat(): [{"main_id": main.id, "side_ids": [side.id]}]},
    }

    client = auth_client

    resp = client.post("/meal-plans", json=payload)
    assert resp.status_code == 200
    expected = {
        plan_date.isoformat(): [
            {
                "recipe": "Main",
                "side_recipes": ["Side"],
                "accepted": False,
                "leftover": False,
                "meal_number": 1,
                "people": 2,
            }
        ]
    }
    assert resp.json() == expected

    resp2 = client.get("/plan", params={"plan_date": plan_date.isoformat()})
    assert resp2.status_code == 200
    assert resp2.json() == expected



def test_add_side_dish_endpoint(db_session, user, auth_client):
    main = crud.create_recipe(db_session, title="Main", course="main", user_id=user.id)
    side = crud.create_recipe(db_session, title="Side", course="main", user_id=user.id)
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [main.id]}, user_id=user.id)

    client = auth_client

    resp = client.post(
        "/meal-plans/side",
        json={"plan_date": plan_date.isoformat(), "meal_number": 1, "side_id": side.id},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "recipe": "Main",
        "side_recipes": ["Side"],
        "accepted": False,
        "leftover": False,
        "meal_number": 1,
        "people": 2,
    }

    resp2 = client.get("/plan", params={"plan_date": plan_date.isoformat()})
    assert resp2.status_code == 200
    assert resp2.json() == {
        plan_date.isoformat(): [
            {
                "recipe": "Main",
                "side_recipes": ["Side"],
                "accepted": False,
                "leftover": False,
                "meal_number": 1,
                "people": 2,
            }
        ]
    }



def test_replace_and_remove_side_dish_leave_scores_alone(db_session, user, auth_client):
    """Replacing or removing a side is bookkeeping, not feedback.

    Scoring a rejection is ``/feedback/reject``'s job -- it is also the only
    caller that stamps ``date_last_rejected``.
    """

    main = crud.create_recipe(db_session, title="Main", course="main", user_id=user.id)
    side1 = crud.create_recipe(db_session, title="Side1", course="side", score=0, user_id=user.id)
    side2 = crud.create_recipe(db_session, title="Side2", course="side", score=0, user_id=user.id)
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [main.id]}, user_id=user.id)
    crud.add_meal_side(db_session, plan_date, 1, side1.id)
    assert crud.get_recipe(db_session, side1.id).score == 0
    crud.replace_meal_side(db_session, plan_date, 1, 0, side2.id)
    assert crud.get_recipe(db_session, side1.id).score == 0
    crud.remove_meal_side(db_session, plan_date, 1, 0)
    assert crud.get_recipe(db_session, side2.id).score == 0


def test_reject_then_replace_side_dish_costs_exactly_one_point(db_session, user, auth_client):
    """The UI's reject flow: POST /feedback/reject, then POST /meal-plans/side."""

    main = crud.create_recipe(db_session, title="Main", course="main", user_id=user.id)
    side1 = crud.create_recipe(db_session, title="Side1", course="side", score=0, user_id=user.id)
    side2 = crud.create_recipe(db_session, title="Side2", course="side", score=0, user_id=user.id)
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [main.id]}, user_id=user.id)
    crud.add_meal_side(db_session, plan_date, 1, side1.id)

    client = auth_client

    reject = client.post(
        "/feedback/reject",
        json={"title": "Side1", "consumed_date": plan_date.isoformat()},
    )
    assert reject.status_code == 200

    replace = client.post(
        "/meal-plans/side",
        json={
            "plan_date": plan_date.isoformat(),
            "meal_number": 1,
            "side_id": side2.id,
            "index": 0,
        },
    )
    assert replace.status_code == 200

    rejected = crud.get_recipe(db_session, side1.id)
    assert rejected.score == -1
    assert rejected.date_last_rejected == date.today()


def test_add_multiple_side_dishes(db_session, user, auth_client):
    main = crud.create_recipe(db_session, title="Main", course="main", user_id=user.id)
    side1 = crud.create_recipe(db_session, title="Side1", course="side", user_id=user.id)
    side2 = crud.create_recipe(db_session, title="Side2", course="side", user_id=user.id)
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [main.id]}, user_id=user.id)

    client = auth_client

    resp1 = client.post(
        "/meal-plans/side",
        json={"plan_date": plan_date.isoformat(), "meal_number": 1, "side_id": side1.id},
    )
    assert resp1.status_code == 200
    resp2 = client.post(
        "/meal-plans/side",
        json={"plan_date": plan_date.isoformat(), "meal_number": 1, "side_id": side2.id},
    )
    assert resp2.status_code == 200

    plan_resp = client.get("/plan", params={"plan_date": plan_date.isoformat()})
    assert plan_resp.status_code == 200
    assert plan_resp.json() == {
        plan_date.isoformat(): [
            {
                "recipe": "Main",
                "side_recipes": ["Side1", "Side2"],
                "accepted": False,
                "leftover": False,
                "meal_number": 1,
                "people": 2,
            }
        ]
    }



def test_swap_specific_side_dish_endpoint(db_session, user, auth_client):
    main = crud.create_recipe(db_session, title="Main", course="main", user_id=user.id)
    side1 = crud.create_recipe(db_session, title="Side1", course="side", score=0, user_id=user.id)
    side2 = crud.create_recipe(db_session, title="Side2", course="side", score=0, user_id=user.id)
    side3 = crud.create_recipe(db_session, title="Side3", course="side", score=0, user_id=user.id)
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [main.id]}, user_id=user.id)
    crud.add_meal_side(db_session, plan_date, 1, side1.id)
    crud.add_meal_side(db_session, plan_date, 1, side2.id)

    client = auth_client

    resp = client.post(
        "/meal-plans/side",
        json={
            "plan_date": plan_date.isoformat(),
            "meal_number": 1,
            "side_id": side3.id,
            "index": 1,
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "recipe": "Main",
        "side_recipes": ["Side1", "Side3"],
        "accepted": False,
        "leftover": False,
        "meal_number": 1,
        "people": 2,
    }
    assert crud.get_recipe(db_session, side2.id).score == 0

    plan_resp = client.get("/plan", params={"plan_date": plan_date.isoformat()})
    assert plan_resp.status_code == 200
    assert plan_resp.json()[plan_date.isoformat()][0]["side_recipes"] == ["Side1", "Side3"]



def test_remove_first_of_multiple_side_dishes(db_session, user, auth_client):
    main = crud.create_recipe(db_session, title="Main", course="main", user_id=user.id)
    side1 = crud.create_recipe(db_session, title="Side1", course="side", score=0, user_id=user.id)
    side2 = crud.create_recipe(db_session, title="Side2", course="side", score=0, user_id=user.id)
    side3 = crud.create_recipe(db_session, title="Side3", course="side", score=0, user_id=user.id)
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [main.id]}, user_id=user.id)
    crud.add_meal_side(db_session, plan_date, 1, side1.id)
    crud.add_meal_side(db_session, plan_date, 1, side2.id)
    crud.add_meal_side(db_session, plan_date, 1, side3.id)

    client = auth_client

    resp = client.request(
        "DELETE",
        "/meal-plans/side",
        json={"plan_date": plan_date.isoformat(), "meal_number": 1, "index": 0},
    )
    assert resp.status_code == 200
    assert resp.json()["side_recipes"] == ["Side2", "Side3"]

    plan_resp = client.get("/plan", params={"plan_date": plan_date.isoformat()})
    assert plan_resp.status_code == 200
    assert plan_resp.json()[plan_date.isoformat()][0]["side_recipes"] == ["Side2", "Side3"]


def test_remove_middle_side_dish_renumbers_positions(db_session, user, auth_client):
    main = crud.create_recipe(db_session, title="Main", course="main", user_id=user.id)
    side1 = crud.create_recipe(db_session, title="Side1", course="side", score=0, user_id=user.id)
    side2 = crud.create_recipe(db_session, title="Side2", course="side", score=0, user_id=user.id)
    side3 = crud.create_recipe(db_session, title="Side3", course="side", score=0, user_id=user.id)
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [main.id]}, user_id=user.id)
    crud.add_meal_side(db_session, plan_date, 1, side1.id)
    crud.add_meal_side(db_session, plan_date, 1, side2.id)
    crud.add_meal_side(db_session, plan_date, 1, side3.id)

    meal = crud.remove_meal_side(db_session, plan_date, 1, 1)

    assert [s.side_recipe.title for s in meal.sides] == ["Side1", "Side3"]
    assert [s.position for s in meal.sides] == [1, 2]


def test_remove_side_dish_endpoint_no_score_change(db_session, user, auth_client):
    main = crud.create_recipe(db_session, title="Main", course="main", user_id=user.id)
    side1 = crud.create_recipe(db_session, title="Side1", course="side", score=0, user_id=user.id)
    side2 = crud.create_recipe(db_session, title="Side2", course="side", score=0, user_id=user.id)
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [main.id]}, user_id=user.id)
    crud.add_meal_side(db_session, plan_date, 1, side1.id)
    crud.add_meal_side(db_session, plan_date, 1, side2.id)

    client = auth_client

    resp = client.request(
        "DELETE",
        "/meal-plans/side",
        json={"plan_date": plan_date.isoformat(), "meal_number": 1, "index": 1},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "recipe": "Main",
        "side_recipes": ["Side1"],
        "accepted": False,
        "leftover": False,
        "meal_number": 1,
        "people": 2,
    }
    assert crud.get_recipe(db_session, side2.id).score == 0

    plan_resp = client.get("/plan", params={"plan_date": plan_date.isoformat()})
    assert plan_resp.status_code == 200
    assert plan_resp.json()[plan_date.isoformat()][0]["side_recipes"] == ["Side1"]

