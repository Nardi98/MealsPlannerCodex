from fastapi.testclient import TestClient
from main import app
from mealplanner.db import Base, engine


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _create_recipe(client: TestClient) -> None:
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


def test_list_and_update_ingredients() -> None:
    _reset_db()
    client = TestClient(app)
    _create_recipe(client)

    res = client.get("/ingredients/details")
    assert res.status_code == 200
    data = res.json()
    names = [d["name"] for d in data]
    assert names == sorted(names)

    res = client.get("/ingredients/details", params={"order": "desc"})
    names_desc = [d["name"] for d in res.json()]
    assert names_desc == sorted(names_desc, reverse=True)

    res = client.get("/ingredients/details", params={"search": "sp"})
    assert res.status_code == 200
    assert {d["name"] for d in res.json()} == {"Spaghetti", "Spinach"}

    salt = next(d for d in data if d["name"] == "Salt")
    res = client.put(
        f"/ingredients/{salt['id']}",
        json={"name": "Salt", "quantity": 2, "unit": "g", "season_months": []},
    )
    assert res.status_code == 200
    assert res.json()["quantity"] == 2
