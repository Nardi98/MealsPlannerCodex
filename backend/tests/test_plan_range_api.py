from datetime import date, timedelta

import crud


def test_get_plan_range(db_session, user, auth_client):
    r1 = crud.create_recipe(db_session, user_id=user.id, title="A", servings_default=1, course="main")
    r2 = crud.create_recipe(db_session, user_id=user.id, title="B", servings_default=1, course="main")
    start = date(2024, 1, 1)
    second = start + timedelta(days=1)
    crud.set_meal_plan(
        db_session,
        {
            start.isoformat(): [r1.id],
            second.isoformat(): [r2.id],
        },
        user.id,
    )

    client = auth_client

    resp = client.get(
        "/plan",
        params={"start_date": start.isoformat(), "end_date": second.isoformat()},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        start.isoformat(): [
            {
                "recipe": "A",
                "side_recipes": [],
                "accepted": False,
                "leftover": False,
            }
        ],
        second.isoformat(): [
            {
                "recipe": "B",
                "side_recipes": [],
                "accepted": False,
                "leftover": False,
            }
        ],
    }
