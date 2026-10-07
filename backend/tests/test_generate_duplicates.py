
from datetime import date, timedelta

import crud

# Generation only accepts ranges from today on (F3), so these run tomorrow.
DAY = (date.today() + timedelta(days=1)).isoformat()


def test_generate_endpoint_handles_duplicate_titles(db_session, user, auth_client):
    for _ in range(2):
        crud.create_recipe(db_session, user_id=user.id, title="Dup", course="main")

    response = auth_client.post(
        "/meal-plans/generate",
        json={"start": DAY, "end": DAY, "meals_per_day": 1},
    )
    assert response.status_code == 200
    data = response.json()
    assert DAY in data
    assert isinstance(data[DAY][0]["id"], int)
    assert isinstance(data[DAY][0]["title"], str)
