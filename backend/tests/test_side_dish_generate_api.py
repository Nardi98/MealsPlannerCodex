from datetime import date, timedelta

import crud
from models import Tag, MealPlan, Meal, MealSide

DAY = date(2025, 3, 10)


def _plan_a_main(db_session, user):
    main = crud.create_recipe(db_session, title="Main", course="main", user_id=user.id)
    crud.set_meal_plan(db_session, {DAY.isoformat(): [main.id]}, user.id)


def _generate(client, **extra):
    return client.post(
        "/side-dishes/generate",
        json={"plan_date": DAY.isoformat(), "meal_number": 1, "epsilon": 0.0, **extra},
    )


def test_generate_side_dish_endpoint_returns_side(db_session, user, auth_client):
    _plan_a_main(db_session, user)
    for i in range(3):
        crud.create_recipe(db_session, title=f"Side {i}", course="side", user_id=user.id)

    resp = _generate(auth_client)

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"].startswith("Side")
    assert isinstance(data["id"], int)


def test_generate_side_dish_requires_the_slot(auth_client):
    assert auth_client.post("/side-dishes/generate", json={}).status_code == 422


def test_generate_side_dish_respects_recency_weight_and_avoid_tags(
    db_session, user, auth_client
):
    _plan_a_main(db_session, user)
    good = crud.create_recipe(
        db_session, title="Good", course="side", score=1.0, bulk_prep=True, user_id=user.id
    )
    recent = crud.create_recipe(
        db_session, title="Recent", course="side", score=2.0, bulk_prep=True, user_id=user.id
    )
    for days_back, side in ((60, good), (1, recent)):
        day = DAY - timedelta(days=days_back)
        db_session.add_all([
            MealPlan(user_id=user.id, plan_date=day),
            Meal(user_id=user.id, plan_date=day, meal_number=1),
            MealSide(user_id=user.id, plan_date=day, meal_number=1, position=1,
                     side_recipe_id=side.id),
        ])
    crud.create_recipe(
        db_session, title="Avoid", course="side", score=5.0, user_id=user.id,
        tags=[Tag(name="avoid", user_id=user.id)],
    )
    db_session.commit()

    resp = _generate(auth_client, avoid_tags=["avoid"], recency_weight=0.0)
    assert resp.json()["title"] == "Recent"

    resp2 = _generate(auth_client, avoid_tags=["avoid"], recency_weight=2.0)
    assert resp2.json()["title"] == "Good"


def test_generate_side_dish_honours_excluded_ids(db_session, user, auth_client):
    _plan_a_main(db_session, user)
    crud.create_recipe(db_session, title="Keep", course="side", score=1.0, user_id=user.id)
    skip = crud.create_recipe(
        db_session, title="Skip", course="side", score=10.0, user_id=user.id
    )

    resp = _generate(auth_client, exclude_ids=[skip.id])

    assert resp.status_code == 200
    assert resp.json()["title"] == "Keep"
