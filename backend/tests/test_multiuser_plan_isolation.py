"""Step 3c tests: meal plans / settings / export are private per user.

Mirrors ``test_multiuser_isolation`` (Step 3b) but covers the planner side of
the app: plans, meals, side dishes, per-user plan settings, and scoped
export/import/clear.
"""

from datetime import date

import crud
from conftest import client_as as _client, db_client
from main import app
from mealplanner import planner
from mealplanner.config import DEFAULT_PLAN_SETTINGS


PLAN_DAY = date(2024, 3, 4)


def _two_users(session):
    a = crud.create_user(session, email="pa@x.com", hashed_password="h")
    b = crud.create_user(session, email="pb@x.com", hashed_password="h")
    return a, b


def _plan_payload(main_id, day=PLAN_DAY):
    return {
        "plan_date": day.isoformat(),
        "plan": {day.isoformat(): [{"main_id": main_id}]},
    }


def _recipe(session, user, title, course="main"):
    return crud.create_recipe(
        session,
        title=title,
        servings_default=1,
        course=course,
        user_id=user.id,
    )


def test_same_date_plans_coexist_per_user(db_session):
    a, b = _two_users(db_session)
    ra = _recipe(db_session, a, "A Main")
    rb = _recipe(db_session, b, "B Main")

    crud.set_meal_plan(db_session, {PLAN_DAY.isoformat(): [ra.id]}, a.id)
    crud.set_meal_plan(db_session, {PLAN_DAY.isoformat(): [rb.id]}, b.id)

    plan_a = crud.get_plan(db_session, PLAN_DAY, user_id=a.id)
    plan_b = crud.get_plan(db_session, PLAN_DAY, user_id=b.id)
    assert [m["recipe"] for m in plan_a[PLAN_DAY.isoformat()]] == ["A Main"]
    assert [m["recipe"] for m in plan_b[PLAN_DAY.isoformat()]] == ["B Main"]


def test_user_b_sees_empty_planner_and_can_build_own(db_session):
    """The Step 3c browser test, driven through the real routes."""
    a, b = _two_users(db_session)
    ra = _recipe(db_session, a, "A Main")
    rb = _recipe(db_session, b, "B Main")

    ca = _client(db_session, a)
    assert ca.post("/meal-plans", json=_plan_payload(ra.id)).status_code == 200

    # B's planner is empty on the same date...
    cb = _client(db_session, b)
    assert cb.get("/meal-plans", params={"plan_date": PLAN_DAY.isoformat()}).json() == {}
    # ...and B can build an independent plan for that same date without a 409.
    resp = cb.post("/meal-plans", json=_plan_payload(rb.id))
    assert resp.status_code == 200
    assert [m["recipe"] for m in resp.json()[PLAN_DAY.isoformat()]] == ["B Main"]

    # A's plan is untouched.
    ca = _client(db_session, a)
    fetched = ca.get("/meal-plans", params={"plan_date": PLAN_DAY.isoformat()}).json()
    assert [m["recipe"] for m in fetched[PLAN_DAY.isoformat()]] == ["A Main"]
    app.dependency_overrides.clear()


def test_meal_mutations_do_not_cross_users(db_session):
    a, b = _two_users(db_session)
    ra = _recipe(db_session, a, "A Main")
    crud.set_meal_plan(db_session, {PLAN_DAY.isoformat(): [ra.id]}, a.id)

    # B cannot accept, side-dish, or delete A's meal.
    assert crud.mark_meal_accepted(db_session, PLAN_DAY, 1, True, b.id) is None
    assert crud.add_meal_side(db_session, PLAN_DAY, 1, ra.id, b.id) is None
    assert crud.delete_meal_plans(db_session, PLAN_DAY, PLAN_DAY, b.id) == 0

    # A still can, and its plan survives B's attempts.
    assert crud.mark_meal_accepted(db_session, PLAN_DAY, 1, True, a.id) is not None
    assert crud.get_plan(db_session, PLAN_DAY, user_id=a.id) != {}


def test_planner_only_draws_on_the_callers_recipes(db_session):
    a, b = _two_users(db_session)
    _recipe(db_session, a, "A Only")
    _recipe(db_session, b, "B Only")

    schedule = planner.generate_plan(
        db_session, start=PLAN_DAY, days=1, meals_per_day=1, user_id=a.id
    )
    assert schedule == {PLAN_DAY.isoformat(): ["A Only"]}


def test_planned_titles_and_recipe_titles_are_scoped(db_session):
    a, b = _two_users(db_session)
    ra = _recipe(db_session, a, "A Main")
    _recipe(db_session, b, "B Main")
    crud.set_meal_plan(db_session, {PLAN_DAY.isoformat(): [ra.id]}, a.id)

    assert crud.list_planned_titles(db_session, a.id) == {"A Main"}
    assert crud.list_planned_titles(db_session, b.id) == set()
    assert set(crud.list_recipe_titles(db_session, user_id=b.id)) == {"B Main"}


def test_plan_settings_are_per_user(db_session):
    a, b = _two_users(db_session)

    # Both start on the shared defaults.
    assert crud.get_plan_settings(db_session, a.id) == DEFAULT_PLAN_SETTINGS

    merged = crud.set_plan_settings(
        db_session, a.id, {"LEFTOVER_REPEAT_DEFAULT": 5}
    )
    assert merged["LEFTOVER_REPEAT_DEFAULT"] == 5
    # Other keys still fall through to the defaults.
    assert (
        merged["LEFTOVER_SPACING_GAP"]
        == DEFAULT_PLAN_SETTINGS["LEFTOVER_SPACING_GAP"]
    )
    # A's override is persisted and does not leak to B.
    assert crud.get_plan_settings(db_session, a.id)["LEFTOVER_REPEAT_DEFAULT"] == 5
    assert crud.get_plan_settings(db_session, b.id) == DEFAULT_PLAN_SETTINGS


def test_set_plan_settings_ignores_unknown_keys(db_session):
    a, _ = _two_users(db_session)
    merged = crud.set_plan_settings(db_session, a.id, {"NOT_A_SETTING": 1})
    assert "NOT_A_SETTING" not in merged


def test_export_returns_only_the_callers_data(db_session):
    import json

    a, b = _two_users(db_session)
    ra = _recipe(db_session, a, "A Main")
    _recipe(db_session, b, "B Main")
    crud.set_meal_plan(db_session, {PLAN_DAY.isoformat(): [ra.id]}, a.id)

    data = json.loads(crud.export_data(db_session, a.id))
    assert [r["title"] for r in data["recipes"]] == ["A Main"]
    assert [p["plan_date"] for p in data["meal_plans"]] == [PLAN_DAY.isoformat()]


def test_clear_data_only_wipes_the_callers_rows(db_session):
    a, b = _two_users(db_session)
    ra = _recipe(db_session, a, "A Main")
    _recipe(db_session, b, "B Main")
    crud.set_meal_plan(db_session, {PLAN_DAY.isoformat(): [ra.id]}, a.id)

    crud.clear_data(db_session, a.id)

    assert crud.list_recipe_titles(db_session, user_id=a.id) == []
    assert crud.get_plan(db_session, PLAN_DAY, user_id=a.id) == {}
    # B is untouched.
    assert set(crud.list_recipe_titles(db_session, user_id=b.id)) == {"B Main"}


def test_import_stamps_ownership_on_the_caller(db_session):
    import io
    import json

    a, b = _two_users(db_session)
    payload = {
        "recipes": [
            {
                "title": "Imported",
                "servings_default": 1,
                "course": "main",
                "ingredients": [],
                "tags": [],
            }
        ],
        "tags": [],
        "meal_plans": [],
    }
    crud.import_data(
        io.StringIO(json.dumps(payload)), db_session, mode="merge", user_id=a.id
    )

    assert set(crud.list_recipe_titles(db_session, user_id=a.id)) == {"Imported"}
    assert crud.list_recipe_titles(db_session, user_id=b.id) == []


def test_registration_seeds_system_tags_for_the_new_user(db_session):
    """New accounts start with their own system tags but no recipes/plans."""
    try:
        client = db_client(db_session)
        resp = client.post(
            "/auth/register",
            json={"email": "fresh@x.com", "password": "pw123456"},
        )
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        tags = crud.get_or_create_tag(db_session, "pasta", new_id)
        assert tags.is_system is True
        assert tags.penalize_repetition is True
        # ...and the account is otherwise empty.
        assert crud.list_recipe_titles(db_session, user_id=new_id) == []
    finally:
        app.dependency_overrides.clear()


def test_registration_seeds_starter_ingredients_per_user(db_session):
    """Each new account gets its own copy of the starter ingredient library."""
    from sqlalchemy import func, select

    from models import Ingredient
    from mealplanner.seed import SYSTEM_INGREDIENTS

    def _ingredient_count(user_id):
        return db_session.execute(
            select(func.count())
            .select_from(Ingredient)
            .where(Ingredient.user_id == user_id)
        ).scalar_one()

    try:
        client = db_client(db_session)
        first = client.post(
            "/auth/register",
            json={"email": "starter-a@x.com", "password": "pw123456"},
        ).json()["id"]
        second = client.post(
            "/auth/register",
            json={"email": "starter-b@x.com", "password": "pw123456"},
        ).json()["id"]

        assert _ingredient_count(first) == len(SYSTEM_INGREDIENTS)
        assert _ingredient_count(second) == len(SYSTEM_INGREDIENTS)

        # A known ingredient exists for the new user, fully populated.
        potato = db_session.execute(
            select(Ingredient).where(
                Ingredient.name == "Potato", Ingredient.user_id == first
            )
        ).scalar_one()
        assert potato.categories and potato.season_months
    finally:
        app.dependency_overrides.clear()
