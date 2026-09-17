"""Integrity of the system recipe catalog pack (spec TST-3, INIT-2..7).

``backend/data/catalog_pack.json`` populates an empty catalog at bootstrap.
These tests guard it against a silent loss or corruption during porting: a
missing recipe, an ingredient name the system account does not own (adoption
would then invent an all-year ingredient), a tag outside the system vocabulary,
or a stray presentation field such as ``minutes`` that ``Recipe`` has no column
for. They read the JSON files only and need no database.
"""
import json
from collections import Counter
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

PACK_KEYS = {"title", "course", "servings", "bulk_prep", "tags", "procedure", "ingredients"}
INGREDIENT_KEYS = {"name", "quantity", "unit"}


def _load(name):
    with open(DATA_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def pack():
    return _load("catalog_pack.json")


def _ingredients(pack):
    return [(recipe["title"], ing) for recipe in pack for ing in recipe["ingredients"]]


def test_pack_is_an_array_of_sixty_recipes_split_by_course(pack):
    assert isinstance(pack, list)
    assert len(pack) == 60
    assert Counter(recipe["course"] for recipe in pack) == {"main": 26, "side": 20, "first-course": 14}


def test_titles_are_unique(pack):
    duplicates = [title for title, n in Counter(r["title"] for r in pack).items() if n > 1]
    assert duplicates == []


def test_recipe_keys_are_exactly_the_pack_contract(pack):
    bad = {r["title"]: sorted(set(r) ^ PACK_KEYS) for r in pack if set(r) != PACK_KEYS}
    assert bad == {}


def test_ingredient_keys_are_exactly_name_quantity_unit(pack):
    bad = [(title, ing) for title, ing in _ingredients(pack) if set(ing) != INGREDIENT_KEYS]
    assert bad == []


def test_every_ingredient_name_exactly_matches_a_system_ingredient(pack):
    system_names = {ing["name"] for ing in _load("system_ingredients.json")}
    unknown = [(title, ing["name"]) for title, ing in _ingredients(pack) if ing["name"] not in system_names]
    assert unknown == []


def test_every_tag_is_a_system_tag(pack):
    system_tags = {tag["name"] for tag in _load("system_tags.json")}
    unknown = [(r["title"], tag) for r in pack for tag in r["tags"] if tag not in system_tags]
    assert unknown == []


def test_servings_is_a_positive_int(pack):
    # ``bool`` is an ``int`` subclass; ``True`` must not pass as one serving.
    bad = {
        r["title"]: r["servings"]
        for r in pack
        if not isinstance(r["servings"], int) or isinstance(r["servings"], bool) or r["servings"] < 1
    }
    assert bad == {}


def test_bulk_prep_is_a_bool(pack):
    bad = {r["title"]: r["bulk_prep"] for r in pack if not isinstance(r["bulk_prep"], bool)}
    assert bad == {}


def test_units_are_canonical_and_quantities_positive(pack):
    bad = [
        (title, ing)
        for title, ing in _ingredients(pack)
        if ing["unit"] not in {"g", "ml", "piece"}
        or isinstance(ing["quantity"], bool)
        or not isinstance(ing["quantity"], (int, float))
        or ing["quantity"] <= 0
    ]
    assert bad == []


def test_piece_quantities_are_whole_numbers(pack):
    bad = [
        (title, ing)
        for title, ing in _ingredients(pack)
        if ing["unit"] == "piece" and float(ing["quantity"]) != int(ing["quantity"])
    ]
    assert bad == []


def test_every_recipe_is_complete_enough_to_publish(pack):
    # CAT-10 refuses to publish a recipe without a procedure or ingredients.
    bad = [
        r["title"]
        for r in pack
        if not isinstance(r["procedure"], str) or not r["procedure"].strip() or not r["ingredients"]
    ]
    assert bad == []


def test_tags_are_a_list_of_strings(pack):
    bad = {r["title"]: r["tags"] for r in pack if not isinstance(r["tags"], list)
           or not all(isinstance(t, str) for t in r["tags"])}
    assert bad == {}
