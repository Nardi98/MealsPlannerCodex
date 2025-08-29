from datetime import date
import os

from fastapi.testclient import TestClient

import crud
from main import app, get_db
from mealplanner.models import Meal


def override_get_db(session):
    def _override():
        try:
            yield session
        finally:
            pass
    return _override


def test_post_plan_accepts_recipe_refs(db_session):
    main = crud.create_recipe(db_session, title="Main", servings_default=1, course="main")
    side = crud.create_recipe(db_session, title="Side", servings_default=1, course="side")
    plan_date = date(2025, 8, 29)

    os.makedirs("data", exist_ok=True)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

    payload = {
        "plan_date": plan_date.isoformat(),
        "plan": {
            plan_date.isoformat(): [
                {
                    "main": {"id": main.id, "title": main.title},
                    "sides": [{"id": side.id, "title": side.title}],
                }
            ]
        },
    }
    resp = client.post("/meal-plans", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {
        plan_date.isoformat(): [
            {"main": "Main", "sides": ["Side"], "accepted": False}
        ]
    }
    meal = db_session.get(Meal, (plan_date, 1))
    assert meal is not None and meal.main_recipe_id == main.id
    assert [ms.side_recipe_id for ms in meal.side_dishes] == [side.id]

    app.dependency_overrides.clear()
