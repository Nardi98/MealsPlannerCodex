import os
from fastapi.testclient import TestClient

import crud


def override_get_db(session):
    def _override():
        try:
            yield session
        finally:
            pass
    return _override


def test_generate_endpoint_returns_plan(db_session):
    for i in range(3):
        crud.create_recipe(db_session, title=f"Meal {i}", servings_default=1, course="main")
    for i in range(2):
        crud.create_recipe(db_session, title=f"Side {i}", servings_default=1, course="side")

    os.makedirs("data", exist_ok=True)
    from main import app, get_db  # imported after data dir exists

    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)
    response = client.post(
        "/meal-plans/generate",
        json={"start": "2024-01-01", "days": 1, "meals_per_day": 1, "side_dishes": 1},
    )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert "2024-01-01" in data
    entry = data["2024-01-01"][0]
    assert isinstance(entry["main"]["id"], int)
    assert entry["main"]["title"].startswith("Meal")
    assert len(entry["sides"]) == 1
