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


from scripts.summer_recipes_data import PANTRY, NEW_INGREDIENTS


def test_existing_pantry_entries_match_the_account(snapshot):
    """An id must name the ingredient the account thinks it names, and carry
    the seasonality the account already has.

    ``get_or_create_ingredient`` looks an ingredient up by id first, so a wrong
    id silently attaches a quantity to an unrelated ingredient. And
    ``import_data`` *assigns* ``season_months`` rather than backfilling it, so a
    wrong list here quietly destroys the account's own value.
    """
    by_id = {ing["id"]: ing for ing in snapshot["ingredients"]}
    for name, entry in PANTRY.items():
        if entry["id"] is None:
            continue
        assert entry["id"] in by_id, f"{name} cites unknown id {entry['id']}"
        assert by_id[entry["id"]]["name"] == name
        # season_months is assigned on import, not backfilled like the
        # conversions are, so a value that disagrees with the account here
        # silently overwrites what the account already knows.
        assert entry["season_months"] == by_id[entry["id"]]["season_months"], (
            f"{name} would overwrite the account's seasonality"
        )


def test_new_ingredients_are_genuinely_new(snapshot):
    """A new ingredient carries no id and no name the account already uses."""
    existing = {ing["name"] for ing in snapshot["ingredients"]}
    for name in NEW_INGREDIENTS:
        assert PANTRY[name]["id"] is None
        assert name not in existing


from scripts.summer_recipes_data import RECIPES, SKIPPED

LEGAL_UNITS = {"g", "ml", "piece"}


def test_twenty_four_recipes_split_by_course():
    assert len(RECIPES) == 24
    courses = [r["course"] for r in RECIPES]
    assert courses.count("first-course") == 5
    assert courses.count("main") == 7
    assert courses.count("side") == 12


def test_no_imported_title_collides_with_an_existing_one(snapshot):
    existing = {t.casefold() for t in snapshot["recipe_titles"]}
    for recipe in RECIPES:
        assert recipe["title"].casefold() not in existing


def test_five_recipes_were_skipped_as_duplicates():
    assert len(SKIPPED) == 5


def test_every_recipe_is_complete():
    titles = [r["title"] for r in RECIPES]
    assert len(titles) == len(set(titles))
    for recipe in RECIPES:
        assert recipe["servings"] == 4
        assert recipe["procedure"].strip()
        assert len(recipe["ingredients"]) >= 3
        assert recipe["tags"]
        assert isinstance(recipe["bulk_prep"], bool)


def test_every_ingredient_line_is_measurable():
    """A quantity with no unit cannot be added to anything.

    ``crud.import_data`` raises on such a line, so catching it here is the
    difference between a failing test and a rejected import.
    """
    for recipe in RECIPES:
        for name, quantity, unit in recipe["ingredients"]:
            assert name in PANTRY, f"{recipe['title']}: unknown ingredient {name}"
            assert unit in LEGAL_UNITS, f"{recipe['title']}: bad unit {unit}"
            assert quantity > 0


def test_every_piece_ingredient_has_a_weight():
    """A piece-unit line with no known weight cannot be converted to grams.

    This is a distinct claim from "the recipe's mass is plausible" -- it is
    about the pantry data, not about any one recipe's total -- so it gets its
    own test rather than surfacing as an assertion buried inside the bulk
    calculation for ``test_each_recipe_feeds_four``.
    """
    for recipe in RECIPES:
        for name, quantity, unit in recipe["ingredients"]:
            if unit == "piece":
                assert PANTRY[name]["grams_per_piece"], (
                    f"{recipe['title']}: {name} in pieces with no weight"
                )


# What four portions of each kind of dish plausibly weighs, in grams, counting
# only the solid and liquid bulk -- seasonings are excluded because a recipe is
# not made implausible by three grams of oregano.
#
# These bounds are not a nutritional standard. They were set by computing the
# actual bulk totals of the 24 imported recipes -- which run 333-2010 g -- and
# leaving room on either side. The band is a tripwire calibrated to this data
# set, not an authority on correct portion size. The tightest margins in that
# calibration were Cannellini Cream at 333 g against the 300 g floor and Light
# Krompirusa at 920 g against the 900 g floor.
SANE_TOTAL_GRAMS = {
    "first-course": (850, 3000),
    "main": (900, 2600),
    "side": (300, 1800),
}

SEASONINGS = {
    "Salt", "Black Pepper", "Sugar", "Cumin", "Paprika", "Nutmeg", "Oregano",
    "Rosemary", "Basil", "Parsley", "Dill", "Garlic", "Olive Oil",
    "Red Wine Vinegar", "White Wine Vinegar", "Dijon Mustard", "Lemon Juice",
}


def _bulk_grams(recipe):
    total = 0.0
    for name, quantity, unit in recipe["ingredients"]:
        if name in SEASONINGS:
            continue
        if unit in ("g", "ml"):
            total += quantity
        else:
            total += quantity * PANTRY[name]["grams_per_piece"]
    return total


@pytest.mark.parametrize("recipe", RECIPES, ids=lambda r: r["title"])
def test_each_recipe_feeds_four(recipe):
    """The band bounds the sum, and the sum is dominated by the largest line,
    so a threefold error on a minor ingredient can still pass -- this does
    not check that every quantity is individually plausible, only that the
    total is. A green result here is not proof every line was checked."""
    low, high = SANE_TOTAL_GRAMS[recipe["course"]]
    total = _bulk_grams(recipe)
    assert low <= total <= high, f"{recipe['title']} is {total:.0f} g for four, want {low}-{high}"


def test_oil_is_measured_by_the_spoon():
    """The document's central claim: the oil is what decides whether a plate of
    vegetables is light. Past 40 ml for four, this is not that cookbook."""
    for recipe in RECIPES:
        oil = sum(q for n, q, _ in recipe["ingredients"] if n == "Olive Oil")
        assert oil <= 40, f"{recipe['title']} uses {oil} ml of oil"
