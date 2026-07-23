from datetime import date

import crud


def test_toggle_meal_acceptance(db_session, user, auth_client):
    r = crud.create_recipe(db_session, user_id=user.id, title="A", servings_default=1, course="main")
    plan_date = date(2024, 1, 1)
    crud.set_meal_plan(db_session, {plan_date.isoformat(): [r.id]}, user.id)
    client = auth_client

    resp = client.post(
        "/meal-plans/accept",
        json={"plan_date": "2024-01-01", "meal_number": 1, "accepted": True},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "recipe": "A",
        "side_recipes": [],
        "accepted": True,
        "leftover": False,
        "meal_number": 1,
        "people": 2,
    }

    resp2 = client.get("/plan", params={"plan_date": "2024-01-01"})
    assert resp2.status_code == 200
    assert resp2.json() == {
        "2024-01-01": [
            {
                "recipe": "A",
                "side_recipes": [],
                "accepted": True,
                "leftover": False,
                "meal_number": 1,
                "people": 2,
            }
        ]
    }
