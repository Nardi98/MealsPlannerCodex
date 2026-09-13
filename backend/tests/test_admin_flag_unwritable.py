"""``is_admin`` is readable, gate-able, and never writable over HTTP.

ADM-2 makes privilege escalation over HTTP impossible *by construction*: no
route, service or startup path writes ``is_admin``; it is granted by SQL alone.
PRV-4 / TST-6 want that proven rather than asserted, so every user-updating
endpoint below is sent ``"is_admin": true`` in its body and the database is
then asked whether anybody became an admin.

Also here: ``auth_users.require_admin`` (ADM-3), exercised on a throwaway app
so the test does not depend on any admin route existing yet, and
``GET /auth/me`` exposing the flag (ADM-5).
"""

from datetime import date

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

import auth_users
import crud
import mailer
import models
from conftest import client_as, db_client
from database import get_db
from main import app


def _admin_count(db_session) -> int:
    db_session.expire_all()
    return db_session.scalar(
        select(func.count()).select_from(models.User).where(models.User.is_admin.is_(True))
    )


@pytest.fixture(autouse=True)
def _clean_overrides_and_outbox():
    mailer.outbox.clear()
    yield
    app.dependency_overrides.clear()
    mailer.outbox.clear()


# --- require_admin (ADM-3) ---------------------------------------------------

@pytest.fixture
def gated(db_session):
    """A throwaway app with one route behind ``require_admin``."""
    throwaway = FastAPI()

    @throwaway.get("/gated")
    def _gated(current_user: models.User = Depends(auth_users.require_admin)):
        return {"id": current_user.id}

    def _db():
        yield db_session

    throwaway.dependency_overrides[get_db] = _db
    return throwaway


def test_require_admin_rejects_the_unauthenticated_with_401(gated):
    resp = TestClient(gated).get("/gated")
    assert resp.status_code == 401


def test_require_admin_rejects_a_non_admin_with_403(gated, user):
    gated.dependency_overrides[auth_users.get_current_user] = lambda: user
    resp = TestClient(gated).get("/gated")
    assert resp.status_code == 403
    assert resp.json() == {"detail": "Forbidden"}


def test_require_admin_returns_the_admin(gated, admin_user):
    gated.dependency_overrides[auth_users.get_current_user] = lambda: admin_user
    resp = TestClient(gated).get("/gated")
    assert resp.status_code == 200
    assert resp.json() == {"id": admin_user.id}


# --- GET /auth/me (ADM-5) ----------------------------------------------------

def test_auth_me_reports_a_non_admin(db_session, user):
    body = client_as(db_session, user).get("/auth/me").json()
    assert body["is_admin"] is False


def test_auth_me_reports_an_admin(db_session, admin_user):
    body = client_as(db_session, admin_user).get("/auth/me").json()
    assert body["is_admin"] is True


# --- PRV-4 / TST-6: no HTTP path writes is_admin -----------------------------

def test_register_ignores_is_admin(db_session):
    resp = db_client(db_session).post(
        "/auth/register",
        json={
            "email": "climber@example.com",
            "password": "Pw123456",
            "username": "climber",
            "is_admin": True,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["is_admin"] is False
    assert crud.get_user_by_email(db_session, "climber@example.com") is not None
    assert _admin_count(db_session) == 0


def test_login_ignores_is_admin(db_session):
    account = crud.create_user(
        db_session,
        email="login@example.com",
        username="loginuser",
        hashed_password=auth_users.hash_password("Pw123456"),
        email_verified=True,
    )
    resp = db_client(db_session).post(
        "/auth/login",
        json={"email": account.email, "password": "Pw123456", "is_admin": True},
    )
    assert resp.status_code == 200
    assert _admin_count(db_session) == 0


def test_forgot_password_ignores_is_admin(db_session):
    crud.create_user(
        db_session,
        email="forgot@example.com",
        username="forgotuser",
        hashed_password=auth_users.hash_password("Pw123456"),
    )
    # Both the existing-account path and the neutral unknown-address path.
    for email in ("forgot@example.com", "nobody@example.com"):
        resp = db_client(db_session).post(
            "/auth/forgot-password", json={"email": email, "is_admin": True}
        )
        assert resp.status_code == 200
    assert mailer.outbox, "the existing-account path should have sent a reset email"
    assert _admin_count(db_session) == 0


def test_google_sign_in_ignores_is_admin(db_session, monkeypatch):
    monkeypatch.setattr(
        auth_users,
        "verify_google_token",
        lambda credential: {
            "sub": "google-sub-admin",
            "email": "gina@gmail.com",
            "email_verified": True,
            "name": "Gina",
        },
    )
    resp = db_client(db_session).post(
        "/auth/google", json={"credential": "any", "is_admin": True}
    )
    assert resp.status_code == 200
    assert crud.get_user_by_google_sub(db_session, "google-sub-admin") is not None
    assert _admin_count(db_session) == 0


def test_verify_email_ignores_is_admin(db_session, user):
    token = auth_users.create_email_token(str(user.id), "verify", 60)
    resp = db_client(db_session).post(
        "/auth/verify-email", json={"token": token, "is_admin": True}
    )
    assert resp.status_code == 200
    assert _admin_count(db_session) == 0


def test_reset_password_ignores_is_admin(db_session, user):
    token = auth_users.create_email_token(str(user.id), "reset", 60)
    resp = db_client(db_session).post(
        "/auth/reset-password",
        json={"token": token, "new_password": "Newpass99", "is_admin": True},
    )
    assert resp.status_code == 200
    assert _admin_count(db_session) == 0


def test_default_people_ignores_is_admin(db_session, user):
    resp = client_as(db_session, user).put(
        "/auth/me/default-people",
        json={
            "people": 3,
            "start_date": date.today().isoformat(),
            "end_date": date.today().isoformat(),
            "is_admin": True,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["is_admin"] is False
    assert _admin_count(db_session) == 0


def test_unit_system_ignores_is_admin(db_session, user):
    resp = client_as(db_session, user).put(
        "/auth/me/unit-system", json={"unit_system": "us", "is_admin": True}
    )
    assert resp.status_code == 200
    assert resp.json()["is_admin"] is False
    assert _admin_count(db_session) == 0


def test_plan_settings_ignores_is_admin(db_session, user):
    # API-19: the deprecated route is only *used* here, never changed.
    resp = client_as(db_session, user).put(
        "/plan/settings", json={"LEFTOVER_REPEAT_DEFAULT": 3, "is_admin": True}
    )
    assert resp.status_code == 200
    assert _admin_count(db_session) == 0


def test_confirm_username_ignores_is_admin(db_session):
    unconfirmed = crud.create_user(
        db_session, email="gus@test.local", username=None, auth_provider="google"
    )
    resp = client_as(db_session, unconfirmed).post(
        "/auth/username", json={"username": "gusgus", "is_admin": True}
    )
    assert resp.status_code == 200
    assert resp.json()["is_admin"] is False
    assert _admin_count(db_session) == 0
