"""Tests for user model, password hashing, JWT, and auth routes (Step 1)."""
import auth_users
import crud
from conftest import db_client
from main import app


# --- password hashing -------------------------------------------------------

def test_hash_password_verifies_correctly():
    hashed = auth_users.hash_password("s3cret")
    assert hashed != "s3cret"
    assert auth_users.verify_password("s3cret", hashed)
    assert not auth_users.verify_password("wrong", hashed)


# --- JWT --------------------------------------------------------------------

def test_create_and_decode_token_roundtrips_subject():
    token = auth_users.create_access_token(subject="42")
    assert auth_users.decode_token(token) == "42"


def test_decode_invalid_token_returns_none():
    assert auth_users.decode_token("not-a-token") is None


# --- crud -------------------------------------------------------------------

def test_create_and_lookup_user_by_email(db_session):
    user = crud.create_user(
        db_session, email="a@b.com", hashed_password="hp", display_name="Al"
    )
    assert user.id is not None
    assert user.auth_provider == "local"
    found = crud.get_user_by_email(db_session, "a@b.com")
    assert found is not None and found.id == user.id


def test_create_user_stores_email_lowercased(db_session):
    user = crud.create_user(
        db_session, email="  Mixed.Case@Example.COM ", hashed_password="hp"
    )
    assert user.email == "mixed.case@example.com"


def test_lookup_user_by_email_ignores_case(db_session):
    user = crud.create_user(
        db_session, email="Case@Example.com", hashed_password="hp"
    )
    found = crud.get_user_by_email(db_session, "CASE@EXAMPLE.COM")
    assert found is not None and found.id == user.id


# --- routes -----------------------------------------------------------------

def test_register_login_me_flow(db_session):
    client = db_client(db_session)
    try:
        resp = client.post(
            "/auth/register",
            json={"email": "u@x.com", "password": "pw12345", "display_name": "U"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["email"] == "u@x.com"
        assert "hashed_password" not in resp.json()

        # duplicate email rejected
        resp = client.post(
            "/auth/register",
            json={"email": "u@x.com", "password": "pw12345", "display_name": "U"},
        )
        assert resp.status_code == 400

        # login success
        resp = client.post(
            "/auth/login", json={"email": "u@x.com", "password": "pw12345"}
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        assert token

        # login failure
        resp = client.post(
            "/auth/login", json={"email": "u@x.com", "password": "nope"}
        )
        assert resp.status_code == 401

        # /auth/me with token
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "u@x.com"

        # /auth/me without token
        resp = client.get("/auth/me")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_register_normalises_email_and_login_ignores_case(db_session):
    """Signing up shouty and logging in quiet is the same person."""
    client = db_client(db_session)
    try:
        resp = client.post(
            "/auth/register",
            json={"email": "Shouty.User@Example.COM", "password": "pw12345"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["email"] == "shouty.user@example.com"

        resp = client.post(
            "/auth/login",
            json={"email": "shouty.user@example.com", "password": "pw12345"},
        )
        assert resp.status_code == 200, resp.text
    finally:
        app.dependency_overrides.clear()


def test_register_rejects_duplicate_email_differing_only_in_case(db_session):
    client = db_client(db_session)
    try:
        resp = client.post(
            "/auth/register",
            json={"email": "dupe@example.com", "password": "pw12345"},
        )
        assert resp.status_code == 201, resp.text

        resp = client.post(
            "/auth/register",
            json={"email": "DUPE@Example.com", "password": "pw12345"},
        )
        assert resp.status_code == 400, resp.text
    finally:
        app.dependency_overrides.clear()
