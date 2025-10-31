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


def test_invalid_unit_rejected() -> None:
    _reset_db()
    client = TestClient(app)
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
