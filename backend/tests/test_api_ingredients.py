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
    names = {i["name"] for i in data}
    assert "Spaghetti" in names
    assert "Spinach" in names
    assert "Salt" not in names


def test_list_all_ingredients() -> None:
    _reset_db()
    client = TestClient(app)
    payload = {
        "title": "Soup",
        "servings_default": 2,
        "procedure": "",
        "bulk_prep": False,
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


def test_update_ingredient() -> None:
    _reset_db()
    client = TestClient(app)
    payload = {
        "title": "Tea",
        "servings_default": 1,
        "procedure": "",
        "bulk_prep": False,
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
        json={"name": "H2O", "season_months": [1, 2]},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "H2O"
    assert set(data["season_months"]) == {1, 2}
