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

    os.makedirs("data", exist_ok=True)
    from main import app, get_db  # imported after data dir exists

    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)
    response = client.post(
        "/meal-plans/generate",
        json={"start": "2024-01-01", "end": "2024-01-01", "meals_per_day": 1},
    )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert "2024-01-01" in data
    assert isinstance(data["2024-01-01"][0]["id"], int)
    assert data["2024-01-01"][0]["title"].startswith("Meal")
    assert data["2024-01-01"][0]["leftover"] is False


def test_generate_endpoint_rejects_invalid_range(db_session):
    os.makedirs("data", exist_ok=True)
    from main import app, get_db  # imported after data dir exists

    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)
    response = client.post(
        "/meal-plans/generate",
        json={"start": "2024-01-02", "end": "2024-01-01", "meals_per_day": 1},
    )
    app.dependency_overrides.clear()
    assert response.status_code == 422


def test_generate_endpoint_accepts_legacy_days_payload(db_session):
    for i in range(4):
        crud.create_recipe(db_session, title=f"Legacy Meal {i}", servings_default=1, course="main")

    os.makedirs("data", exist_ok=True)
    from main import app, get_db  # imported after data dir exists

    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)
    response = client.post(
        "/meal-plans/generate",
        json={"start": "2024-01-01", "days": 2, "meals_per_day": 1},
    )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    data = response.json()
    assert sorted(data)[:2] == ["2024-01-01", "2024-01-02"]
