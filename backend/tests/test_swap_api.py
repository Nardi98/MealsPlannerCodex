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


def _pos(day, number=1):
    return {"plan_date": day, "meal_number": number}


def test_swap_endpoint_sequential_swaps_are_one_to_one(db_session, user, auth_client):
    ids = {}
    for title in ("A", "B", "C"):
        ids[title] = crud.create_recipe(
            db_session, user_id=user.id, title=title, servings_default=1, course="main"
        ).id
    crud.set_meal_plan(
        db_session,
        {"2024-01-01": [ids["A"]], "2024-01-02": [ids["B"]], "2024-01-03": [ids["C"]]},
        user.id,
    )

    def recipes():
        plan = auth_client.get(
            "/meal-plans",
            params={"start_date": "2024-01-01", "end_date": "2024-01-03"},
        ).json()
        return {d: plan[d][0]["recipe"] for d in plan}

    assert auth_client.post(
        "/meal-plans/swap", json={"a": _pos("2024-01-01"), "b": _pos("2024-01-03")}
    ).status_code == 200
    assert recipes() == {"2024-01-01": "C", "2024-01-02": "B", "2024-01-03": "A"}

    assert auth_client.post(
        "/meal-plans/swap", json={"a": _pos("2024-01-01"), "b": _pos("2024-01-02")}
    ).status_code == 200
    # Only the two swapped slots change; the untouched slot keeps its recipe.
    assert recipes() == {"2024-01-01": "B", "2024-01-02": "C", "2024-01-03": "A"}


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
