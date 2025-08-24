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
            {"quantity": 100, "ingredient": {"name": "Spaghetti", "unit": "g"}},
            {"quantity": 50, "ingredient": {"name": "Spinach", "unit": "g"}},
            {"quantity": 1, "ingredient": {"name": "Salt", "unit": "g"}},
        ],
    }
    res = client.post("/recipes", json=payload)
    assert res.status_code == 201

    res = client.get("/ingredients", params={"search": "sp"})
    assert res.status_code == 200
    data = res.json()
    assert "Spaghetti" in data
    assert "Spinach" in data
    assert "Salt" not in data
