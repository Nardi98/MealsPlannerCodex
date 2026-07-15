from fastapi.testclient import TestClient
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from main import app



def test_invalid_unit_rejected(api_client) -> None:
    client = api_client
    payload = {
        "title": "Salad",
        "servings_default": 1,
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
