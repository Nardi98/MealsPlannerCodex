from fastapi.testclient import TestClient
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from main import app



def test_invalid_unit_rejected(api_client) -> None:
    client = api_client
    payload = {
        "title": "Salad",
        "procedure": "",
        "bulk_prep": False,
        "course": "main",
        "tags": [],
        "ingredients": [
            {"name": "Lettuce", "quantity": 1, "unit": "bag"},
        ],
    }
    res = client.post("/recipes", json=payload)
    assert res.status_code == 422


def test_a_negative_quantity_is_refused(auth_client) -> None:
    """You cannot need less than none of something.

    A negative quantity is not a small quantity: it subtracts from every other
    recipe's share of the same ingredient once the shopping list unifies them,
    so one bad row silently corrupts an unrelated total.
    """
    res = auth_client.post(
        "/recipes",
        json={
            "title": "Impossible",
            "course": "main",
            "ingredients": [{"name": "Onion", "quantity": -10, "unit": "piece"}],
        },
    )
    assert res.status_code == 422


def test_a_zero_quantity_is_still_allowed(auth_client) -> None:
    # "To taste" is a real thing to write down, and it is not an error.
    res = auth_client.post(
        "/recipes",
        json={
            "title": "Seasoned",
            "course": "main",
            "ingredients": [{"name": "Salt", "quantity": 0, "unit": "g"}],
        },
    )
    assert res.status_code == 201
