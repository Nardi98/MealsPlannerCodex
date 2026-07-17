from fastapi.testclient import TestClient
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from main import app



def test_create_ingredient_roundtrips_categories(api_client) -> None:
    client = api_client
    payload = {
        "name": "Spaghetti",
        "unit": "g",
        "season_months": [],
        "categories": ["Grains & Pasta", "Carbs"],
    }
    res = client.post("/ingredients", json=payload)
    assert res.status_code == 201
    assert res.json()["categories"] == ["Grains & Pasta", "Carbs"]


def test_update_ingredient_roundtrips_categories(api_client) -> None:
    client = api_client
    res = client.post(
        "/ingredients",
        json={"name": "Lentils", "unit": "g", "season_months": [], "categories": []},
    )
    ing_id = res.json()["id"]
    res = client.put(
        f"/ingredients/{ing_id}",
        json={
            "name": "Lentils",
            "season_months": [],
            "unit": "g",
            "categories": ["Legumes", "Protein"],
        },
    )
    assert res.status_code == 200
    assert res.json()["categories"] == ["Legumes", "Protein"]


def test_create_rejects_unknown_category(api_client) -> None:
    client = api_client
    res = client.post(
        "/ingredients",
        json={"name": "Mystery", "unit": "g", "categories": ["Not A Category"]},
    )
    assert res.status_code == 422
