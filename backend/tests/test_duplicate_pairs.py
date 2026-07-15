import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parent.parent))

import crud
from main import app
from models import Ingredient, UnitEnum



def test_find_duplicate_pairs_returns_each_pair_once(db_session) -> None:
    db_session.add_all(
        [
            Ingredient(name="Tomato", unit=UnitEnum.G),
            Ingredient(name="Tomatoes", unit=UnitEnum.PIECE),
            Ingredient(name="Onion", unit=UnitEnum.G),
        ]
    )
    db_session.flush()
    pairs = crud.find_duplicate_pairs(db_session)
    names = {frozenset({a.name, b.name}) for a, b, _ in pairs}
    assert frozenset({"Tomato", "Tomatoes"}) in names
    assert len(pairs) == 1
    # scores sorted descending
    scores = [s for _, _, s in pairs]
    assert scores == sorted(scores, reverse=True)


def test_duplicates_endpoint_shape(api_client) -> None:
    client = api_client
    client.post("/ingredients", json={"name": "Tomato", "unit": "g"})
    client.post("/ingredients", json={"name": "Tomatoes", "unit": "piece"})
    res = client.get("/ingredients/duplicates")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    pair = data[0]
    assert {pair["a"]["name"], pair["b"]["name"]} == {"Tomato", "Tomatoes"}
    assert 0.0 <= pair["score"] <= 1.0
    assert "recipe_count" in pair["a"]
