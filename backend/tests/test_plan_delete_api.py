from datetime import date, timedelta


import crud
from mealplanner import planner
from models import Meal, MealPlan


def test_delete_meal_plans_removes_rows_and_cache(db_session, user, auth_client):
    main = crud.create_recipe(db_session, user_id=user.id, title="Main", servings_default=1, course="main")
    alt = crud.create_recipe(db_session, user_id=user.id, title="Alt", servings_default=1, course="main")
    side = crud.create_recipe(db_session, user_id=user.id, title="Side", servings_default=1, course="side")

    start = date(2024, 1, 1)
    second = start + timedelta(days=1)

    crud.set_meal_plan(
        db_session,
        {
            start.isoformat(): [{"main_id": main.id, "side_ids": [side.id]}],
            second.isoformat(): [{"main_id": alt.id}],
        },
        user.id,
    )

    assert db_session.query(MealPlan).count() == 2

    client = auth_client

    resp = client.delete(
        "/meal-plans",
        params={"start_date": start.isoformat(), "end_date": second.isoformat()},
    )
    assert resp.status_code == 200
    assert resp.json() == {"deleted": 2}

    assert db_session.query(MealPlan).count() == 0
    assert db_session.query(Meal).count() == 0
    assert crud.get_plan(db_session, start_date=start, end_date=second, user_id=user.id) == {}

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


def test_delete_meal_plans_legacy_route(db_session, user, auth_client):
    main = crud.create_recipe(db_session, user_id=user.id, title="Main", servings_default=1, course="main")

    start = date(2024, 1, 1)

    crud.set_meal_plan(
        db_session,
        {start.isoformat(): [{"main_id": main.id}]},
        user.id,
    )

    client = auth_client

    resp = client.delete(
        "/plan",
        params={"start_date": start.isoformat(), "end_date": start.isoformat()},
    )
    assert resp.status_code == 200
    assert resp.json() == {"deleted": 1}
