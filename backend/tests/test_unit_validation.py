"""Tests for ingredient unit validation on recipe creation."""


def test_invalid_unit_rejected(client, user_token_factory):
    auth = user_token_factory()
    payload = {
        "title": "Salad",
        "servings_default": 1,
        "procedure": "",
        "bulk_prep": False,
        "course": "main",
        "tags": [],
        "ingredients": [
            {"name": "Lettuce", "quantity": 1, "unit": "bag"},
        ],
    }
    res = client.post("/recipes", json=payload, headers=auth.headers)
    assert res.status_code == 422


def test_invalid_unit_requires_authentication(client):
    payload = {
        "title": "Salad",
        "servings_default": 1,
        "ingredients": [
            {"name": "Lettuce", "quantity": 1, "unit": "bag"},
        ],
    }
    assert client.post("/recipes", json=payload).status_code == 401
