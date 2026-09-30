"""ALPHA-GATE: the signup gate at ``/auth/register`` and ``/auth/google``.

Temporary scaffolding, deleted whole when the alpha ends.

Two properties matter more than the happy path and are asserted here rather than
inferred: the gate **fails open** on an empty table (a wiped or half-migrated
database must not lock everyone out), and it sits *before* ``/auth/register``'s
duplicate-email lookup, so the endpoint's existing anti-enumeration guarantee
survives — an uninvited address gets the same answer whether or not an account
already holds it. Sign-in is never gated: only account *creation* is.
"""

import pytest
from sqlalchemy import func, select

import alpha
import auth_users
import crud
import models
from main import app
from tests.conftest import db_client

PASSWORD = "Pw123456"


@pytest.fixture
def client(db_session):
    try:
        yield db_client(db_session)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def invite(db_session):
    def _invite(email):
        row = models.AlphaInvite(email=email)
        db_session.add(row)
        db_session.flush()
        return row

    return _invite


@pytest.fixture
def google(monkeypatch):
    """Stub ``verify_google_token`` to return claims for a chosen address."""

    def _use(email, *, sub="google-sub-123", email_verified=True):
        claims = {
            "sub": sub,
            "email": email,
            "email_verified": email_verified,
            "name": "Gina Green",
        }
        monkeypatch.setattr(
            auth_users, "verify_google_token", lambda credential: claims
        )

    return _use


def _register(client, email):
    return client.post(
        "/auth/register", json={"email": email, "password": PASSWORD}
    )


def _user_count(session):
    return session.scalar(select(func.count()).select_from(models.User))


# --- Fail open ----------------------------------------------------------------


def test_registration_still_works_with_an_empty_invite_table(client, db_session):
    """Fail open: no invites listed means the gate is not switched on at all."""
    response = _register(client, "anyone@example.com")

    assert response.status_code == 201, response.text
    assert crud.get_user_by_email(db_session, "anyone@example.com") is not None


# --- /auth/register -----------------------------------------------------------


def test_an_uninvited_email_is_refused_and_creates_no_account(
    client, db_session, invite
):
    invite("listed@example.com")
    before = _user_count(db_session)

    response = _register(client, "stranger@example.com")

    assert response.status_code == 403
    assert response.json() == {"detail": alpha.NOT_INVITED_DETAIL}
    assert crud.get_user_by_email(db_session, "stranger@example.com") is None
    assert _user_count(db_session) == before


def test_an_invited_email_registers(client, invite):
    invite("listed@example.com")

    assert _register(client, "listed@example.com").status_code == 201


def test_an_invite_stored_in_another_case_still_matches(client, invite):
    invite("  Listed@Example.COM ")

    assert _register(client, "listed@example.com").status_code == 201


def test_an_uninvited_existing_account_gets_the_same_403_as_an_unknown_address(
    client, db_session, invite
):
    """Anti-enumeration: the gate runs before the duplicate-email lookup.

    If it ran after, an uninvited address that already had an account would get
    the neutral 201 while an unknown one got a 403 — turning the pair of
    responses into exactly the oracle the neutral path exists to prevent.
    """
    invite("listed@example.com")
    crud.create_user(
        db_session,
        email="unlisted-existing@example.com",
        username="oldaccount",
        hashed_password="x",
    )
    db_session.flush()

    known_but_unlisted = _register(client, "unlisted-existing@example.com")
    unknown = _register(client, "unlisted-unknown@example.com")

    assert known_but_unlisted.status_code == unknown.status_code == 403
    assert known_but_unlisted.content == unknown.content


def test_an_invited_address_that_already_has_an_account_stays_neutral(
    client, invite
):
    invite("listed@example.com")
    assert _register(client, "listed@example.com").status_code == 201

    again = _register(client, "listed@example.com")

    assert again.status_code == 201
    assert again.json()["email"] == "listed@example.com"


# --- /auth/google -------------------------------------------------------------


def test_google_refuses_to_create_an_account_for_an_uninvited_address(
    client, db_session, invite, google
):
    invite("listed@example.com")
    google("stranger@gmail.com")

    response = client.post("/auth/google", json={"credential": "any-id-token"})

    assert response.status_code == 403
    assert response.json() == {"detail": alpha.NOT_INVITED_DETAIL}
    assert crud.get_user_by_email(db_session, "stranger@gmail.com") is None


def test_google_creates_an_account_for_an_invited_address(client, invite, google):
    invite("gina@gmail.com")
    google("gina@gmail.com")

    response = client.post("/auth/google", json={"credential": "any-id-token"})

    assert response.status_code == 200, response.text


def test_google_sign_in_for_an_existing_unlisted_account_is_never_gated(
    client, db_session, invite, google
):
    account = crud.create_user(
        db_session,
        email="oldtimer@gmail.com",
        username="oldtimer",
        hashed_password=None,
    )
    account.google_sub = "google-sub-old"
    account.email_verified = True
    db_session.flush()
    invite("someone-else@example.com")
    google("oldtimer@gmail.com", sub="google-sub-old")

    response = client.post("/auth/google", json={"credential": "any-id-token"})

    assert response.status_code == 200, response.text


# --- Sign-in paths are untouched ----------------------------------------------


def test_login_and_refresh_still_work_for_an_existing_unlisted_account(
    client, db_session, invite
):
    """Only account creation is gated; an existing tester is never locked out."""
    user = crud.create_user(
        db_session,
        email="already@example.com",
        username="already",
        hashed_password=auth_users.hash_password(PASSWORD),
    )
    crud.set_email_verified(db_session, user, True)
    db_session.flush()
    invite("someone-else@example.com")

    login = client.post(
        "/auth/login", json={"email": "already@example.com", "password": PASSWORD}
    )
    refresh = client.post("/auth/refresh")

    assert login.status_code == 200, login.text
    assert refresh.status_code == 200, refresh.text
