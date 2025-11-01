"""Ingredient API integration tests with authentication."""


def test_ingredients_endpoints_require_authentication(client):
    assert client.get("/ingredients").status_code == 401
    assert client.post("/ingredients", json={}).status_code == 401


def test_create_ingredient(client, user_token_factory):
    auth = user_token_factory()
    payload = {"name": "Cabbage", "unit": "kg", "season_months": [1, 2]}
    res = client.post("/ingredients", json=payload, headers=auth.headers)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Cabbage"
    assert data["unit"] == "kg"
    assert data["season_months"] == [1, 2]
    assert data["recipe_count"] == 0


def test_search_ingredients(client, user_token_factory):
    auth = user_token_factory()
    recipe_payload = {
        "title": "Pasta",
        "servings_default": 2,
        "procedure": "",
        "bulk_prep": False,
        "course": "main",
        "tags": [],
        "ingredients": [
            {"name": "Spaghetti", "quantity": 100, "unit": "g"},
            {"name": "Spinach", "quantity": 50, "unit": "g"},
            {"name": "Salt", "quantity": 1, "unit": "g"},
        ],
    }
    create = client.post("/recipes", json=recipe_payload, headers=auth.headers)
    assert create.status_code == 201

    res = client.get(
        "/ingredients",
        params={"search": "sp"},
        headers=auth.headers,
    )
    assert res.status_code == 200
    data = res.json()
    details = {i["name"]: i for i in data}
    assert "Spaghetti" in details
    assert details["Spaghetti"]["unit"] == "g"
    assert "Spinach" in details
    assert details["Spinach"]["unit"] == "g"
    assert "Salt" not in details


def test_list_all_ingredients(client, user_token_factory):
    auth = user_token_factory()
    recipe_payload = {
        "title": "Soup",
        "servings_default": 2,
        "procedure": "",
        "bulk_prep": False,
        "course": "main",
        "tags": [],
        "ingredients": [
            {"name": "Water", "quantity": 1, "unit": "l"},
            {"name": "Carrot", "quantity": 2, "unit": "piece"},
            {"name": "Salt", "quantity": 1, "unit": "g"},
        ],
    }
    res = client.post("/recipes", json=recipe_payload, headers=auth.headers)
    assert res.status_code == 201

    res = client.get("/ingredients", headers=auth.headers)
    assert res.status_code == 200
    data = res.json()
    assert {i["name"] for i in data} == {"Water", "Carrot", "Salt"}
    assert all(i["recipe_count"] == 1 for i in data)
    units = {i["name"]: i["unit"] for i in data}
    assert units == {"Water": "l", "Carrot": "piece", "Salt": "g"}


def test_update_ingredient(client, user_token_factory):
    auth = user_token_factory()
    recipe_payload = {
        "title": "Tea",
        "servings_default": 1,
        "procedure": "",
        "bulk_prep": False,
        "course": "main",
        "tags": [],
        "ingredients": [
            {"name": "Water", "quantity": 1, "unit": "l"},
        ],
    }
    res = client.post("/recipes", json=recipe_payload, headers=auth.headers)
    assert res.status_code == 201

    res = client.get("/ingredients", headers=auth.headers)
    ing = res.json()[0]
    res = client.put(
        f"/ingredients/{ing['id']}",
        json={"name": "H2O", "season_months": [1, 2], "unit": "ml"},
        headers=auth.headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "H2O"
    assert set(data["season_months"]) == {1, 2}
    assert data["unit"] == "ml"


def test_ingredient_recipe_lookup_and_delete(client, user_token_factory):
    auth = user_token_factory()

    payload1 = {
        "title": "Pasta",
        "servings_default": 2,
        "procedure": "",
        "bulk_prep": False,
        "course": "main",
        "tags": [],
        "ingredients": [
            {"name": "Tomato", "quantity": 2, "unit": "piece"},
        ],
    }
    payload2 = {
        "title": "Salad",
        "servings_default": 1,
        "procedure": "",
        "bulk_prep": False,
        "course": "main",
        "tags": [],
        "ingredients": [
            {"name": "Tomato", "quantity": 1, "unit": "piece"},
        ],
    }
    recipe1 = client.post("/recipes", json=payload1, headers=auth.headers)
    assert recipe1.status_code == 201
    recipe1_data = recipe1.json()
    recipe2 = client.post("/recipes", json=payload2, headers=auth.headers)
    assert recipe2.status_code == 201
    recipe2_data = recipe2.json()

    res = client.get(
        "/ingredients",
        params={"search": "Tom"},
        headers=auth.headers,
    )
    assert res.status_code == 200
    ingredient_id = res.json()[0]["id"]

    lookup = client.get(
        f"/ingredients/{ingredient_id}/recipes",
        headers=auth.headers,
    )
    assert lookup.status_code == 200
    titles = {r["title"] for r in lookup.json()}
    assert titles == {recipe1_data["title"], recipe2_data["title"]}

    delete_fail = client.delete(f"/ingredients/{ingredient_id}", headers=auth.headers)
    assert delete_fail.status_code == 400

    client.delete(f"/recipes/{recipe2_data['id']}", headers=auth.headers)
    client.put(
        f"/recipes/{recipe1_data['id']}",
        json={
            "title": recipe1_data["title"],
            "servings_default": recipe1_data["servings_default"],
            "procedure": recipe1_data["procedure"],
            "bulk_prep": recipe1_data["bulk_prep"],
            "course": recipe1_data["course"],
            "tags": [],
            "ingredients": [],
        },
        headers=auth.headers,
    )

    delete_success = client.delete(
        f"/ingredients/{ingredient_id}", headers=auth.headers
    )
    assert delete_success.status_code == 204

    not_found = client.get(
        f"/ingredients/{ingredient_id}/recipes",
        headers=auth.headers,
    )
    assert not_found.status_code == 404


def test_force_delete_removes_references(client, user_token_factory):
    auth = user_token_factory()
    payload = {
        "title": "Soup",
        "servings_default": 1,
        "procedure": "",
        "bulk_prep": False,
        "course": "main",
        "tags": [],
        "ingredients": [
            {"name": "Tomato", "quantity": 1, "unit": "piece"},
        ],
    }
    recipe = client.post("/recipes", json=payload, headers=auth.headers)
    assert recipe.status_code == 201

    res = client.get(
        "/ingredients",
        params={"search": "Tom"},
        headers=auth.headers,
    )
    assert res.status_code == 200
    ingredient_id = res.json()[0]["id"]

    delete = client.delete(
        f"/ingredients/{ingredient_id}?force=true",
        headers=auth.headers,
    )
    assert delete.status_code == 204

    recipes = client.get("/recipes", headers=auth.headers)
    assert recipes.status_code == 200
    assert recipes.json()[0]["ingredients"] == []

    lookup = client.get(
        f"/ingredients/{ingredient_id}/recipes",
        headers=auth.headers,
    )
    assert lookup.status_code == 404
