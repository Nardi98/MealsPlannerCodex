"""Tests for recipe API endpoints requiring authentication."""


def test_recipes_endpoints_require_authentication(client):
    assert client.get("/recipes").status_code == 401
    assert client.post("/recipes", json={}).status_code == 401


def test_recipe_crud_flow(client, user_token_factory):
    auth = user_token_factory()

    payload = {
        "title": "Soup",
        "servings_default": 2,
        "procedure": "Boil",
        "bulk_prep": False,
        "course": "main",
        "tags": ["vegan"],
        "ingredients": [{"name": "Water", "quantity": 1, "unit": "l"}],
    }

    res = client.post("/recipes", json=payload, headers=auth.headers)
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Soup"
    assert data["course"] == "main"
    assert data["ingredients"][0]["name"] == "Water"
    assert data["tags"][0]["name"] == "vegan"

    recipe_id = data["id"]

    listing = client.get("/recipes", headers=auth.headers)
    assert listing.status_code == 200
    assert any(r["id"] == recipe_id for r in listing.json())

    detail = client.get(f"/recipes/{recipe_id}", headers=auth.headers)
    assert detail.status_code == 200
    assert detail.json()["title"] == "Soup"

    update = dict(payload, title="Stew")
    updated = client.put(
        f"/recipes/{recipe_id}",
        json=update,
        headers=auth.headers,
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Stew"

    delete = client.delete(f"/recipes/{recipe_id}", headers=auth.headers)
    assert delete.status_code == 204

    listing = client.get("/recipes", headers=auth.headers)
    assert all(r["id"] != recipe_id for r in listing.json())


def test_recipe_isolation_between_users(client, user_token_factory):
    primary = user_token_factory()
    secondary = user_token_factory()

    payload = {
        "title": "Private Soup",
        "servings_default": 2,
        "course": "main",
        "ingredients": [{"name": "Water", "quantity": 1, "unit": "l"}],
    }

    create = client.post("/recipes", json=payload, headers=primary.headers)
    assert create.status_code == 201
    recipe_id = create.json()["id"]

    primary_list = client.get("/recipes", headers=primary.headers)
    assert primary_list.status_code == 200
    assert any(item["id"] == recipe_id for item in primary_list.json())

    secondary_list = client.get("/recipes", headers=secondary.headers)
    assert secondary_list.status_code == 200
    assert all(item["id"] != recipe_id for item in secondary_list.json())

    secondary_detail = client.get(
        f"/recipes/{recipe_id}", headers=secondary.headers
    )
    assert secondary_detail.status_code == 404


def test_create_recipe_ignores_blank_ingredients(client, user_token_factory):
    auth = user_token_factory()
    payload = {
        "title": "Tea",
        "servings_default": 1,
        "course": "main",
        "ingredients": [
            {"name": "Water", "quantity": 1, "unit": "l"},
            {},
        ],
    }

    res = client.post("/recipes", json=payload, headers=auth.headers)
    assert res.status_code == 201
    data = res.json()
    assert len(data["ingredients"]) == 1
    assert data["ingredients"][0]["name"] == "Water"


def test_create_recipe_defaults_course(client, user_token_factory):
    auth = user_token_factory()
    payload = {
        "title": "Rice",
        "servings_default": 1,
        "ingredients": [],
    }
    res = client.post("/recipes", json=payload, headers=auth.headers)
    assert res.status_code == 201
    assert res.json()["course"] == "main"


def test_recipe_persists_ingredient_season_months(client, user_token_factory):
    auth = user_token_factory()
    payload = {
        "title": "Veggies",
        "servings_default": 2,
        "course": "main",
        "ingredients": [
            {
                "name": "Zucchini",
                "quantity": 1,
                "unit": "piece",
                "season_months": [6, 7],
            }
        ],
    }
    res = client.post("/recipes", json=payload, headers=auth.headers)
    assert res.status_code == 201
    data = res.json()
    assert data["ingredients"][0]["season_months"] == [6, 7]


def test_recipe_defaults_ingredient_season_months(client, user_token_factory):
    auth = user_token_factory()
    payload = {
        "title": "Pepper Soup",
        "servings_default": 1,
        "course": "main",
        "ingredients": [
            {"name": "Pepper", "quantity": 1, "unit": "piece"}
        ],
    }
    res = client.post("/recipes", json=payload, headers=auth.headers)
    assert res.status_code == 201
    data = res.json()
    assert data["ingredients"][0]["season_months"] == list(range(1, 13))
