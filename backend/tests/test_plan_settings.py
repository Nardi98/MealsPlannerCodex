import json

import crud
from mealplanner.config import DEFAULT_PLAN_SETTINGS


def test_get_plan_settings_returns_defaults(db_session):
    settings = crud.get_plan_settings(db_session)
    assert settings == DEFAULT_PLAN_SETTINGS
    # A copy, not the shared default object.
    assert settings is not DEFAULT_PLAN_SETTINGS


def test_get_plan_settings_falls_back_to_defaults_without_overrides(db_session, user):
    assert crud.get_plan_settings(db_session, user.id) == DEFAULT_PLAN_SETTINGS


def test_plan_settings_endpoint_returns_defaults(auth_client):
    resp = auth_client.get("/plan/settings")
    assert resp.status_code == 200
    # JSON coerces the int meal-number keys to strings, so compare against
    # a JSON round-tripped copy of the defaults.
    assert resp.json() == json.loads(json.dumps(DEFAULT_PLAN_SETTINGS))


def test_plan_settings_endpoint_persists_overrides(auth_client):
    resp = auth_client.put("/plan/settings", json={"LEFTOVER_REPEAT_DEFAULT": 4})
    assert resp.status_code == 200
    assert resp.json()["LEFTOVER_REPEAT_DEFAULT"] == 4
    # The override survives a subsequent read.
    assert auth_client.get("/plan/settings").json()["LEFTOVER_REPEAT_DEFAULT"] == 4
