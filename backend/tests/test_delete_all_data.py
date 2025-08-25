from fastapi.testclient import TestClient
from main import app
from mealplanner.db import Base, engine, SessionLocal
from mealplanner import crud, models


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_delete_all_data_function() -> None:
    _reset_db()
    with SessionLocal() as session:
        crud.create_recipe(session, title="Soup", servings_default=2)
        crud.create_recipe(session, title="Salad", servings_default=1)
        assert session.query(models.Recipe).count() == 2
        crud.delete_all_data(session)
        assert session.query(models.Recipe).count() == 0


def test_delete_data_endpoint() -> None:
    _reset_db()
    client = TestClient(app)
    payload = {"title": "Soup", "servings_default": 2}
    client.post("/recipes", json=payload)
    assert client.get("/recipes").json()
    res = client.delete("/data")
    assert res.status_code == 204
    assert client.get("/recipes").json() == []
