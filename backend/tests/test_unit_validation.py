from fastapi.testclient import TestClient
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from main import app
from mealplanner.db import Base, engine


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_invalid_unit_rejected() -> None:
    _reset_db()
    client = TestClient(app)
    payload = {
        "title": "Salad",
        "servings_default": 1,
        "procedure": "",
        "bulk_prep": False,
        "course": "main course",
        "tags": [],
        "ingredients": [
            {"name": "Lettuce", "quantity": 1, "unit": "bag"},
        ],
    }
    res = client.post("/recipes", json=payload)
    assert res.status_code == 422
