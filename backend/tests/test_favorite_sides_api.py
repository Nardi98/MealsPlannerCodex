"""The /recipes surface for curating a main's favorite sides."""
import crud


def _create(client, title, course, favorite_side_ids=None):
    payload = {
        "title": title,
        "servings_default": 2,
        "course": course,
    }
    if favorite_side_ids is not None:
        payload["favorite_side_ids"] = favorite_side_ids
    return client.post("/recipes", json=payload)


def _make_side(client, title="Mashed Potatoes"):
    res = _create(client, title, "side")
    assert res.status_code == 201
    return res.json()["id"]


def test_create_main_with_favorite_sides_round_trips(api_client):
    side_id = _make_side(api_client)

    res = _create(api_client, "Roast Chicken", "main", [side_id])

    assert res.status_code == 201
    assert res.json()["favorite_side_ids"] == [side_id]

    fetched = api_client.get(f"/recipes/{res.json()['id']}")
    assert fetched.json()["favorite_side_ids"] == [side_id]


def test_favorite_sides_default_to_empty(api_client):
    res = _create(api_client, "Plain Steak", "main")

    assert res.status_code == 201
    assert res.json()["favorite_side_ids"] == []


def test_update_replaces_the_favorite_sides(api_client):
    first = _make_side(api_client, "Mashed Potatoes")
    second = _make_side(api_client, "Steamed Broccoli")
    created = _create(api_client, "Roast Chicken", "main", [first]).json()

    res = api_client.put(
        f"/recipes/{created['id']}",
        json={
            "title": "Roast Chicken",
            "servings_default": 2,
            "course": "main",
            "favorite_side_ids": [second],
        },
    )

    assert res.status_code == 200
    assert res.json()["favorite_side_ids"] == [second]


def test_a_non_side_recipe_cannot_be_a_favorite_side(api_client):
    main_id = _create(api_client, "Lasagne", "main").json()["id"]

    res = _create(api_client, "Roast Chicken", "main", [main_id])

    assert res.status_code == 400
    assert "side" in res.json()["detail"].lower()


def test_an_unknown_favorite_side_is_rejected(api_client):
    res = _create(api_client, "Roast Chicken", "main", [999999])

    assert res.status_code == 400


def test_a_side_dish_cannot_itself_have_favorite_sides(api_client):
    """Only a main dish is served with a side."""
    side_id = _make_side(api_client)

    res = _create(api_client, "Coleslaw", "side", [side_id])

    assert res.status_code == 400


def test_a_first_course_cannot_have_favorite_sides(api_client):
    """Favorite sides are a main-dish feature only."""
    side_id = _make_side(api_client)

    res = _create(api_client, "Risotto", "first-course", [side_id])

    assert res.status_code == 400


def test_deleting_a_favorite_side_leaves_the_main(api_client):
    """Agreed behaviour: the delete is silently allowed."""
    side_id = _make_side(api_client)
    main_id = _create(api_client, "Roast Chicken", "main", [side_id]).json()["id"]

    assert api_client.delete(f"/recipes/{side_id}").status_code == 204

    fetched = api_client.get(f"/recipes/{main_id}")
    assert fetched.status_code == 200
    assert fetched.json()["favorite_side_ids"] == []


def test_generate_returns_the_favorite_side_for_the_main(db_session, user, auth_client):
    side = crud.create_recipe(
        db_session, user_id=user.id, title="Potatoes",
        servings_default=1, course="side",
    )
    main = crud.create_recipe(
        db_session, user_id=user.id, title="Roast",
        servings_default=1, course="main",
    )
    main.favorite_sides = [side]
    db_session.flush()

    res = auth_client.post(
        "/meal-plans/generate",
        json={"start": "2024-01-01", "end": "2024-01-01", "meals_per_day": 1},
    )

    assert res.status_code == 200
    assert res.json()["2024-01-01"][0]["side_ids"] == [side.id]


def test_generate_returns_no_sides_for_a_main_without_favorites(
    db_session, user, auth_client
):
    crud.create_recipe(
        db_session, user_id=user.id, title="Plain Steak",
        servings_default=1, course="main",
    )

    res = auth_client.post(
        "/meal-plans/generate",
        json={"start": "2024-01-01", "end": "2024-01-01", "meals_per_day": 1},
    )

    assert res.json()["2024-01-01"][0]["side_ids"] == []


def test_a_generated_side_persists_onto_the_meal(db_session, user, auth_client):
    """The whole point: generate -> save -> the side is on the plan."""
    side = crud.create_recipe(
        db_session, user_id=user.id, title="Potatoes",
        servings_default=1, course="side",
    )
    main = crud.create_recipe(
        db_session, user_id=user.id, title="Roast",
        servings_default=1, course="main",
    )
    main.favorite_sides = [side]
    db_session.flush()

    generated = auth_client.post(
        "/meal-plans/generate",
        json={"start": "2024-01-01", "end": "2024-01-01", "meals_per_day": 1},
    ).json()
    meal = generated["2024-01-01"][0]

    saved = auth_client.post(
        "/meal-plans",
        json={
            "plan_date": "2024-01-01",
            "plan": {
                "2024-01-01": [
                    {
                        "main_id": meal["id"],
                        "side_ids": meal["side_ids"],
                        "leftover": meal["leftover"],
                    }
                ]
            },
        },
    )

    assert saved.status_code in (200, 201)
    fetched = auth_client.get("/meal-plans?plan_date=2024-01-01").json()
    assert fetched["2024-01-01"][0]["side_recipes"] == ["Potatoes"]
