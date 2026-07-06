import json

from fastapi.testclient import TestClient

from main import app, get_db
from mealplanner import crud
from mealplanner.config import DEFAULT_PLAN_SETTINGS


def override_get_db(session):
    def _override():
        try:
            yield session
        finally:
            pass
    return _override


def test_get_plan_settings_returns_defaults(db_session):
    settings = crud.get_plan_settings(db_session)
    assert settings == DEFAULT_PLAN_SETTINGS
    # A copy, not the shared default object.
    assert settings is not DEFAULT_PLAN_SETTINGS


def test_get_plan_settings_accepts_user_id(db_session):
    # Future-proof seam: a user_id kwarg is accepted (ignored for now).
    settings = crud.get_plan_settings(db_session, user_id=42)
    assert settings == DEFAULT_PLAN_SETTINGS


def test_plan_settings_endpoint_returns_defaults(db_session):
    app.dependency_overrides[get_db] = override_get_db(db_session)
    try:
        client = TestClient(app)
        resp = client.get("/plan/settings")
        assert resp.status_code == 200
        # JSON coerces the int meal-number keys to strings, so compare against
        # a JSON round-tripped copy of the defaults.
        assert resp.json() == json.loads(json.dumps(DEFAULT_PLAN_SETTINGS))
    finally:
        app.dependency_overrides.clear()
