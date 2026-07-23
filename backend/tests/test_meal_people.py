"""Tests for the per-meal / per-user "number of people" servings scaling.

Recipes are authored for one serving; the shopping list scales each meal's
ingredients by a people count. That count is stored per user
(``User.default_people``, the global default) and per meal (``Meal.people``),
and is surfaced on the plan/meal routes so the shopping list can read and edit
it.
"""
from datetime import date

import crud
from tests.conftest import client_as


def _make_meal(db_session, user, make_recipe, people=None):
    recipe = make_recipe("Pasta")
    day = date(2026, 8, 3)
    crud.set_meal_plan(db_session, {day.isoformat(): [recipe.id]}, user.id)
    if people is not None:
        crud.set_meal_people(db_session, day, 1, people, user.id)
    return recipe, day


def test_new_user_defaults_to_two_people(db_session):
    user = crud.create_user(
        db_session, email="p1@test.local", hashed_password="x"
    )
    assert user.default_people == 2


def test_set_meal_plan_initialises_people_from_user_default(
    db_session, user, make_recipe
):
    user.default_people = 5
    db_session.flush()
    recipe = make_recipe("Pasta")
    day = date(2026, 8, 3)
    crud.set_meal_plan(db_session, {day.isoformat(): [recipe.id]}, user.id)
    meal = crud._get_meal(db_session, day, 1, user.id)
    assert meal.people == 5


def test_set_meal_people_updates_single_meal(db_session, user, make_recipe):
    recipe, day = _make_meal(db_session, user, make_recipe)
    crud.set_meal_people(db_session, day, 1, 7, user.id)
    meal = crud._get_meal(db_session, day, 1, user.id)
    assert meal.people == 7


def test_meal_item_exposes_meal_number_and_people(
    db_session, user, make_recipe
):
    recipe, day = _make_meal(db_session, user, make_recipe, people=4)
    meal = crud._get_meal(db_session, day, 1, user.id)
    item = crud.meal_item(meal)
    assert item["meal_number"] == 1
    assert item["people"] == 4


def test_set_default_people_updates_user_and_meals_in_range_only(
    db_session, user, make_recipe
):
    recipe = make_recipe("Pasta")
    in_range = date(2026, 8, 5)
    out_of_range = date(2026, 8, 20)
    crud.set_meal_plan(
        db_session,
        {
            in_range.isoformat(): [recipe.id],
            out_of_range.isoformat(): [recipe.id],
        },
        user.id,
    )

    crud.set_default_people(
        db_session, 9, date(2026, 8, 1), date(2026, 8, 7), user.id
    )

    assert crud.get_user(db_session, user.id).default_people == 9
    assert crud._get_meal(db_session, in_range, 1, user.id).people == 9
    # A meal outside the shopping-list range keeps its previous value.
    assert crud._get_meal(db_session, out_of_range, 1, user.id).people != 9


def test_get_plan_route_returns_people(db_session, user, make_recipe):
    recipe, day = _make_meal(db_session, user, make_recipe, people=6)
    client = client_as(db_session, user)
    try:
        resp = client.get(
            "/meal-plans",
            params={"start_date": "2026-08-01", "end_date": "2026-08-07"},
        )
    finally:
        from main import app

        app.dependency_overrides.clear()
    assert resp.status_code == 200
    meals = resp.json()[day.isoformat()]
    assert meals[0]["people"] == 6
    assert meals[0]["meal_number"] == 1


def test_people_endpoint_updates_meal(db_session, user, make_recipe):
    recipe, day = _make_meal(db_session, user, make_recipe)
    client = client_as(db_session, user)
    try:
        resp = client.post(
            "/meal-plans/people",
            json={
                "plan_date": day.isoformat(),
                "meal_number": 1,
                "people": 8,
            },
        )
    finally:
        from main import app

        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert resp.json()["people"] == 8
    assert crud._get_meal(db_session, day, 1, user.id).people == 8


def test_default_people_endpoint_applies_to_range(
    db_session, user, make_recipe
):
    recipe, day = _make_meal(db_session, user, make_recipe)
    client = client_as(db_session, user)
    try:
        resp = client.put(
            "/auth/me/default-people",
            json={
                "people": 10,
                "start_date": "2026-08-01",
                "end_date": "2026-08-07",
            },
        )
    finally:
        from main import app

        app.dependency_overrides.clear()
    assert resp.status_code == 200
    assert crud.get_user(db_session, user.id).default_people == 10
    assert crud._get_meal(db_session, day, 1, user.id).people == 10


def test_export_import_round_trips_people(db_session, user, make_recipe):
    import io

    recipe, day = _make_meal(db_session, user, make_recipe, people=3)
    raw = crud.export_data(db_session, user.id)
    import json

    payload = json.loads(raw)
    meal = payload["meal_plans"][0]["meals"][0]
    assert meal["people"] == 3

    other = crud.create_user(
        db_session, email="importer@test.local", hashed_password="x"
    )
    crud.import_data(
        io.StringIO(raw), session=db_session, mode="merge", user_id=other.id
    )
    imported = crud._get_meal(db_session, day, 1, other.id)
    assert imported.people == 3
