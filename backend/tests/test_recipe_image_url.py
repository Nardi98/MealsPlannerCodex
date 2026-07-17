from fastapi.testclient import TestClient
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from main import app



def _recipe_payload(**overrides) -> dict:
    payload = {
        "title": "Test Recipe",
        "servings_default": 1,
        "procedure": "Cook it.",
        "bulk_prep": False,
        "course": "main",
        "tags": [],
        "ingredients": [],
    }
    payload.update(overrides)
    return payload


def test_create_recipe_roundtrips_image_url(api_client) -> None:
    client = api_client
    res = client.post(
        "/recipes",
        json=_recipe_payload(image_url="https://example.com/pic.jpg"),
    )
    assert res.status_code == 201
    assert res.json()["image_url"] == "https://example.com/pic.jpg"


def test_create_recipe_defaults_image_url_to_none(api_client) -> None:
    client = api_client
    res = client.post("/recipes", json=_recipe_payload())
    assert res.status_code == 201
    assert res.json()["image_url"] is None


def test_update_recipe_sets_and_clears_image_url(api_client) -> None:
    client = api_client
    recipe_id = client.post("/recipes", json=_recipe_payload()).json()["id"]

    res = client.put(
        f"/recipes/{recipe_id}",
        json=_recipe_payload(image_url="https://example.com/new.png"),
    )
    assert res.status_code == 200
    assert res.json()["image_url"] == "https://example.com/new.png"

    res = client.put(f"/recipes/{recipe_id}", json=_recipe_payload(image_url=None))
    assert res.status_code == 200
    assert res.json()["image_url"] is None
