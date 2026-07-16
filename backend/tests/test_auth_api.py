"""Routes touching user-owned data reject unauthenticated callers.

The old shared ``X-API-Key`` gate was retired once JWT auth landed: a single
process-wide secret said nothing about *which* account was calling, and it was
inert unless ``API_KEY`` happened to be set. Authentication is now solely
``get_current_user``, which these tests pin down.
"""
import pytest

from conftest import client_as, db_client
from main import app


@pytest.fixture
def anon_client(db_session):
    """A client on the test's session with no ``get_current_user`` override."""
    try:
        yield db_client(db_session)
    finally:
        app.dependency_overrides.clear()


_IMPORT_PAYLOAD = {"recipes": [], "ingredients": [], "tags": [], "meal_plans": []}


@pytest.mark.parametrize(
    "method, path, kwargs",
    [
        ("delete", "/data", {}),
        ("post", "/data/import", {"json": _IMPORT_PAYLOAD}),
        (
            "post",
            "/recipes/upload-image",
            {"files": {"file": ("pic.png", b"pngbytes", "image/png")}},
        ),
    ],
)
def test_route_rejects_anonymous_caller(anon_client, method, path, kwargs):
    resp = getattr(anon_client, method)(path, **kwargs)
    assert resp.status_code == 401


def test_delete_data_succeeds_for_authenticated_caller(db_session, user):
    try:
        resp = client_as(db_session, user).delete("/data")
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_import_data_succeeds_for_authenticated_caller(db_session, user):
    try:
        resp = client_as(db_session, user).post("/data/import", json=_IMPORT_PAYLOAD)
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()
