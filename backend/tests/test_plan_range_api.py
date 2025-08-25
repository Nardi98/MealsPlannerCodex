from datetime import date
from datetime import date
from fastapi.testclient import TestClient
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from main import app
from mealplanner.db import Base, engine, SessionLocal
from mealplanner.crud import create_recipe, set_meal_plan


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_get_plan_range_combines_plans() -> None:
    _reset_db()
    with SessionLocal() as session:
        r1 = create_recipe(session, title="A", servings_default=1)
        r2 = create_recipe(session, title="B", servings_default=1)
        d1 = date(2024, 1, 1)
        d2 = date(2024, 1, 2)
        set_meal_plan(session, d1, {d1.isoformat(): [r1.id]})
        set_meal_plan(session, d2, {d2.isoformat(): [r2.id]})

    client = TestClient(app)
    res = client.get("/plan", params={"start": "2024-01-01", "end": "2024-01-02"})
    assert res.status_code == 200
    assert res.json() == {"2024-01-01": ["A"], "2024-01-02": ["B"]}


def test_get_plan_range_empty() -> None:
    _reset_db()
    client = TestClient(app)
    res = client.get("/plan", params={"start": "2024-01-01", "end": "2024-01-02"})
    assert res.status_code == 200
    assert res.json() == {}
