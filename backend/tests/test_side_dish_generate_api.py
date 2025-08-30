import os
from datetime import date, timedelta
from fastapi.testclient import TestClient

import crud
from mealplanner.models import Tag


def override_get_db(session):
    def _override():
        try:
            yield session
        finally:
            pass
    return _override


def test_generate_side_dish_endpoint_returns_side(db_session):
    for i in range(3):
        crud.create_recipe(db_session, title=f"Side {i}", servings_default=1, course="side")
    os.makedirs("data", exist_ok=True)
    from main import app, get_db  # imported after data dir exists
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)
    resp = client.post("/side-dishes/generate", json={})
    app.dependency_overrides.clear()
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"].startswith("Side")
    assert isinstance(data["id"], int)


def test_generate_side_dish_respects_tag_weight(db_session):
    today = date.today()
    crud.create_recipe(
        db_session,
        title="Good",
        servings_default=1,
        course="side",
        score=1.0,
        bulk_prep=True,
        date_last_consumed=today - timedelta(days=60),
    )
    crud.create_recipe(
        db_session,
        title="Recent",
        servings_default=1,
        course="side",
        score=2.0,
        bulk_prep=True,
        date_last_consumed=today - timedelta(days=1),
    )
    crud.create_recipe(
        db_session,
        title="Avoid",
        servings_default=1,
        course="side",
        score=5.0,
        tags=[Tag(name="avoid")],
    )
    os.makedirs("data", exist_ok=True)
    from main import app, get_db  # imported after data dir exists
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

    resp = client.post(
        "/side-dishes/generate",
        json={"avoid_tags": ["avoid"], "recency_weight": 0.0},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Recent"

    resp2 = client.post(
        "/side-dishes/generate",
        json={"avoid_tags": ["avoid"], "recency_weight": 2.0},
    )
    app.dependency_overrides.clear()
    assert resp2.status_code == 200
    assert resp2.json()["title"] == "Good"

