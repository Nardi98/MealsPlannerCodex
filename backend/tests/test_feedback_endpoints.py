from datetime import date

from conftest import client_as
from main import app
import crud


def test_feedback_endpoints_return_unique_replacement(db_session):
    user = crud.create_user(
        db_session, email="feedback@test.local", hashed_password="x"
    )
    client = client_as(db_session, user)
    uid = user.id
    a = crud.create_recipe(db_session, title="A", servings_default=1, course="main", score=0, user_id=uid)
    crud.create_recipe(db_session, title="B", servings_default=1, course="main", score=0, user_id=uid)
    c = crud.create_recipe(db_session, title="C", servings_default=1, course="main", score=0, user_id=uid)
    crud.set_meal_plan(
        db_session,
        {
            "2024-01-01": [
                {"main_id": a.id, "leftover": False},
                {"main_id": c.id, "leftover": True},
            ]
        },
        uid,
    )

    consumed = date(2024, 1, 1)
    resp = client.post(
        "/feedback/accept", json={"title": "A", "consumed_date": consumed.isoformat()}
    )
    assert resp.status_code == 200
    db_session.refresh(a)
    assert a.score == 1
    assert a.date_last_consumed == consumed

    resp = client.post(
        "/feedback/reject", json={"title": "A", "consumed_date": consumed.isoformat()}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["replacement"] == "B"

    app.dependency_overrides.clear()


def test_reject_replacement_limited_to_main_courses(db_session):
    user = crud.create_user(
        db_session, email="feedback@test.local", hashed_password="x"
    )
    client = client_as(db_session, user)
    uid = user.id
    a = crud.create_recipe(db_session, title="A", servings_default=1, course="main", score=0, user_id=uid)
    crud.create_recipe(db_session, title="B", servings_default=1, course="main", score=0, user_id=uid)
    crud.create_recipe(
        db_session, title="C", servings_default=1, course="dessert", score=0, user_id=uid
    )
    crud.set_meal_plan(
        db_session,
        {"2024-01-01": [{"main_id": a.id, "leftover": False}]},
        uid,
    )

    consumed = date(2024, 1, 1)
    resp = client.post(
        "/feedback/reject", json={"title": "A", "consumed_date": consumed.isoformat()}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["replacement"] == "B"
    assert data["replacement"] != "C"

    app.dependency_overrides.clear()
