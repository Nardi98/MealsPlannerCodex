"""Two accounts sharing one database never see each other's rows.

Two layers, kept in one module because they defend the same invariant:

- *Schema* (step 3a): ownership columns, per-user uniqueness, and the
  ``meal_plans`` PK -- proving two users can independently hold same-named
  tags/ingredients and same-date plans, since uniqueness is scoped per user
  rather than globally.
- *Routes* (step 3b): recipes / ingredients / tags are private per user. Each
  request runs through the real FastAPI routes with ``get_db`` pinned to the
  test session and ``get_current_user`` overridden to a chosen user, so
  switching the override simulates a different logged-in account against
  shared storage.

Plan-scoped isolation (settings, import/export ownership, registration
seeding) lives in ``test_multiuser_plan_isolation.py``.
"""

from datetime import date

import pytest

import crud
from conftest import client_as as _client, db_client
from main import app
from models import Ingredient, Meal, MealPlan, Tag


# ---------------------------------------------------------------------------
# Schema layer
# ---------------------------------------------------------------------------
def test_two_users_same_named_tag(db_session, user, other_user):
    a, b = user, other_user
    db_session.add_all([
        Tag(name="pasta", user_id=a.id),
        Tag(name="pasta", user_id=b.id),
    ])
    db_session.commit()
    assert db_session.query(Tag).filter_by(name="pasta").count() == 2


def test_same_user_duplicate_tag_rejected(db_session, user):
    a = user
    db_session.add_all([
        Tag(name="pasta", user_id=a.id),
        Tag(name="pasta", user_id=a.id),
    ])
    with pytest.raises(Exception):
        db_session.commit()
    db_session.rollback()


def test_two_users_same_named_ingredient(db_session, user, other_user):
    a, b = user, other_user
    db_session.add_all([
        Ingredient(name="Tomato", user_id=a.id),
        Ingredient(name="Tomato", user_id=b.id),
    ])
    db_session.commit()
    assert db_session.query(Ingredient).filter_by(name="Tomato").count() == 2


def test_same_user_duplicate_ingredient_rejected(db_session, user):
    a = user
    db_session.add_all([
        Ingredient(name="Tomato", user_id=a.id),
        Ingredient(name="Tomato", user_id=a.id),
    ])
    with pytest.raises(Exception):
        db_session.commit()
    db_session.rollback()


def test_two_users_same_date_meal_plan(db_session, user, other_user):
    a, b = user, other_user
    day = date(2026, 1, 1)
    db_session.add_all([
        MealPlan(plan_date=day, user_id=a.id),
        MealPlan(plan_date=day, user_id=b.id),
    ])
    db_session.commit()
    assert db_session.query(MealPlan).filter_by(plan_date=day).count() == 2


def test_meals_scoped_by_user(db_session, user, other_user):
    a, b = user, other_user
    day = date(2026, 1, 1)
    db_session.add_all([
        MealPlan(plan_date=day, user_id=a.id),
        MealPlan(plan_date=day, user_id=b.id),
    ])
    db_session.flush()
    db_session.add_all([
        Meal(user_id=a.id, plan_date=day, meal_number=1),
        Meal(user_id=b.id, plan_date=day, meal_number=1),
    ])
    db_session.commit()
    assert db_session.query(Meal).filter_by(plan_date=day, meal_number=1).count() == 2


# ---------------------------------------------------------------------------
# Route layer
# ---------------------------------------------------------------------------
def _recipe_payload(title, **over):
    payload = {
        "title": title,
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
