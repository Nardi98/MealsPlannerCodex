"""The summer recipe import file: it must be importable, and it must not
duplicate anything the account already holds.

The account is represented by ``tests/data/account_snapshot.json`` -- ingredient
ids with their names, and every existing recipe title. That is all the checks
here need, and committing less of the user's data than the full export is the
point.
"""

import json
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = BACKEND / "tests" / "data" / "account_snapshot.json"


@pytest.fixture(scope="module")
def snapshot():
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_snapshot_is_self_consistent(snapshot):
    names = [ing["name"] for ing in snapshot["ingredients"]]
    ids = [ing["id"] for ing in snapshot["ingredients"]]
    assert len(names) == len(set(names))
    assert len(ids) == len(set(ids))
    assert len(snapshot["recipe_titles"]) == len(set(snapshot["recipe_titles"]))
