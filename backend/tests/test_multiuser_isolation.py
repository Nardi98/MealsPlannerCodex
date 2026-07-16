"""Step 3b tests: recipes / ingredients / tags routes are private per user.

Each request runs through the real FastAPI routes with ``get_db`` pinned to the
test session and ``get_current_user`` overridden to a chosen user, so switching
the override simulates a different logged-in account against shared storage.
"""

import crud
from conftest import client_as as _client, db_client
from main import app


def _recipe_payload(title, **over):
    payload = {
        "title": title,
        "servings_default": 1,
        "course": "main",
        "tags": [],
        "ingredients": [],
    }
    payload.update(over)
    return payload


def _two_users(session):
    a = crud.create_user(session, email="a@x.com", hashed_password="h")
    b = crud.create_user(session, email="b@x.com", hashed_password="h")
    return a, b


def test_recipes_are_private_per_user(db_session):
    a, b = _two_users(db_session)
    try:
        ca = _client(db_session, a)
        rid = ca.post("/recipes", json=_recipe_payload("A Soup")).json()["id"]
        assert any(r["title"] == "A Soup" for r in ca.get("/recipes").json())

        cb = _client(db_session, b)
        assert cb.get("/recipes").json() == []
        assert cb.get(f"/recipes/{rid}").status_code == 404
        assert cb.put(
            f"/recipes/{rid}", json=_recipe_payload("Hacked")
        ).status_code == 404
        assert cb.delete(f"/recipes/{rid}").status_code == 404

        # A still owns an untouched recipe (re-select A: the overrides are
        # global, so the previous ``_client`` call switched the active user).
        ca = _client(db_session, a)
        assert ca.get(f"/recipes/{rid}").json()["title"] == "A Soup"
    finally:
        app.dependency_overrides.clear()


def test_recipe_routes_require_authentication(db_session):
    try:
        assert db_client(db_session).get("/recipes").status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_ingredients_are_private_per_user(db_session):
    a, b = _two_users(db_session)
    try:
        ca = _client(db_session, a)
        ing = ca.post(
            "/ingredients",
            json={"name": "Tomato", "unit": "g", "season_months": []},
        ).json()
        assert [i["name"] for i in ca.get("/ingredients").json()] == ["Tomato"]

        cb = _client(db_session, b)
        assert cb.get("/ingredients").json() == []
        # Same name is allowed for a different user (per-user uniqueness).
        assert cb.post(
            "/ingredients",
            json={"name": "Tomato", "unit": "g", "season_months": []},
        ).status_code == 201
        # B cannot reach A's ingredient.
        assert cb.delete(f"/ingredients/{ing['id']}").status_code == 404
        assert cb.get(f"/ingredients/{ing['id']}/recipes").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_tags_are_private_per_user(db_session):
    a, b = _two_users(db_session)
    try:
        ca = _client(db_session, a)
        ca.post("/recipes", json=_recipe_payload("Tagged", tags=["dinner"]))
        assert any(t["name"] == "dinner" for t in ca.get("/tags").json())

        cb = _client(db_session, b)
        assert all(t["name"] != "dinner" for t in cb.get("/tags").json())
    finally:
        app.dependency_overrides.clear()


def test_feedback_is_scoped_to_owner(db_session):
    from datetime import date

    a, b = _two_users(db_session)
    try:
        ca = _client(db_session, a)
        ca.post("/recipes", json=_recipe_payload("A Only"))

        # B cannot record feedback on a recipe it does not own.
        cb = _client(db_session, b)
        resp = cb.post(
            "/feedback/accept",
            json={"title": "A Only", "consumed_date": date(2024, 1, 1).isoformat()},
        )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
