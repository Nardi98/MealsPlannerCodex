"""Google sign-in: ID-token verification and find-or-create account flow."""
import pytest

import auth_users
import crud
import models
from conftest import db_client
from main import app


@pytest.fixture
def client(db_session):
    try:
        yield db_client(db_session)
    finally:
        app.dependency_overrides.clear()


def fake_claims(**overrides):
    claims = {
        "sub": "google-sub-123",
        "email": "gina@gmail.com",
        "email_verified": True,
        "name": "Gina Green",
    }
    claims.update(overrides)
    return claims


def test_google_login_creates_new_account(client, db_session, monkeypatch):
    monkeypatch.setattr(
        auth_users, "verify_google_token", lambda credential: fake_claims()
    )

    resp = client.post("/auth/google", json={"credential": "any-id-token"})

    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"
    user = crud.get_user_by_google_sub(db_session, "google-sub-123")
    assert user is not None
    assert user.email == "gina@gmail.com"
    assert user.display_name == "Gina Green"
    assert user.auth_provider == "google"
    assert user.hashed_password is None


def test_google_login_token_identifies_the_new_user(client, db_session, monkeypatch):
    monkeypatch.setattr(
        auth_users, "verify_google_token", lambda credential: fake_claims()
    )

    resp = client.post("/auth/google", json={"credential": "any-id-token"})

    user = crud.get_user_by_google_sub(db_session, "google-sub-123")
    assert auth_users.decode_token(resp.json()["access_token"]) == str(user.id)


def test_google_login_seeds_system_tags_for_new_account(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(
        auth_users, "verify_google_token", lambda credential: fake_claims()
    )

    client.post("/auth/google", json={"credential": "any-id-token"})

    user = crud.get_user_by_google_sub(db_session, "google-sub-123")
    tags = db_session.query(models.Tag).filter(models.Tag.user_id == user.id).all()
    assert tags, "a brand-new Google account should start with system tags"


def test_google_login_reuses_existing_account(client, db_session, monkeypatch):
    monkeypatch.setattr(
        auth_users, "verify_google_token", lambda credential: fake_claims()
    )
    existing = crud.create_user(
        db_session,
        email="gina@gmail.com",
        auth_provider="google",
        google_sub="google-sub-123",
    )

    resp = client.post("/auth/google", json={"credential": "any-id-token"})

    assert resp.status_code == 200
    assert auth_users.decode_token(resp.json()["access_token"]) == str(existing.id)
    assert (
        db_session.query(crud.User)
        .filter(crud.User.google_sub == "google-sub-123")
        .count()
        == 1
    )


def test_google_login_links_sub_to_existing_local_account(
    client, db_session, monkeypatch
):
    """Google verifies the email, so the same address is the same person."""
    monkeypatch.setattr(
        auth_users, "verify_google_token", lambda credential: fake_claims()
    )
    local = crud.create_user(
        db_session, email="gina@gmail.com", hashed_password="hashed"
    )

    resp = client.post("/auth/google", json={"credential": "any-id-token"})

    assert resp.status_code == 200
    assert auth_users.decode_token(resp.json()["access_token"]) == str(local.id)
    db_session.refresh(local)
    assert local.google_sub == "google-sub-123"
    # The local password still works — linking must not lock the user out.
    assert local.hashed_password == "hashed"


def test_google_login_refuses_to_link_an_unverified_email(
    client, db_session, monkeypatch
):
    """An unverified address proves nothing — linking it would hand over the account."""
    monkeypatch.setattr(
        auth_users,
        "verify_google_token",
        lambda credential: fake_claims(email_verified=False),
    )
    local = crud.create_user(
        db_session, email="gina@gmail.com", hashed_password="hashed"
    )

    resp = client.post("/auth/google", json={"credential": "any-id-token"})

    assert resp.status_code == 401
    db_session.refresh(local)
    assert local.google_sub is None


def test_google_login_rejects_an_invalid_token(client, monkeypatch):
    def _boom(credential):
        raise ValueError("bad token")

    monkeypatch.setattr(auth_users, "verify_google_token", _boom)

    resp = client.post("/auth/google", json={"credential": "forged"})

    assert resp.status_code == 401
    assert "Google" in resp.json()["detail"]


def test_verify_google_token_requires_client_id_configuration(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)

    with pytest.raises(ValueError, match="GOOGLE_CLIENT_ID"):
        auth_users.verify_google_token("any-id-token")
