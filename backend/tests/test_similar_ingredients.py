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


def test_looser_threshold_returns_more_matches(db_session) -> None:
    basil = Ingredient(name="Basil", unit=UnitEnum.G)
    db_session.add(basil)
    db_session.flush()
    # "Fresh Basil" is too different for the default 0.8 threshold ...
    assert crud.find_similar_ingredients(db_session, "Fresh Basil") == []
    # ... but a looser threshold surfaces it.
    loose = crud.find_similar_ingredients(db_session, "Fresh Basil", threshold=0.5)
    assert "Basil" in [m.name for m in loose]


def test_similar_endpoint_accepts_threshold(api_client) -> None:
    client = api_client
    client.post("/ingredients", json={"name": "Basil", "unit": "g"})

    strict = client.get("/ingredients/similar", params={"name": "Fresh Basil"})
    assert strict.status_code == 200
    assert not any(i["name"] == "Basil" for i in strict.json())

    loose = client.get(
        "/ingredients/similar", params={"name": "Fresh Basil", "threshold": 0.5}
    )
    assert loose.status_code == 200
    assert any(i["name"] == "Basil" for i in loose.json())
