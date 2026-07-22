from datetime import date

import crud


def test_swap_endpoint_exchanges_meals(db_session, user, auth_client):
    a = crud.create_recipe(
        db_session, user_id=user.id, title="A", servings_default=1, course="main"
    )
    b = crud.create_recipe(
        db_session, user_id=user.id, title="B", servings_default=1, course="main"
    )
    crud.set_meal_plan(
        db_session,
        {"2024-01-01": [a.id], "2024-01-02": [b.id]},
        user.id,
    )

    resp = auth_client.post(
        "/meal-plans/swap",
        json={
            "a": {"plan_date": "2024-01-01", "meal_number": 1},
            "b": {"plan_date": "2024-01-02", "meal_number": 1},
        },
    )
    assert resp.status_code == 200

    plan = auth_client.get(
        "/meal-plans",
        params={"start_date": "2024-01-01", "end_date": "2024-01-02"},
    ).json()
    assert plan["2024-01-01"][0]["recipe"] == "B"
    assert plan["2024-01-02"][0]["recipe"] == "A"


def test_swap_endpoint_missing_slot_returns_404(db_session, user, auth_client):
    a = crud.create_recipe(
        db_session, user_id=user.id, title="A", servings_default=1, course="main"
    )
    crud.set_meal_plan(db_session, {"2024-01-01": [a.id]}, user.id)

    resp = auth_client.post(
        "/meal-plans/swap",
        json={
            "a": {"plan_date": "2024-01-01", "meal_number": 1},
            "b": {"plan_date": "2024-01-02", "meal_number": 1},
        },
    )
    assert resp.status_code == 404
