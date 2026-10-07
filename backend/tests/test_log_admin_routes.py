"""Admin developer-log routes (``/admin/logs/*``)."""

import pytest

import devlog
from main import app
from tests.conftest import client_as


@pytest.fixture
def admin_client(db_session, admin_user):
    try:
        yield client_as(db_session, admin_user)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("path", ["/admin/logs/users?q=own", "/admin/logs/export?user_id=1"])
def test_anonymous_callers_get_401(anon, path):
    assert anon.get(path).status_code == 401


@pytest.mark.parametrize("path", ["/admin/logs/users?q=own", "/admin/logs/export?user_id=1"])
def test_non_admins_get_403(auth_client, path):
    assert auth_client.get(path).status_code == 403


def test_user_search_matches_email_or_username_case_insensitively(
    admin_client, user, other_user
):
    by_email = admin_client.get("/admin/logs/users", params={"q": "OWNER@test"}).json()
    by_username = admin_client.get("/admin/logs/users", params={"q": "Othe"}).json()

    assert [u["id"] for u in by_email] == [user.id]
    assert [u["id"] for u in by_username] == [other_user.id]
    assert set(by_email[0]) == {"id", "email", "username"}


def test_user_search_is_capped_at_twenty(admin_client, db_session):
    import crud

    for i in range(25):
        crud.create_user(db_session, email=f"bulk{i}@test.local", username=f"bulk{i}",
                         hashed_password="x")

    assert len(admin_client.get("/admin/logs/users", params={"q": "bulk"}).json()) == 20


def test_export_downloads_only_that_users_rows(admin_client, db_session, user, other_user):
    devlog.record(db_session, user_id=user.id, channel="planner", event="mine", payload={"a": 1})
    devlog.record(db_session, user_id=other_user.id, channel="planner", event="theirs", payload={})

    resp = admin_client.get("/admin/logs/export", params={"user_id": user.id})

    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    assert f"user-{user.id}" in resp.headers["content-disposition"]
    body = resp.json()
    assert body["user"] == {"id": user.id, "email": user.email, "username": user.username}
    assert [e["event"] for e in body["entries"]] == ["mine"]


def test_export_filters_by_channel(admin_client, db_session, user):
    devlog.record(db_session, user_id=user.id, channel="planner", event="a", payload={})
    devlog.record(db_session, user_id=user.id, channel="other", event="b", payload={})

    body = admin_client.get(
        "/admin/logs/export", params={"user_id": user.id, "channel": "other"}
    ).json()

    assert [e["event"] for e in body["entries"]] == ["b"]


def test_export_of_an_unknown_user_is_404(admin_client):
    assert admin_client.get("/admin/logs/export", params={"user_id": 10**9}).status_code == 404
