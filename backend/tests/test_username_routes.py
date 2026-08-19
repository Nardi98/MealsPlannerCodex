"""Tests for ``GET /usernames/available`` (UN-3, UN-4, UN-6, UN-7).

The endpoint is reachable without authentication, so these tests cover the
enumeration surface as carefully as the happy path: what the ``reason`` field
is allowed to say, what an oversized query does *before* it reaches the
database, and that the rate limit is really wired on.
"""

import pytest
from fastapi.testclient import TestClient

import crud
import usernames
from conftest import db_client, reset_schema
from main import app


@pytest.fixture
def client(db_session):
    """Unauthenticated client sharing the test's rolled-back transaction."""
    try:
        yield db_client(db_session)
    finally:
        app.dependency_overrides.clear()


def _check(client, value):
    return client.get("/usernames/available", params={"u": value})


# --- availability ----------------------------------------------------------

def test_free_handle_is_available(client):
    resp = _check(client, "brand_new_cook")
    assert resp.status_code == 200
    assert resp.json() == {"available": True, "reason": None}


def test_taken_handle_is_unavailable(client, db_session):
    crud.create_user(
        db_session, email="taken@test.local", username="takenchef",
        hashed_password="x",
    )
    db_session.flush()
    body = _check(client, "takenchef").json()
    assert body["available"] is False
    assert body["reason"] == "taken"


def test_taken_check_is_case_insensitive(client, db_session):
    crud.create_user(
        db_session, email="case@test.local", username="mixedcase",
        hashed_password="x",
    )
    db_session.flush()
    assert _check(client, "MixedCase").json()["available"] is False


def test_reserved_handle_is_unavailable(client, db_session):
    usernames.reserve(db_session, "admin", reason="system")
    db_session.flush()
    body = _check(client, "admin").json()
    assert body["available"] is False
    assert body["reason"] == "reserved"


def test_invalid_handle_reports_the_validation_message(client):
    body = _check(client, "ab").json()
    assert body["available"] is False
    assert "3 characters" in body["reason"]


def test_handle_with_illegal_characters_is_invalid(client):
    body = _check(client, "chef!!").json()
    assert body["available"] is False
    assert body["reason"]


def test_surrounding_whitespace_and_case_are_normalised(client):
    assert _check(client, "  Fresh_Cook  ").json()["available"] is True


# --- input bounds ----------------------------------------------------------

def test_oversized_input_is_rejected_before_the_database(client, monkeypatch):
    """A 5 KB ``u`` must not become a cheap query amplifier."""
    called = []
    monkeypatch.setattr(
        "username_routes.usernames.is_available",
        lambda *a, **k: called.append(1) or True,
    )
    resp = _check(client, "a" * 5000)
    assert resp.status_code == 422
    assert called == []


def test_missing_query_parameter_is_a_validation_error(client):
    assert client.get("/usernames/available").status_code == 422


# --- privacy ---------------------------------------------------------------

def test_response_never_leaks_account_details(client, db_session):
    owner = crud.create_user(
        db_session, email="secret@test.local", username="secretchef",
        hashed_password="x",
    )
    db_session.flush()
    raw = _check(client, "secretchef").text
    assert "secret@test.local" not in raw
    assert str(owner.id) not in raw
    assert set(_check(client, "secretchef").json()) == {"available", "reason"}


# --- UN-7 timing neutrality ------------------------------------------------

def test_every_outcome_runs_the_same_availability_lookup(client, db_session,
                                                         monkeypatch):
    """Free, taken, reserved and malformed all take the identical code path.

    Rather than timing the handler (flaky), this asserts the property that
    makes the timing equal: exactly one ``is_available`` call, which itself
    always runs both queries, for every outcome.
    """
    crud.create_user(
        db_session, email="t@test.local", username="timingtaken",
        hashed_password="x",
    )
    usernames.reserve(db_session, "timingheld", reason="system")
    db_session.flush()

    calls = []
    real = usernames.is_available
    monkeypatch.setattr(
        "username_routes.usernames.is_available",
        lambda session, value, **kw: (
            calls.append(value) or real(session, value, **kw)
        ),
    )
    for handle in ["timingfree", "timingtaken", "timingheld", "!!"]:
        assert _check(client, handle).status_code == 200
    assert len(calls) == 4


# --- UN-7 rate limiting ----------------------------------------------------

def test_endpoint_is_rate_limited(engine, monkeypatch):
    monkeypatch.setattr(app.state.share_limiter, "enabled", True)
    saw_429 = False
    try:
        with TestClient(app) as client:
            for _ in range(60):
                resp = client.get("/usernames/available", params={"u": "abcdef"})
                if resp.status_code == 429:
                    saw_429 = True
                    break
    finally:
        reset_schema(engine)
    assert saw_429
