from fastapi.testclient import TestClient

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from main import app
from mealplanner.db import Base, engine
from migration_runner import upgrade as run_migrations


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    run_migrations(engine)


def test_recipe_crud() -> None:
    _reset_db()
    client = TestClient(app)
    payload = {
        "title": "Soup",
        "servings_default": 2,
        "procedure": "Boil",
        "bulk_prep": False,
        "course": "main",
        "tags": ["vegan"],
        "ingredients": [{"name": "Water", "quantity": 1, "unit": "l"}],
    }
    res = client.post("/recipes", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Soup"
    assert data["course"] == "main"
    assert data["ingredients"][0]["name"] == "Water"
    assert data["tags"][0]["name"] == "vegan"

    recipe_id = data["id"]
    res = client.get("/recipes")
    assert any(r["id"] == recipe_id for r in res.json())

    res = client.get(f"/recipes/{recipe_id}")
    assert res.status_code == 200
    assert res.json()["title"] == "Soup"

    update = dict(payload, title="Stew")
    res = client.put(f"/recipes/{recipe_id}", json=update)
    assert res.status_code == 200
    assert res.json()["title"] == "Stew"

    res = client.delete(f"/recipes/{recipe_id}")
    assert res.status_code == 204
    res = client.get("/recipes")
    assert all(r["id"] != recipe_id for r in res.json())


def test_create_recipe_ignores_blank_ingredients() -> None:
    _reset_db()
    client = TestClient(app)
    payload = {
        "title": "Tea",
        "servings_default": 1,
        "course": "main",
        "ingredients": [
            {"name": "Water", "quantity": 1, "unit": "l"},
            {},
        ],
    }
    res = client.post("/recipes", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert len(data["ingredients"]) == 1
    assert data["ingredients"][0]["name"] == "Water"


def test_create_recipe_defaults_course_api() -> None:
    _reset_db()
    client = TestClient(app)
    payload = {
        "title": "Rice",
        "servings_default": 1,
        "ingredients": [],
    }
    res = client.post("/recipes", json=payload)
    assert res.status_code == 201
    assert res.json()["course"] == "main"


def test_recipe_persists_ingredient_season_months() -> None:
    _reset_db()
    client = TestClient(app)
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
    res = client.post("/recipes", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["ingredients"][0]["season_months"] == [6, 7]


def test_recipe_defaults_ingredient_season_months() -> None:
    _reset_db()
    client = TestClient(app)
    payload = {
        "title": "Pepper Soup",
        "servings_default": 1,
        "course": "main",
        "ingredients": [
            {"name": "Pepper", "quantity": 1, "unit": "piece"}
        ],
    }
    res = client.post("/recipes", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["ingredients"][0]["season_months"] == list(range(1, 13))
