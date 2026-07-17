
import crud


def test_generate_endpoint_returns_plan(db_session, user, auth_client):
    for i in range(3):
        crud.create_recipe(db_session, user_id=user.id, title=f"Meal {i}", servings_default=1, course="main")

    response = auth_client.post(
        "/meal-plans/generate",
        json={"start": "2024-01-01", "end": "2024-01-01", "meals_per_day": 1},
    )
    assert response.status_code == 200
    data = response.json()
    assert "2024-01-01" in data
    assert isinstance(data["2024-01-01"][0]["id"], int)
    assert data["2024-01-01"][0]["title"].startswith("Meal")
    assert data["2024-01-01"][0]["leftover"] is False
