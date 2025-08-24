from fastapi.testclient import TestClient

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from main import app
from mealplanner.db import Base, engine


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_recipe_crud() -> None:
    _reset_db()
    client = TestClient(app)
    payload = {
        "title": "Soup",
        "servings_default": 2,
        "procedure": "Boil",
        "bulk_prep": False,
        "tags": ["vegan"],
        "ingredients": [{"name": "Water", "quantity": 1, "unit": "l"}],
    }
    res = client.post("/recipes", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Soup"
    assert data["ingredients"][0]["name"] == "Water"
    assert data["tags"][0]["name"] == "vegan"

    recipe_id = data["id"]
    res = client.get("/recipes")
    assert any(r["id"] == recipe_id for r in res.json())

    update = dict(payload, title="Stew")
    res = client.put(f"/recipes/{recipe_id}", json=update)
    assert res.status_code == 200
    assert res.json()["title"] == "Stew"

    res = client.delete(f"/recipes/{recipe_id}")
    assert res.status_code == 204
    res = client.get("/recipes")
    assert all(r["id"] != recipe_id for r in res.json())
