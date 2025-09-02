from fastapi.testclient import TestClient
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from main import app
from mealplanner.db import Base, engine


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_search_ingredients() -> None:
    _reset_db()
    client = TestClient(app)
    payload = {
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
    res = client.post("/recipes", json=payload)
    assert res.status_code == 201

    res = client.get("/ingredients", params={"search": "sp"})
    assert res.status_code == 200
    data = res.json()
    details = {i["name"]: i for i in data}
    assert "Spaghetti" in details
    assert details["Spaghetti"]["unit"] == "g"
    assert "Spinach" in details
    assert details["Spinach"]["unit"] == "g"
    assert "Salt" not in details


def test_list_all_ingredients() -> None:
    _reset_db()
    client = TestClient(app)
    payload = {
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
    res = client.post("/recipes", json=payload)
    assert res.status_code == 201

    res = client.get("/ingredients")
    assert res.status_code == 200
    data = res.json()
    assert {i["name"] for i in data} == {"Water", "Carrot", "Salt"}
    assert all(i["recipe_count"] == 1 for i in data)
    units = {i["name"]: i["unit"] for i in data}
    assert units == {"Water": "l", "Carrot": "piece", "Salt": "g"}


def test_update_ingredient() -> None:
    _reset_db()
    client = TestClient(app)
    payload = {
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
    res = client.post("/recipes", json=payload)
    assert res.status_code == 201

    res = client.get("/ingredients")
    ing = res.json()[0]
    res = client.put(
        f"/ingredients/{ing['id']}",
        json={"name": "H2O", "season_months": [1, 2], "unit": "ml"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "H2O"
    assert set(data["season_months"]) == {1, 2}
    assert data["unit"] == "ml"


def test_ingredient_recipe_lookup_and_delete() -> None:
    _reset_db()
    client = TestClient(app)

    # Create two recipes sharing an ingredient and one unique recipe
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
            "servings_default": recipe1["servings_default"],
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
