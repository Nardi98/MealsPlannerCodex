import importlib

from fastapi.testclient import TestClient

from main import app, get_db


def override_get_db(session):
    def _override():
        try:
            yield session
        finally:
            pass

    return _override


def test_delete_data_requires_key_when_configured(db_session, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)
    try:
        # Missing header -> 401
        resp = client.delete("/data")
        assert resp.status_code == 401

        # Wrong key -> 401
        resp = client.delete("/data", headers={"X-API-Key": "nope"})
        assert resp.status_code == 401

        # Correct key -> 200
        resp = client.delete("/data", headers={"X-API-Key": "secret"})
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_import_requires_key_when_configured(db_session, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)
    try:
        payload = {"recipes": [], "ingredients": [], "tags": [], "meal_plans": []}
        resp = client.post("/data/import", json=payload)
        assert resp.status_code == 401

        resp = client.post(
            "/data/import", json=payload, headers={"X-API-Key": "secret"}
        )
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_auth_disabled_when_env_unset(db_session, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)
    try:
        resp = client.delete("/data")
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()
