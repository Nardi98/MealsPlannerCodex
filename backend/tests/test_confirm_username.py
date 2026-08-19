"""Tests for ``POST /auth/username`` -- confirm-once handle selection (D-7).

This is the endpoint that releases a Google sign-up from the SPA's handle
gate: it assigns the chosen handle *and* stamps ``username_changed_at``, which
is what ``username_confirmed`` derives from. It is deliberately **not** the
UN-8/UN-9 change flow, so the tests pin the confirm-once refusal as hard as
they pin the happy path.

The security-shaped cases get the most attention: a reserved handle must be
indistinguishable from a taken one, the database index -- not the availability
check -- is the uniqueness guarantee, and nothing in any response may echo an
email address (UN-11).
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

import crud
import usernames
from conftest import client_as, db_client, reset_schema
from main import app


@pytest.fixture
def unconfirmed(db_session):
    """A Google-shaped account: provisional handle, never confirmed."""
    user = crud.create_user(
        db_session,
        email="anna.rossi@test.local",
        username=None,
        auth_provider="google",
    )
    db_session.flush()
    assert user.username_changed_at is None
    return user


@pytest.fixture
def client(db_session, unconfirmed):
    try:
        yield client_as(db_session, unconfirmed)
    finally:
        app.dependency_overrides.clear()


def _confirm(client, value):
    return client.post("/auth/username", json={"username": value})


# --- happy path ------------------------------------------------------------

def test_confirming_a_free_handle_returns_the_updated_account(client, unconfirmed):
    resp = _confirm(client, "annarossi")
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "annarossi"
    assert body["username_confirmed"] is True
    assert body["id"] == unconfirmed.id


def test_confirming_stamps_username_changed_at(client, db_session, unconfirmed):
    """The whole point: the gate reads ``username_changed_at IS NOT NULL``."""
    assert _confirm(client, "annarossi").status_code == 200
    db_session.refresh(unconfirmed)
    assert unconfirmed.username_changed_at is not None
    assert unconfirmed.username == "annarossi"


def test_handle_is_normalised_before_it_is_stored(client, db_session, unconfirmed):
    assert _confirm(client, "  Chef_Anna  ").status_code == 200
    db_session.refresh(unconfirmed)
    assert unconfirmed.username == "chef_anna"


def test_keeping_the_provisional_handle_confirms_it(client, db_session, unconfirmed):
    """The gate's most likely outcome: "yes, that one is fine".

    The provisional handle is already on the caller's own row, so a naive
    availability check calls it taken and traps the account behind the gate
    forever -- the exact bug this endpoint exists to fix.
    """
    assert unconfirmed.username == "anna_rossi"
    resp = _confirm(client, "anna_rossi")
    assert resp.status_code == 200
    assert resp.json()["username_confirmed"] is True
    db_session.refresh(unconfirmed)
    assert unconfirmed.username == "anna_rossi"
    assert unconfirmed.username_changed_at is not None


# --- confirm-once (UN-8/UN-9 stay deferred) --------------------------------

def test_an_already_confirmed_account_cannot_rename(db_session, user):
    """Renaming is Part 2 (UN-8/UN-9); this route confirms exactly once."""
    user.username_changed_at = datetime.utcnow()
    db_session.flush()
    try:
        client = client_as(db_session, user)
        resp = _confirm(client, "brandnewname")
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 403
    db_session.refresh(user)
    assert user.username == "owner"


def test_confirming_twice_is_refused_the_second_time(client, db_session):
    assert _confirm(client, "annarossi").status_code == 200
    assert _confirm(client, "annarossi2").status_code == 403


# --- rejection paths -------------------------------------------------------

def test_a_taken_handle_is_a_conflict(client, db_session):
    crud.create_user(
        db_session, email="taken@test.local", username="takenchef",
        hashed_password="x",
    )
    db_session.flush()
    resp = _confirm(client, "takenchef")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "That username is taken"


def test_a_taken_handle_is_matched_case_insensitively(client, db_session):
    crud.create_user(
        db_session, email="taken@test.local", username="mixedcase",
        hashed_password="x",
    )
    db_session.flush()
    assert _confirm(client, "MixedCase").status_code == 409


def test_a_reserved_handle_is_refused(client, db_session):
    usernames.reserve(db_session, "admin", reason="system")
    db_session.flush()
    assert _confirm(client, "admin").status_code == 409


def test_a_reserved_handle_is_indistinguishable_from_a_taken_one(client, db_session):
    """Telling them apart would map the structurally blocked handle space."""
    usernames.reserve(db_session, "static", reason="system")
    crud.create_user(
        db_session, email="held@test.local", username="heldchef",
        hashed_password="x",
    )
    db_session.flush()
    reserved = _confirm(client, "static")
    taken = _confirm(client, "heldchef")
    assert reserved.status_code == taken.status_code == 409
    assert reserved.json() == taken.json()


def test_an_expired_reservation_can_be_claimed(client, db_session, unconfirmed):
    usernames.reserve(
        db_session, "oldhandle", reason="released",
        reserved_until=datetime(2000, 1, 1),
    )
    db_session.flush()
    assert _confirm(client, "oldhandle").status_code == 200


@pytest.mark.parametrize(
    "bad, fragment",
    [
        ("ab", "3 characters"),
        ("_leading", "underscore"),
        ("trailing_", "underscore"),
        ("two__scores", "two underscores"),
        ("chef!!", "lowercase letters"),
        ("a" * 31, "30 characters"),
    ],
)
def test_an_invalid_handle_is_a_bad_request(client, bad, fragment):
    resp = _confirm(client, bad)
    assert resp.status_code == 400
    assert fragment in resp.json()["detail"]


def test_an_empty_handle_is_rejected(client):
    assert _confirm(client, "").status_code == 400


def test_an_oversized_body_is_rejected_before_the_database(client, monkeypatch):
    called = []
    monkeypatch.setattr(
        "username_routes.usernames.is_available",
        lambda *a, **k: called.append(1) or True,
    )
    assert _confirm(client, "a" * 5000).status_code == 422
    assert called == []


def test_a_rejected_request_leaves_the_account_untouched(client, db_session,
                                                         unconfirmed):
    before = unconfirmed.username
    assert _confirm(client, "chef!!").status_code == 400
    db_session.refresh(unconfirmed)
    assert unconfirmed.username == before
    assert unconfirmed.username_changed_at is None


# --- concurrency: the database is the guarantee ----------------------------

def test_a_lost_race_is_a_conflict_not_a_server_error(client, db_session,
                                                      unconfirmed, monkeypatch):
    """``uq_user_username_lower`` -- not ``is_available`` -- is the guarantee.

    Two callers can both pass the availability check; the loser must see the
    same 409 as anyone else, never a 500. Simulated deterministically by
    forcing the check to say "free" while the row already exists, which is
    exactly the state the loser of the real race observes.
    """
    crud.create_user(
        db_session, email="winner@test.local", username="contested",
        hashed_password="x",
    )
    db_session.flush()
    monkeypatch.setattr(
        "username_routes.usernames.is_available", lambda *a, **k: True
    )
    resp = _confirm(client, "contested")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "That username is taken"


def test_the_session_is_usable_after_a_lost_race(client, db_session,
                                                 unconfirmed, monkeypatch):
    """The rollback must be scoped, so the caller can simply retry."""
    crud.create_user(
        db_session, email="winner@test.local", username="contested",
        hashed_password="x",
    )
    db_session.flush()
    calls = []
    real = usernames.is_available
    monkeypatch.setattr(
        "username_routes.usernames.is_available",
        lambda s, v, **k: True if not calls.append(v) and len(calls) == 1 else real(s, v, **k),
    )
    assert _confirm(client, "contested").status_code == 409
    assert _confirm(client, "freehandle").status_code == 200
    db_session.refresh(unconfirmed)
    assert unconfirmed.username == "freehandle"


# --- identity and privacy --------------------------------------------------

def test_the_body_cannot_redirect_the_write_to_another_account(client, db_session,
                                                               other_user,
                                                               unconfirmed):
    """Identity comes from the token only -- never from the payload."""
    before = other_user.username_changed_at
    resp = client.post(
        "/auth/username",
        json={"username": "annarossi", "user_id": other_user.id,
              "id": other_user.id, "email": other_user.email},
    )
    assert resp.status_code == 200
    db_session.refresh(other_user)
    db_session.refresh(unconfirmed)
    assert other_user.username == "other"
    # The write landed on the token's account, not the payload's. Asserted as
    # "the stamp did not move" rather than "the stamp is NULL": ``other_user``
    # is created with an explicit handle, which D-7 counts as *chosen* and so
    # already confirmed, so NULL was never the interesting property -- what
    # matters is that this request did not touch the row at all.
    assert other_user.username_changed_at == before
    assert unconfirmed.username == "annarossi"


def test_no_response_echoes_another_accounts_email(client, db_session):
    """UN-11: no error may leak the address behind a handle."""
    crud.create_user(
        db_session, email="private@test.local", username="privatechef",
        hashed_password="x",
    )
    db_session.flush()
    raw = _confirm(client, "privatechef").text
    assert "private@test.local" not in raw
    assert "privatechef" not in raw


def test_the_success_response_matches_get_auth_me(client, db_session):
    resp = _confirm(client, "annarossi")
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert set(resp.json()) == set(me.json())
    assert resp.json() == me.json()


# --- auth ------------------------------------------------------------------

def test_an_unauthenticated_caller_is_refused(db_session):
    try:
        client = db_client(db_session)
        resp = client.post("/auth/username", json={"username": "annarossi"})
    finally:
        app.dependency_overrides.clear()
    assert resp.status_code == 401


# --- rate limiting ---------------------------------------------------------

def test_endpoint_is_rate_limited(engine, monkeypatch):
    """Authenticated, because ``get_current_user`` resolves before the limiter."""
    import auth_users
    import models
    from database import SessionLocal, get_db
    from fastapi import Depends

    session = SessionLocal()
    holder_id = crud.create_user(
        session, email="limited@test.local", username="limitedchef",
        hashed_password="x",
    ).id
    session.commit()
    session.close()

    # Resolved from the request's own session: the route refreshes the user it
    # is handed, which only works if it belongs to that session.
    def _holder(db=Depends(get_db)):
        return db.get(models.User, holder_id)

    monkeypatch.setattr(app.state.share_limiter, "enabled", True)
    app.dependency_overrides[auth_users.get_current_user] = _holder
    saw_429 = False
    try:
        with TestClient(app) as client:
            for _ in range(60):
                resp = client.post("/auth/username", json={"username": "abcdef"})
                if resp.status_code == 429:
                    saw_429 = True
                    break
    finally:
        app.dependency_overrides.clear()
        reset_schema(engine)
    assert saw_429
