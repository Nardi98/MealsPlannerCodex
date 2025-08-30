from datetime import date
import os
from fastapi.testclient import TestClient

import crud
from main import app, get_db


def override_get_db(session):
    def _override():
        try:
            yield session
        finally:
            pass
    return _override


def test_post_plan_with_side_recipe(db_session):
    main = crud.create_recipe(db_session, title="Main", servings_default=1, course="main")
    side = crud.create_recipe(db_session, title="Side", servings_default=1, course="main")
    plan_date = date(2024, 1, 1)
    payload = {
        "plan_date": plan_date.isoformat(),
        "plan": {plan_date.isoformat(): [{"main_id": main.id, "side_ids": [side.id]}]},
    }

    os.makedirs("data", exist_ok=True)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

    resp = client.post("/meal-plans", json=payload)
    assert resp.status_code == 200
    expected = {
        plan_date.isoformat(): [
            {"recipe": "Main", "side_recipes": ["Side"], "accepted": False}
        ]
    }
    assert resp.json() == expected

    resp2 = client.get("/plan", params={"plan_date": plan_date.isoformat()})
    assert resp2.status_code == 200
    assert resp2.json() == expected

    app.dependency_overrides.clear()


def test_add_side_dish_endpoint(db_session):
    main = crud.create_recipe(db_session, title="Main", servings_default=1, course="main")
    side = crud.create_recipe(db_session, title="Side", servings_default=1, course="main")
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [main.id]})

    os.makedirs("data", exist_ok=True)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

    resp = client.post(
        "/meal-plans/side",
        json={"plan_date": plan_date.isoformat(), "meal_number": 1, "side_id": side.id},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "recipe": "Main",
        "side_recipes": ["Side"],
        "accepted": False,
    }

    resp2 = client.get("/plan", params={"plan_date": plan_date.isoformat()})
    assert resp2.status_code == 200
    assert resp2.json() == {
        plan_date.isoformat(): [
            {"recipe": "Main", "side_recipes": ["Side"], "accepted": False}
        ]
    }

    app.dependency_overrides.clear()


def test_replace_and_remove_side_dish_scores(db_session):
    main = crud.create_recipe(db_session, title="Main", servings_default=1, course="main")
    side1 = crud.create_recipe(db_session, title="Side1", servings_default=1, course="side", score=0)
    side2 = crud.create_recipe(db_session, title="Side2", servings_default=1, course="side", score=0)
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [main.id]})
    crud.add_meal_side(db_session, plan_date, 1, side1.id)
    assert crud.get_recipe(db_session, side1.id).score == 0
    crud.replace_meal_side(db_session, plan_date, 1, 0, side2.id)
    assert crud.get_recipe(db_session, side1.id).score == -1
    crud.remove_meal_side(db_session, plan_date, 1, 0)
    assert crud.get_recipe(db_session, side2.id).score == 0


def test_add_multiple_side_dishes(db_session):
    main = crud.create_recipe(db_session, title="Main", servings_default=1, course="main")
    side1 = crud.create_recipe(db_session, title="Side1", servings_default=1, course="side")
    side2 = crud.create_recipe(db_session, title="Side2", servings_default=1, course="side")
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [main.id]})

    os.makedirs("data", exist_ok=True)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

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
            }
        ]
    }

    app.dependency_overrides.clear()


def test_swap_specific_side_dish_endpoint(db_session):
    main = crud.create_recipe(db_session, title="Main", servings_default=1, course="main")
    side1 = crud.create_recipe(db_session, title="Side1", servings_default=1, course="side", score=0)
    side2 = crud.create_recipe(db_session, title="Side2", servings_default=1, course="side", score=0)
    side3 = crud.create_recipe(db_session, title="Side3", servings_default=1, course="side", score=0)
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [main.id]})
    crud.add_meal_side(db_session, plan_date, 1, side1.id)
    crud.add_meal_side(db_session, plan_date, 1, side2.id)

    os.makedirs("data", exist_ok=True)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

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
    }
    assert crud.get_recipe(db_session, side2.id).score == -1

    plan_resp = client.get("/plan", params={"plan_date": plan_date.isoformat()})
    assert plan_resp.status_code == 200
    assert plan_resp.json()[plan_date.isoformat()][0]["side_recipes"] == ["Side1", "Side3"]

    app.dependency_overrides.clear()


def test_remove_side_dish_endpoint_no_score_change(db_session):
    main = crud.create_recipe(db_session, title="Main", servings_default=1, course="main")
    side1 = crud.create_recipe(db_session, title="Side1", servings_default=1, course="side", score=0)
    side2 = crud.create_recipe(db_session, title="Side2", servings_default=1, course="side", score=0)
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [main.id]})
    crud.add_meal_side(db_session, plan_date, 1, side1.id)
    crud.add_meal_side(db_session, plan_date, 1, side2.id)

    os.makedirs("data", exist_ok=True)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

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
    }
    assert crud.get_recipe(db_session, side2.id).score == 0

    plan_resp = client.get("/plan", params={"plan_date": plan_date.isoformat()})
    assert plan_resp.status_code == 200
    assert plan_resp.json()[plan_date.isoformat()][0]["side_recipes"] == ["Side1"]

    app.dependency_overrides.clear()
