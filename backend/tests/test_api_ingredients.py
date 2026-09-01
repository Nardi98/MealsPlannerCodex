from fastapi.testclient import TestClient
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from main import app



def test_create_ingredient(api_client) -> None:
    client = api_client
    payload = {
        "name": "Cabbage",
        "season_months": [1, 2],
        "grams_per_piece": 900,
        "preferred_dimension": "mass",
    }
    res = client.post("/ingredients", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Cabbage"
    # An ingredient no longer owns a unit; it owns the physics that let a
    # reader restate it in one.
    assert data["grams_per_piece"] == 900
    assert data["grams_per_ml"] is None
    assert data["preferred_dimension"] == "mass"
    assert data["season_months"] == [1, 2]
    assert data["recipe_count"] == 0


def test_search_ingredients(api_client) -> None:
    client = api_client
    payload = {
        "title": "Pasta",
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
    res = client.post("/recipes", json=payload)
    assert res.status_code == 201

    res = client.get("/ingredients", params={"search": "sp"})
    assert res.status_code == 200
    data = res.json()
    details = {i["name"]: i for i in data}
    assert "Spaghetti" in details

    assert "Spinach" in details

    assert "Salt" not in details


def test_list_all_ingredients(api_client) -> None:
    client = api_client
    payload = {
        "title": "Soup",
        "procedure": "",
        "bulk_prep": False,
        "course": "main",
        "tags": [],
        "ingredients": [
            {"name": "Water", "quantity": 1000, "unit": "ml"},
            {"name": "Carrot", "quantity": 2, "unit": "piece"},
            {"name": "Salt", "quantity": 1, "unit": "g"},
        ],
    }
    res = client.post("/recipes", json=payload)
    assert res.status_code == 201

    res = client.get("/ingredients")
    assert res.status_code == 200
    data = res.json()
    assert {i["name"] for i in data} == {"Water", "Carrot", "Salt"}
    assert all(i["recipe_count"] == 1 for i in data)
    # Nothing was taught any conversions, so the pantry admits it knows none.
    assert all(i["grams_per_ml"] is None for i in data)
    assert all(i["grams_per_piece"] is None for i in data)


def test_update_ingredient(api_client) -> None:
    client = api_client
    payload = {
        "title": "Tea",
        "procedure": "",
        "bulk_prep": False,
        "course": "main",
        "tags": [],
        "ingredients": [
            {"name": "Water", "quantity": 1000, "unit": "ml"},
        ],
    }
    res = client.post("/recipes", json=payload)
    assert res.status_code == 201

    res = client.get("/ingredients")
    ing = res.json()[0]
    res = client.put(
        f"/ingredients/{ing['id']}",
        json={
            "name": "H2O",
            "season_months": [1, 2],
            "grams_per_ml": 1.0,
            "preferred_dimension": "volume",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "H2O"
    assert set(data["season_months"]) == {1, 2}
    assert data["grams_per_ml"] == 1.0
    assert data["preferred_dimension"] == "volume"


def test_ingredient_recipe_lookup_and_delete(api_client) -> None:
    client = api_client

    # Create two recipes sharing an ingredient and one unique recipe
    payload1 = {
        "title": "Pasta",
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
        "procedure": "",
        "bulk_prep": False,
        "course": "main",
        "tags": [],
        "ingredients": [
            {"name": "Tomato", "quantity": 1, "unit": "piece"},
        ],
    }
    res = client.post("/recipes", json=payload1)
    assert res.status_code == 201
    recipe1 = res.json()
    res = client.post("/recipes", json=payload2)
    assert res.status_code == 201
    recipe2 = res.json()

    # Find ingredient id
    res = client.get("/ingredients", params={"search": "Tom"})
    assert res.status_code == 200
    ingredient_id = res.json()[0]["id"]

    # Lookup recipes using the ingredient
    res = client.get(f"/ingredients/{ingredient_id}/recipes")
    assert res.status_code == 200
    titles = {r["title"] for r in res.json()}
    assert titles == {recipe1["title"], recipe2["title"]}

    # Attempt to delete while still referenced
    res = client.delete(f"/ingredients/{ingredient_id}")
    assert res.status_code == 400

    # Delete one recipe and remove ingredient from the other
    client.delete(f"/recipes/{recipe2['id']}")
    client.put(
        f"/recipes/{recipe1['id']}",
        json={
            "title": recipe1["title"],
            "procedure": recipe1["procedure"],
            "bulk_prep": recipe1["bulk_prep"],
            "course": recipe1["course"],
            "tags": [],
            "ingredients": [],
        },
    )

    # Ingredient now unreferenced should delete successfully
    res = client.delete(f"/ingredients/{ingredient_id}")
    assert res.status_code == 204

    # Subsequent lookups should 404
    res = client.get(f"/ingredients/{ingredient_id}/recipes")
    assert res.status_code == 404


def test_force_delete_removes_references(api_client) -> None:
    client = api_client

    payload = {
        "title": "Soup",
        "procedure": "",
        "bulk_prep": False,
        "course": "main",
        "tags": [],
        "ingredients": [
            {"name": "Tomato", "quantity": 1, "unit": "piece"},
        ],
    }
    res = client.post("/recipes", json=payload)
    assert res.status_code == 201

    res = client.get("/ingredients", params={"search": "Tom"})
    assert res.status_code == 200
    ingredient_id = res.json()[0]["id"]

    res = client.delete(f"/ingredients/{ingredient_id}?force=true")
    assert res.status_code == 204

    res = client.get("/recipes")
    assert res.status_code == 200
    recipes = res.json()
    assert recipes[0]["ingredients"] == []
    res = client.get(f"/ingredients/{ingredient_id}/recipes")
    assert res.status_code == 404


def test_read_one_ingredient(api_client) -> None:
    """A single ingredient is fetchable by id.

    The shopping list's "combine" affordance needs the whole row -- including
    the seasonality and categories the editor will save back -- and pulling the
    entire pantry to find one of them would be a poor way to get it.
    """
    client = api_client
    created = client.post(
        "/ingredients",
        json={"name": "Bell Pepper", "season_months": [7, 8], "grams_per_piece": 120},
    ).json()

    res = client.get(f"/ingredients/{created['id']}")

    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Bell Pepper"
    assert body["grams_per_piece"] == 120
    assert body["season_months"] == [7, 8]
    assert body["recipe_count"] == 0


def test_read_one_ingredient_is_scoped_to_its_owner(
    db_session, user, other_user
) -> None:
    from conftest import client_as
    from main import app

    mine = client_as(db_session, user)
    created = mine.post("/ingredients", json={"name": "Private Herb"}).json()

    theirs = client_as(db_session, other_user)
    try:
        assert theirs.get(f"/ingredients/{created['id']}").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_read_a_missing_ingredient_is_a_404(api_client) -> None:
    assert api_client.get("/ingredients/999999").status_code == 404
