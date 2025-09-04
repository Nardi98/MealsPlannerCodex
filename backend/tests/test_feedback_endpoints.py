from datetime import date

from fastapi.testclient import TestClient
from main import app, get_db
from mealplanner import crud


def override_get_db(session):
    def _override():
        try:
            yield session
        finally:
            pass
    return _override


def test_feedback_endpoints_return_unique_replacement(db_session):
    app.dependency_overrides[get_db] = override_get_db(db_session)
    a = crud.create_recipe(db_session, title="A", servings_default=1, course="main", score=0)
    crud.create_recipe(db_session, title="B", servings_default=1, course="main", score=0)
    crud.create_recipe(db_session, title="C", servings_default=1, course="main", score=0)
    crud.save_plan(
        {
            "2024-01-01": [
                {"recipe": "A", "side_recipes": [], "accepted": False},
                {"recipe": "C (leftover)", "side_recipes": [], "accepted": False},
            ]
        }
    )
    client = TestClient(app)

    consumed = date(2024, 1, 1)
    resp = client.post(
        "/feedback/accept", json={"title": "A", "consumed_date": consumed.isoformat()}
    )
    assert resp.status_code == 200
    db_session.refresh(a)
    assert a.score == 1
    assert a.date_last_consumed == consumed

    resp = client.post(
        "/feedback/reject", json={"title": "A", "consumed_date": consumed.isoformat()}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["replacement"] == "B"

    crud._PLAN_CACHE.clear()
    crud._PLAN_SETTINGS.clear()
    app.dependency_overrides.clear()


def test_reject_replacement_limited_to_main_courses(db_session):
    app.dependency_overrides[get_db] = override_get_db(db_session)
    crud.create_recipe(db_session, title="A", servings_default=1, course="main", score=0)
    crud.create_recipe(db_session, title="B", servings_default=1, course="main", score=0)
    crud.create_recipe(
        db_session, title="C", servings_default=1, course="dessert", score=0
    )
    crud.save_plan(
        {"2024-01-01": [{"recipe": "A", "side_recipes": [], "accepted": False}]}
    )
    client = TestClient(app)

    consumed = date(2024, 1, 1)
    resp = client.post(
        "/feedback/reject", json={"title": "A", "consumed_date": consumed.isoformat()}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["replacement"] == "B"
    assert data["replacement"] != "C"

    crud._PLAN_CACHE.clear()
    crud._PLAN_SETTINGS.clear()
    app.dependency_overrides.clear()

