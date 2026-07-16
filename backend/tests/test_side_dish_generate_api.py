from datetime import date, timedelta

import crud
from models import Tag, MealPlan, Meal, MealSide


def test_generate_side_dish_endpoint_returns_side(db_session, user, auth_client):
    for i in range(3):
        crud.create_recipe(db_session, title=f"Side {i}", servings_default=1, course="side", user_id=user.id)
    client = auth_client
    resp = client.post("/side-dishes/generate", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"].startswith("Side")
    assert isinstance(data["id"], int)


def test_generate_side_dish_respects_tag_weight(db_session, user, auth_client):
    today = date.today()
    good = crud.create_recipe(
        db_session,
        title="Good",
        servings_default=1,
        course="side",
        score=1.0,
        bulk_prep=True,
        user_id=user.id,
    )
    recent = crud.create_recipe(
        db_session,
        title="Recent",
        servings_default=1,
        course="side",
        score=2.0,
        bulk_prep=True,
        user_id=user.id,
    )
    db_session.commit()
    db_session.add_all(
        [
            MealPlan(user_id=user.id, plan_date=today - timedelta(days=60)),
            Meal(user_id=user.id, plan_date=today - timedelta(days=60), meal_number=1),
            MealSide(
                user_id=user.id,
                plan_date=today - timedelta(days=60),
                meal_number=1,
                position=1,
                side_recipe_id=good.id,
            ),
            MealPlan(user_id=user.id, plan_date=today - timedelta(days=1)),
            Meal(user_id=user.id, plan_date=today - timedelta(days=1), meal_number=1),
            MealSide(
                user_id=user.id,
                plan_date=today - timedelta(days=1),
                meal_number=1,
                position=1,
                side_recipe_id=recent.id,
            ),
        ]
    )
    db_session.commit()
    crud.create_recipe(
        db_session,
        title="Avoid",
        servings_default=1,
        course="side",
        score=5.0,
        tags=[Tag(name="avoid")],
    )
    client = auth_client

    resp = client.post(
        "/side-dishes/generate",
        json={"avoid_tags": ["avoid"], "recency_weight": 0.0},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Recent"

    resp2 = client.post(
        "/side-dishes/generate",
        json={"avoid_tags": ["avoid"], "recency_weight": 2.0},
    )
    assert resp2.status_code == 200
    assert resp2.json()["title"] == "Good"


def test_generate_side_dish_avoids_titles(db_session, user, auth_client):
    crud.create_recipe(
        db_session,
        title="Keep",
        servings_default=1,
        course="side",
        score=1.0,
        user_id=user.id,
    )
    crud.create_recipe(
        db_session,
        title="Skip",
        servings_default=1,
        course="side",
        score=10.0,
        user_id=user.id,
    )
    resp = auth_client.post(
        "/side-dishes/generate", json={"avoid_titles": ["Skip"]}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Keep"

