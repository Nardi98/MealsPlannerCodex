"""The summer recipe import file: it must be importable, and it must not
duplicate anything the account already holds.

The account is represented by ``tests/data/account_snapshot.json`` -- ingredient
ids with their names, and every existing recipe title. That is all the checks
here need, and committing less of the user's data than the full export is the
point.
"""

import io
import json
from pathlib import Path

import pytest

import crud
from models import Ingredient, Recipe, UnitEnum
from scripts.build_summer_import import JSON_PATH, build_payload
from scripts.summer_recipes_data import (
    NEW_INGREDIENTS,
    PANTRY,
    RECIPES,
    SKIPPED,
)

BACKEND = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = BACKEND / "tests" / "data" / "account_snapshot.json"

# Derived from the enum rather than copied from it: a unit added to or removed
# from UnitEnum must break this suite, not slip past a stale duplicate of it.
LEGAL_UNITS = {unit.value for unit in UnitEnum}


@pytest.fixture(scope="module")
def snapshot():
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_snapshot_is_self_consistent(snapshot):
    names = [ing["name"] for ing in snapshot["ingredients"]]
    ids = [ing["id"] for ing in snapshot["ingredients"]]
    assert len(names) == len(set(names))
    assert len(ids) == len(set(ids))
    assert len(snapshot["recipe_titles"]) == len(set(snapshot["recipe_titles"]))



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



def test_payload_is_export_shaped():
    payload = build_payload()
    assert set(payload) == {"recipes", "tags", "meal_plans"}
    # Importing a plan would overwrite whatever is planned for that date.
    assert payload["meal_plans"] == []
    assert len(payload["recipes"]) == 24


def test_payload_recipe_ids_are_unique():
    """Merge assigns fresh ids, but favourite-side wiring reads the payload's
    own ids, so they must at least be unique within the file."""
    ids = [r["id"] for r in build_payload()["recipes"]]
    assert len(ids) == len(set(ids))


def test_payload_carries_no_favorite_sides():
    for recipe in build_payload()["recipes"]:
        assert recipe["favorite_side_ids"] == []


def test_payload_tags_are_declared_once_and_referenced_by_id():
    payload = build_payload()
    declared = {tag["id"] for tag in payload["tags"]}
    names = [tag["name"] for tag in payload["tags"]]
    assert len(names) == len(set(names))
    for recipe in payload["recipes"]:
        assert recipe["tags"]
        for tag_id in recipe["tags"]:
            assert tag_id in declared


def test_payload_ingredient_lines_match_the_source_tables(snapshot):
    """The table being right does not prove the renderer copied it -- and the
    renderer is what the account actually receives. ``crud.import_data``
    assigns ``season_months`` onto the ingredient whenever the payload
    carries the key, rather than backfilling it the way it treats
    conversions, so a wrong (or silently dropped) value here would overwrite
    what the user's account already knows. This checks every emitted line
    against ``PANTRY``/``RECIPES`` directly, not merely that the keys exist.

    The id is checked here too: an existing ingredient must carry the
    account's own id, and one the account does not have must carry none. An
    invented id would bind the quantity to an unrelated ingredient.
    """
    by_name = {ing["name"]: ing["id"] for ing in snapshot["ingredients"]}
    for recipe, payload_recipe in zip(RECIPES, build_payload()["recipes"]):
        assert recipe["title"] == payload_recipe["title"]
        source_lines = {name: (quantity, unit) for name, quantity, unit in recipe["ingredients"]}
        assert len(source_lines) == len(recipe["ingredients"])
        emitted_names = {line["name"] for line in payload_recipe["ingredients"]}
        assert emitted_names == set(source_lines)
        for line in payload_recipe["ingredients"]:
            entry = PANTRY[line["name"]]
            quantity, unit = source_lines[line["name"]]
            assert line["season_months"] == entry["season_months"]
            assert line["grams_per_piece"] == entry["grams_per_piece"]
            assert line["quantity"] == quantity
            assert line["unit"] == unit
            assert line["id"] == by_name.get(line["name"])



def _seed_account(session, user, snapshot):
    """Put the account's ingredients and recipe titles in the database.

    Enough for the two things the import must not do: create a second
    ingredient with a name that already exists, or a second recipe with a title
    that already exists.
    """
    for info in snapshot["ingredients"]:
        session.add(Ingredient(
            id=info["id"],
            name=info["name"],
            season_months=info["season_months"],
            grams_per_ml=info["grams_per_ml"],
            grams_per_piece=info["grams_per_piece"],
            user_id=user.id,
        ))
    for title in snapshot["recipe_titles"]:
        session.add(Recipe(title=title, course="main", user_id=user.id))
    session.commit()


def test_the_file_imports_into_a_populated_account(db_session, user, snapshot):
    _seed_account(db_session, user, snapshot)
    before_ingredients = {
        name for (name,) in db_session.query(Ingredient.name).all()
    }
    before_recipes = db_session.query(Recipe).count()

    payload = json.dumps(build_payload())
    crud.import_data(io.StringIO(payload), db_session, mode="merge", user_id=user.id)

    assert db_session.query(Recipe).count() == before_recipes + 24

    after_ingredients = {
        name for (name,) in db_session.query(Ingredient.name).all()
    }
    created = after_ingredients - before_ingredients
    assert created == set(NEW_INGREDIENTS), (
        "import created ingredients that were not the declared new ones: "
        f"{created - set(NEW_INGREDIENTS)}"
    )


def test_imported_recipes_carry_their_quantities(db_session, user, snapshot):
    _seed_account(db_session, user, snapshot)
    payload = json.dumps(build_payload())
    crud.import_data(io.StringIO(payload), db_session, mode="merge", user_id=user.id)

    gazpacho = (
        db_session.query(Recipe)
        .filter(Recipe.title == "Andalusian Gazpacho")
        .one()
    )
    assert gazpacho.servings == 4
    assert gazpacho.course == "first-course"
    assert gazpacho.bulk_prep is True
    by_name = {
        ri.ingredient.name: (ri.quantity, ri.unit.value)
        for ri in gazpacho.ingredients
    }
    assert by_name["Tomato"] == (1000, "g")
    assert by_name["Olive Oil"] == (25, "ml")
    # Reused, not recreated.
    tomato_id = next(
        ri.ingredient.id for ri in gazpacho.ingredients
        if ri.ingredient.name == "Tomato"
    )
    assert tomato_id == 919


def test_import_leaves_the_existing_pantry_intact(db_session, user, snapshot):
    """This asserts the state of the database *after* the merge, not the
    payload before it.

    ``crud.import_data`` writes ``season_months`` onto ingredients that
    already exist *unconditionally* -- not backfilled the way it treats the
    conversions -- so a wrong value anywhere upstream (the source table, the
    renderer, or the import path itself) silently overwrites what the
    account already knows, and it lands in a live account that has no
    backups. Task 2's checks compare ``PANTRY`` against the snapshot, which
    catches a mistake in the table, but nothing else checks what actually
    ends up stored. This does, for every existing ingredient, not just the
    ones the imported recipes touch: ``season_months`` must come back
    exactly as it went in. ``grams_per_ml``, ``grams_per_piece`` and
    ``preferred_dimension`` are genuinely backfill-only (``_backfill_conversions``
    fills a NULL and never replaces a stored value), so those are only
    checked for the stronger violation that would matter -- a value the
    account already had being replaced or cleared.
    """
    _seed_account(db_session, user, snapshot)
    names = {ing.id: ing.name for ing in db_session.query(Ingredient).all()}
    before = {
        ing.id: (
            ing.season_months,
            ing.grams_per_ml,
            ing.grams_per_piece,
            ing.preferred_dimension,
        )
        for ing in db_session.query(Ingredient).all()
    }

    payload = json.dumps(build_payload())
    crud.import_data(io.StringIO(payload), db_session, mode="merge", user_id=user.id)

    after = {
        ing.id: (
            ing.season_months,
            ing.grams_per_ml,
            ing.grams_per_piece,
            ing.preferred_dimension,
        )
        for ing in db_session.query(Ingredient).all()
    }

    for ing_id, (b_season, b_ml, b_piece, b_dim) in before.items():
        a_season, a_ml, a_piece, a_dim = after[ing_id]
        assert a_season == b_season, (
            f"ingredient {ing_id} ({names[ing_id]!r}) had its season_months "
            f"changed during merge: was {b_season}, now {a_season}"
        )
        # grams_per_ml / grams_per_piece / preferred_dimension only ever fill
        # a NULL -- a value the account already had must never move.
        if b_ml is not None:
            assert a_ml == b_ml, (
                f"ingredient {ing_id} ({names[ing_id]!r}) had grams_per_ml "
                f"overwritten: was {b_ml}, now {a_ml}"
            )
        if b_piece is not None:
            assert a_piece == b_piece, (
                f"ingredient {ing_id} ({names[ing_id]!r}) had grams_per_piece "
                f"overwritten: was {b_piece}, now {a_piece}"
            )
        if b_dim is not None:
            assert a_dim == b_dim, (
                f"ingredient {ing_id} ({names[ing_id]!r}) had "
                f"preferred_dimension overwritten: was {b_dim}, now {a_dim}"
            )


def test_the_committed_file_matches_the_table():
    """The deliverable on disk is what gets imported -- not what the table says.

    ``summer-recipes-import.json`` is generated, but it is also the artefact a
    person actually uploads, so it is committed. That pairing is what rots: edit
    a quantity in ``RECIPES``, forget to re-run the builder, and the file the
    account receives is the old one while every other test in this suite passes
    against the new table. Comparing the two is the only thing that notices.
    """
    committed = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert committed == build_payload(), (
        "docs/recipes/summer-recipes-import.json is stale -- "
        "re-run: python -m scripts.build_summer_import"
    )
