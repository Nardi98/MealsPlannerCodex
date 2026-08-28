from fastapi.testclient import TestClient

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from main import app



def test_recipe_crud(api_client) -> None:
    client = api_client
    payload = {
        "title": "Soup",
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


def test_create_recipe_ignores_blank_ingredients(api_client) -> None:
    client = api_client
    payload = {
        "title": "Tea",
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


def test_create_recipe_defaults_course_api(api_client) -> None:
    client = api_client
    payload = {
        "title": "Rice",
        "ingredients": [],
    }
    res = client.post("/recipes", json=payload)
    assert res.status_code == 201
    assert res.json()["course"] == "main"


def test_recipe_persists_ingredient_season_months(api_client) -> None:
    client = api_client
    payload = {
        "title": "Veggies",
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


def test_recipe_defaults_ingredient_season_months(api_client) -> None:
    client = api_client
    payload = {
        "title": "Pepper Soup",
        "course": "main",
        "ingredients": [
            {"name": "Pepper", "quantity": 1, "unit": "piece"}
        ],
    }
    res = client.post("/recipes", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["ingredients"][0]["season_months"] == list(range(1, 13))


def _season_of(client, ingredient_id: int) -> list[int]:
    """The stored seasonality of one ingredient (there is no GET by id)."""
    rows = client.get("/ingredients").json()
    return next(row for row in rows if row["id"] == ingredient_id)["season_months"]


def test_recipe_create_does_not_overwrite_an_existing_ingredients_season(
    api_client,
) -> None:
    """Saving a recipe must not rewrite the seasonality of ingredients it uses.

    ``season_months`` lives on the shared ingredient row, so writing whatever a
    recipe payload happens to carry would let one recipe silently reseason an
    ingredient for every other recipe using it -- and the SPA sends an all-year
    default whenever a form does not collect the field. Seasonality is owned by
    the ``/ingredients`` endpoints; a recipe payload only *names* the row.
    """
    client = api_client
    res = client.post(
        "/ingredients",
        json={"name": "Tomato", "unit": "g", "season_months": [6, 7, 8, 9]},
    )
    assert res.status_code == 201
    ingredient_id = res.json()["id"]

    res = client.post(
        "/recipes",
        json={
            "title": "Tomato Salad",
            "course": "main",
            "ingredients": [
                {
                    "id": ingredient_id,
                    "name": "Tomato",
                    "quantity": 100,
                    "unit": "g",
                    "season_months": list(range(1, 13)),
                }
            ],
        },
    )
    assert res.status_code == 201

    assert _season_of(client, ingredient_id) == [6, 7, 8, 9]


def test_recipe_update_does_not_overwrite_an_existing_ingredients_season(
    api_client,
) -> None:
    # Same rule on the update path, which is where it bit hardest: editing any
    # field of a saved recipe re-sends its whole ingredient list.
    client = api_client
    res = client.post(
        "/ingredients",
        json={"name": "Pumpkin", "unit": "g", "season_months": [9, 10, 11, 12]},
    )
    ingredient_id = res.json()["id"]

    payload = {
        "title": "Pumpkin Soup",
        "course": "main",
        "ingredients": [
            {"id": ingredient_id, "name": "Pumpkin", "quantity": 200, "unit": "g"}
        ],
    }
    recipe_id = client.post("/recipes", json=payload).json()["id"]

    res = client.put(f"/recipes/{recipe_id}", json=dict(payload, title="Pumpkin Stew"))
    assert res.status_code == 200

    assert _season_of(client, ingredient_id) == [9, 10, 11, 12]


def test_recipe_matching_an_existing_ingredient_by_name_keeps_its_season(
    api_client,
) -> None:
    # No id, so the row is resolved by name -- still an existing row, still not
    # the recipe's to reseason.
    client = api_client
    res = client.post(
        "/ingredients",
        json={"name": "Asparagus", "unit": "g", "season_months": [4, 5]},
    )
    ingredient_id = res.json()["id"]

    res = client.post(
        "/recipes",
        json={
            "title": "Asparagus Risotto",
            "course": "first-course",
            "ingredients": [{"name": "Asparagus", "quantity": 100, "unit": "g"}],
        },
    )
    assert res.status_code == 201

    assert _season_of(client, ingredient_id) == [4, 5]


def test_recipe_servings_round_trip(api_client) -> None:
    """Quantities are stored as authored; ``servings`` records their basis."""
    client = api_client
    payload = {
        "title": "Ribollita",
        "course": "main",
        "servings": 4,
        "ingredients": [{"name": "Cavolo nero", "quantity": 800, "unit": "g"}],
    }
    res = client.post("/recipes", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["servings"] == 4
    assert data["ingredients"][0]["quantity"] == 800

    res = client.put(f"/recipes/{data['id']}", json=dict(payload, servings=6))
    assert res.status_code == 200
    assert res.json()["servings"] == 6
    # Changing the basis never rewrites what was typed.
    assert res.json()["ingredients"][0]["quantity"] == 800


def test_recipe_defaults_to_one_serving(api_client) -> None:
    res = api_client.post("/recipes", json={"title": "Toast", "course": "main"})
    assert res.status_code == 201
    assert res.json()["servings"] == 1


def test_recipe_rejects_non_positive_servings(api_client) -> None:
    res = api_client.post(
        "/recipes", json={"title": "Nothing", "course": "main", "servings": 0}
    )
    assert res.status_code == 422
