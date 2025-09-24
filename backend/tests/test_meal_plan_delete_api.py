import os
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

import crud
from main import app, get_db
from models import MealPlan


def override_get_db(session):
    def _override():
        try:
            yield session
        finally:
            pass

    return _override


def test_delete_meal_plans_range(db_session):
    recipe = crud.create_recipe(db_session, title="Recipe", servings_default=1, course="main")
    start = date(2024, 1, 1)
    plan_dates = [start + timedelta(days=offset) for offset in range(4)]
    crud.set_meal_plan(
        db_session,
        {plan_date.isoformat(): [recipe.id] for plan_date in plan_dates},
    )

    os.makedirs("data", exist_ok=True)
    app.dependency_overrides[get_db] = override_get_db(db_session)
    client = TestClient(app)

    response = client.request(
        "DELETE",
        "/meal-plans",
        json={
            "start_date": plan_dates[1].isoformat(),
            "end_date": plan_dates[2].isoformat(),
        },
    )

    assert response.status_code in {200, 204}
    if response.status_code == 200:
        assert response.json() == {"deleted": 2}

    remaining_dates = set(
        db_session.execute(select(MealPlan.plan_date)).scalars().all()
    )
    assert remaining_dates == {plan_dates[0], plan_dates[3]}

    app.dependency_overrides.clear()
