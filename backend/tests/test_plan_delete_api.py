import os
from datetime import date, timedelta

from fastapi.testclient import TestClient

import crud
from main import app, get_db
from mealplanner import planner
from mealplanner.models import Meal, MealPlan


def override_get_db(session):
    def _override():
        try:
            yield session
        finally:
            pass

    return _override


def test_delete_meal_plans_removes_rows_and_cache(db_session):
    main = crud.create_recipe(db_session, title="Main", servings_default=1, course="main")
    alt = crud.create_recipe(db_session, title="Alt", servings_default=1, course="main")
    side = crud.create_recipe(db_session, title="Side", servings_default=1, course="side")

    start = date(2024, 1, 1)
    second = start + timedelta(days=1)

    crud.set_meal_plan(
        db_session,
        {
            start.isoformat(): [{"main_id": main.id, "side_ids": [side.id]}],
            second.isoformat(): [{"main_id": alt.id}],
        },
    )

    crud.save_plan(
        {
            start.isoformat(): [
                {
                    "recipe": "Main",
                    "side_recipes": ["Side"],
                    "accepted": False,
                    "leftover": False,
                }
            ],
            second.isoformat(): [
                {
                    "recipe": "Alt",
                    "side_recipes": [],
                    "accepted": False,
                    "leftover": False,
                }
            ],
        }
    )

    assert db_session.query(MealPlan).count() == 2

    os.makedirs("data", exist_ok=True)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

    try:
        resp = client.delete(
            "/meal-plans",
            params={"start_date": start.isoformat(), "end_date": second.isoformat()},
        )
        assert resp.status_code == 200
        assert resp.json() == {"deleted": 2}

        assert db_session.query(MealPlan).count() == 0
        assert db_session.query(Meal).count() == 0
        assert crud.get_plan() == {}

        generated = planner.generate_plan(
            db_session,
            start=start,
            days=1,
            meals_per_day=1,
            keep_days=7,
            bulk_leftovers=False,
            epsilon=0.0,
            avoid_tags=[],
            reduce_tags=[],
            seasonality_weight=1.0,
            recency_weight=1.0,
            tag_penalty_weight=1.0,
            bulk_bonus_weight=1.0,
        )
        assert start.isoformat() in generated
        assert generated[start.isoformat()]
    finally:
        app.dependency_overrides.clear()


def test_delete_meal_plans_legacy_route(db_session):
    main = crud.create_recipe(db_session, title="Main", servings_default=1, course="main")

    start = date(2024, 1, 1)

    crud.set_meal_plan(
        db_session,
        {start.isoformat(): [{"main_id": main.id}]},
    )

    crud.save_plan(
        {
            start.isoformat(): [
                {
                    "recipe": "Main",
                    "side_recipes": [],
                    "accepted": False,
                    "leftover": False,
                }
            ]
        }
    )

    os.makedirs("data", exist_ok=True)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

    try:
        resp = client.delete(
            "/plan",
            params={"start_date": start.isoformat(), "end_date": start.isoformat()},
        )
        assert resp.status_code == 200
        assert resp.json() == {"deleted": 1}
    finally:
        app.dependency_overrides.clear()
