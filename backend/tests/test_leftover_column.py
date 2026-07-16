"""Leftover state must come from the Meal.leftover column, never a title suffix."""



import crud


def test_recipe_named_leftover_is_not_treated_as_leftover(db_session, user, auth_client):
    """A recipe literally titled '... (leftover)' must not be flagged as a leftover."""
    crud.create_recipe(
        db_session, title="Soup (leftover)", servings_default=1, course="main",
        user_id=user.id,
    )
    response = auth_client.post(
        "/meal-plans/generate",
        json={"start": "2024-01-01", "end": "2024-01-01", "meals_per_day": 1},
    )

    assert response.status_code == 200
    item = response.json()["2024-01-01"][0]
    assert item["title"] == "Soup (leftover)"
    assert item["leftover"] is False


def test_scheduled_leftover_slot_has_clean_title_and_flag(db_session, user, auth_client):
    """A bulk-prep leftover slot reports leftover=True with the clean base title."""
    crud.create_recipe(
        db_session, title="Bulk", servings_default=1, course="main", bulk_prep=True,
        user_id=user.id,
    )
    response = auth_client.post(
        "/meal-plans/generate",
        json={"start": "2024-01-01", "end": "2024-01-03", "meals_per_day": 1},
    )

    assert response.status_code == 200
    data = response.json()
    leftover_items = [
        item for day in data.values() for item in day if item["leftover"]
    ]
    assert leftover_items, "expected at least one scheduled leftover slot"
    for item in leftover_items:
        assert item["title"] == "Bulk"
