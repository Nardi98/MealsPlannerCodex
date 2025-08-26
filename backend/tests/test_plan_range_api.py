import os
from datetime import date, timedelta
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


def test_get_plan_range(db_session):
    r1 = crud.create_recipe(db_session, title="A", servings_default=1, course="main course")
    r2 = crud.create_recipe(db_session, title="B", servings_default=1, course="main course")
    start = date(2024, 1, 1)
    second = start + timedelta(days=1)
    crud.set_meal_plan(
        db_session,
        {
            start.isoformat(): [{"main": r1.id, "sides": []}],
            second.isoformat(): [{"main": r2.id, "sides": []}],
        },
    )

    os.makedirs("data", exist_ok=True)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

    resp = client.get(
        "/plan",
        params={"start_date": start.isoformat(), "end_date": second.isoformat()},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        start.isoformat(): [
            {"recipe": "A", "accepted": False, "side_dishes": []}
        ],
        second.isoformat(): [
            {"recipe": "B", "accepted": False, "side_dishes": []}
        ],
    }

    app.dependency_overrides.clear()
