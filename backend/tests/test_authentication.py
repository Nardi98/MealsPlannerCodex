"""Authentication API integration tests."""

import pytest


def test_user_registration(register_user):
    response, payload = register_user()
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == payload["email"]
    assert data["username"] == payload["username"]
    assert "id" in data


def test_duplicate_email_rejected(register_user):
    response, payload = register_user(email="duplicate@example.com")
    assert response.status_code == 201

    duplicate_response, _ = register_user(email=payload["email"], username="other")
    assert duplicate_response.status_code == 400
    assert "already exists" in duplicate_response.json()["detail"]


def test_successful_login_by_email_and_username(register_user, login_user):
    response, payload = register_user()
    assert response.status_code == 201

    email_login = login_user(payload["email"], payload["password"])
    assert email_login.status_code == 200
    token = email_login.json()["access_token"]
    assert token

    username_login = login_user(payload["username"], payload["password"])
    assert username_login.status_code == 200
    assert username_login.json()["access_token"]


@pytest.mark.parametrize(
    "identifier, password",
    [
        ("missing@example.com", "invalid"),
        ("", ""),
    ],
)
def test_failed_login_returns_401(identifier, password, login_user):
    response = login_user(identifier, password)
    assert response.status_code == 401
    assert "Incorrect" in response.json()["detail"]


def test_protected_route_requires_valid_token(client, register_user, login_user):
    unauthenticated = client.get("/recipes")
    assert unauthenticated.status_code == 401

    response, payload = register_user()
    assert response.status_code == 201
    login_response = login_user(payload["email"], payload["password"])
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    recipes_response = client.get("/recipes", headers=headers)
    assert recipes_response.status_code == 200
    assert recipes_response.json() == []
