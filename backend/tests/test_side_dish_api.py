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
        "plan": {plan_date.isoformat(): [{"main_id": main.id, "side_id": side.id}]},
    }

    os.makedirs("data", exist_ok=True)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

    resp = client.post("/meal-plans", json=payload)
    assert resp.status_code == 200
    expected = {
        plan_date.isoformat(): [
            {"recipe": "Main", "side_recipe": "Side", "accepted": False}
        ]
    }
    assert resp.json() == expected

    resp2 = client.get("/plan", params={"plan_date": plan_date.isoformat()})
    assert resp2.status_code == 200
    assert resp2.json() == expected

    app.dependency_overrides.clear()


def test_set_side_dish_endpoint(db_session):
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
        "side_recipe": "Side",
        "accepted": False,
    }

    resp2 = client.get("/plan", params={"plan_date": plan_date.isoformat()})
    assert resp2.status_code == 200
    assert resp2.json() == {
        plan_date.isoformat(): [
            {"recipe": "Main", "side_recipe": "Side", "accepted": False}
        ]
    }

    app.dependency_overrides.clear()
