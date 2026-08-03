"""Auth-hardening coverage: fail-closed secret, token lifecycle, refresh
rotation/revocation, verification gate, enumeration neutrality, email flows,
and rate limiting."""
import re

import pytest

import auth_users
import crud
import mailer
import models
from conftest import db_client
from main import app


@pytest.fixture
def client(db_session):
    try:
        yield db_client(db_session)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _clear_outbox():
    mailer.outbox.clear()
    yield
    mailer.outbox.clear()


def _register(client, email, password="Pw123456", display_name=None):
    return client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": display_name},
    )


def _token_from_outbox(pattern="token="):
    body = mailer.outbox[-1].body
    return re.search(pattern + r"([A-Za-z0-9._-]+)", body).group(1)


# --- #1 JWT secret fail-closed ---------------------------------------------

def test_resolve_jwt_secret_requires_env(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("AUTH_DEV_MODE", raising=False)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        auth_users.resolve_jwt_secret()


def test_resolve_jwt_secret_dev_flag_allows_default(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("AUTH_DEV_MODE", "1")
    assert auth_users.resolve_jwt_secret()


# --- #5 token lifecycle -----------------------------------------------------

def test_access_token_carries_type_iat_jti():
    import jwt

    token = auth_users.create_access_token("7")
    payload = jwt.decode(token, auth_users.SECRET_KEY, algorithms=[auth_users.ALGORITHM])
    assert payload["type"] == "access"
    assert payload["sub"] == "7"
    assert payload["jti"] and payload["iat"]


def test_decode_token_rejects_refresh_token():
    refresh, _jti, _exp = auth_users.create_refresh_token("7")
    assert auth_users.decode_token(refresh) is None


# --- verification gate on login --------------------------------------------

def _verify(db_session, email):
    user = crud.get_user_by_email(db_session, email)
    crud.set_email_verified(db_session, user, True)


def test_login_blocks_unverified_account(client):
    _register(client, "unv@x.com")
    resp = client.post("/auth/login", json={"email": "unv@x.com", "password": "Pw123456"})
    assert resp.status_code == 403


def test_login_sets_refresh_cookie_when_verified(client, db_session):
    _register(client, "v@x.com")
    _verify(db_session, "v@x.com")
    resp = client.post("/auth/login", json={"email": "v@x.com", "password": "Pw123456"})
    assert resp.status_code == 200
    assert "refresh_token" in resp.cookies


# --- #6 enumeration neutrality ---------------------------------------------

def test_register_unknown_email_sends_verification(client):
    resp = _register(client, "new@x.com")
    assert resp.status_code == 201
    assert mailer.outbox and mailer.outbox[-1].to == "new@x.com"


def test_register_duplicate_is_silent(client):
    _register(client, "dup@x.com")
    mailer.outbox.clear()
    resp = _register(client, "dup@x.com")
    assert resp.status_code == 201
    # No second verification email leaks that the account already exists.
    assert mailer.outbox == []


# --- #3 email verification + reset flows ------------------------------------

def test_verify_email_marks_account_verified(client, db_session):
    _register(client, "verify@x.com")
    token = _token_from_outbox()
    resp = client.post("/auth/verify-email", json={"token": token})
    assert resp.status_code == 200
    assert crud.get_user_by_email(db_session, "verify@x.com").email_verified is True


def test_verify_email_rejects_bad_token(client):
    resp = client.post("/auth/verify-email", json={"token": "garbage"})
    assert resp.status_code == 400


def test_forgot_password_is_always_neutral(client):
    # Unknown address: still 200, no email.
    resp = client.post("/auth/forgot-password", json={"email": "nobody@x.com"})
    assert resp.status_code == 200
    assert mailer.outbox == []


def test_reset_password_updates_and_revokes_sessions(client, db_session):
    _register(client, "reset@x.com")
    _verify(db_session, "reset@x.com")
    login = client.post("/auth/login", json={"email": "reset@x.com", "password": "Pw123456"})
    assert login.status_code == 200
    user = crud.get_user_by_email(db_session, "reset@x.com")

    mailer.outbox.clear()
    client.post("/auth/forgot-password", json={"email": "reset@x.com"})
    token = _token_from_outbox()

    resp = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "Newpass99"}
    )
    assert resp.status_code == 200
    db_session.refresh(user)
    assert auth_users.verify_password("Newpass99", user.hashed_password)
    # Every refresh token for the user is revoked.
    active = [t for t in db_session.query(models.RefreshToken).filter_by(user_id=user.id) if not t.revoked]
    assert active == []


def test_reset_password_rejects_short_password(client, db_session):
    _register(client, "shortpw@x.com")
    _verify(db_session, "shortpw@x.com")
    client.post("/auth/forgot-password", json={"email": "shortpw@x.com"})
    token = _token_from_outbox()
    resp = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "short"}
    )
    assert resp.status_code == 422


# --- refresh rotation / revocation / logout --------------------------------

def _login(client, db_session, email):
    _register(client, email)
    _verify(db_session, email)
    resp = client.post("/auth/login", json={"email": email, "password": "Pw123456"})
    return resp.cookies["refresh_token"]


def test_refresh_rotates_and_invalidates_old_cookie(client, db_session):
    old = _login(client, db_session, "rot@x.com")

    resp = client.post("/auth/refresh", cookies={"refresh_token": old})
    assert resp.status_code == 200
    assert resp.json()["access_token"]
    new = resp.cookies["refresh_token"]
    assert new != old

    # Old token is revoked; reusing it fails.
    reuse = client.post("/auth/refresh", cookies={"refresh_token": old})
    assert reuse.status_code == 401
    # New token still works.
    assert client.post("/auth/refresh", cookies={"refresh_token": new}).status_code == 200


def test_refresh_without_cookie_is_401(client):
    assert client.post("/auth/refresh").status_code == 401


def test_logout_revokes_refresh_token(client, db_session):
    token = _login(client, db_session, "out@x.com")
    resp = client.post("/auth/logout", cookies={"refresh_token": token})
    assert resp.status_code == 204
    assert client.post("/auth/refresh", cookies={"refresh_token": token}).status_code == 401


# --- #8 Google create requires a verified claim -----------------------------

def _fake_claims(**overrides):
    claims = {
        "sub": "gsub-1",
        "email": "gcreate@gmail.com",
        "email_verified": True,
        "name": "G",
    }
    claims.update(overrides)
    return claims


def test_google_create_requires_verified_email(client, monkeypatch):
    monkeypatch.setattr(
        auth_users, "verify_google_token", lambda c: _fake_claims(email_verified=False)
    )
    resp = client.post("/auth/google", json={"credential": "x"})
    assert resp.status_code == 401


def test_google_create_sets_refresh_cookie(client, monkeypatch):
    monkeypatch.setattr(auth_users, "verify_google_token", lambda c: _fake_claims())
    resp = client.post("/auth/google", json={"credential": "x"})
    assert resp.status_code == 200
    assert "refresh_token" in resp.cookies


# --- #4 rate limiting -------------------------------------------------------

def test_auth_endpoint_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(app.state.limiter, "enabled", True)
    saw_429 = False
    for _ in range(40):
        resp = client.post("/auth/login", json={"email": "rl@x.com", "password": "Pw123456"})
        if resp.status_code == 429:
            saw_429 = True
            break
    assert saw_429
