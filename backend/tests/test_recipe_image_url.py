from fastapi.testclient import TestClient
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from main import app
from database import Base, engine


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


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


def test_create_recipe_roundtrips_image_url() -> None:
    _reset_db()
    client = TestClient(app)
    res = client.post(
        "/recipes",
        json=_recipe_payload(image_url="https://example.com/pic.jpg"),
    )
    assert res.status_code == 201
    assert res.json()["image_url"] == "https://example.com/pic.jpg"


def test_create_recipe_defaults_image_url_to_none() -> None:
    _reset_db()
    client = TestClient(app)
    res = client.post("/recipes", json=_recipe_payload())
    assert res.status_code == 201
    assert res.json()["image_url"] is None


def test_update_recipe_sets_and_clears_image_url() -> None:
    _reset_db()
    client = TestClient(app)
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
