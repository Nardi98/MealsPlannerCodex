import os
from datetime import date
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


def test_post_meal_plan_accepts_int_lists(db_session):
    recipe = crud.create_recipe(db_session, title="A", servings_default=1, course="main course")

    os.makedirs("data", exist_ok=True)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

    plan_date = date(2024, 1, 1).isoformat()
    payload = {"plan_date": plan_date, "plan": {plan_date: [recipe.id]}}
    resp = client.post("/meal-plans", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {plan_date: [{"recipe": "A", "accepted": False, "side_dishes": []}]}

    app.dependency_overrides.clear()


def test_post_meal_plan_handles_none_and_side_lists(db_session):
    main = crud.create_recipe(db_session, title="M", servings_default=1, course="main course")
    side = crud.create_recipe(db_session, title="S", servings_default=1, course="side dish")

    os.makedirs("data", exist_ok=True)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

    plan_date = date(2024, 1, 2).isoformat()
    payload = {"plan_date": plan_date, "plan": {plan_date: [[main.id, side.id], None]}}
    resp = client.post("/meal-plans", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {
        plan_date: [
            {"recipe": "M", "accepted": False, "side_dishes": ["S"]}
        ]
    }

    app.dependency_overrides.clear()
