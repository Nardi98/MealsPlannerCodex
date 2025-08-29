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


def test_toggle_meal_acceptance(db_session):
    r = crud.create_recipe(db_session, title="A", servings_default=1, course="main")
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [{"main": r.id, "sides": []}]})
    os.makedirs("data", exist_ok=True)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

    resp = client.post(
        "/meal-plans/accept",
        json={"plan_date": "2024-01-01", "meal_number": 1, "accepted": True},
    )
    assert resp.status_code == 200
    assert resp.json() == {"main": "A", "sides": [], "accepted": True}

    resp2 = client.get("/plan", params={"plan_date": "2024-01-01"})
    assert resp2.status_code == 200
    assert resp2.json() == {
        "2024-01-01": [{"main": "A", "sides": [], "accepted": True}]
    }

    app.dependency_overrides.clear()
