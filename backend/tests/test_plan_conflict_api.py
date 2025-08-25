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


def test_post_meal_plan_conflict_requires_force(db_session):
    r1 = crud.create_recipe(db_session, title="A", servings_default=1)
    r2 = crud.create_recipe(db_session, title="B", servings_default=1)
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [r1.id]})

    os.makedirs("data", exist_ok=True)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

    payload = {
        "plan_date": plan_date.isoformat(),
        "plan": {plan_date.isoformat(): [r2.id]},
    }
    resp = client.post("/meal-plans", json=payload)
    assert resp.status_code == 409
    assert resp.json()["conflicts"] == [plan_date.isoformat()]

    resp2 = client.post("/meal-plans?force=true", json=payload)
    assert resp2.status_code == 200
    resp3 = client.get("/plan", params={"plan_date": plan_date.isoformat()})
    assert resp3.status_code == 200
    assert resp3.json() == {
        plan_date.isoformat(): [{"recipe": "B", "accepted": False}]
    }

    app.dependency_overrides.clear()
