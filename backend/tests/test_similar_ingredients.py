import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parent.parent))

import crud
from main import app
from models import Ingredient, UnitEnum



def test_find_similar_matches_plural(db_session) -> None:
    tomato = Ingredient(name="Tomato", unit=UnitEnum.G)
    db_session.add_all(
        [
            tomato,
            Ingredient(name="Onion", unit=UnitEnum.G),
        ]
    )
    db_session.flush()
    matches = crud.find_similar_ingredients(db_session, "Tomatoes")
    names = [m.name for m in matches]
    assert "Tomato" in names
    assert "Onion" not in names


def test_find_similar_respects_exclude_id(db_session) -> None:
    tomato = Ingredient(name="Tomato", unit=UnitEnum.G)
    db_session.add(tomato)
    db_session.flush()
    matches = crud.find_similar_ingredients(
        db_session, "Tomato", exclude_id=tomato.id
    )
    assert tomato.id not in [m.id for m in matches]


def test_similar_endpoint(api_client) -> None:
    client = api_client
    client.post("/ingredients", json={"name": "Tomato", "unit": "g"})
    res = client.get("/ingredients/similar", params={"name": "Tomatoes"})
    assert res.status_code == 200
    assert any(i["name"] == "Tomato" for i in res.json())
