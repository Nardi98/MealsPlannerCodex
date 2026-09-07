# Summer Recipe Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `docs/recipes/summer-recipes-import.json` — 24 recipes from `ricettario-estivo-saziante.md`, in `/data/export` shape, ready for `POST /data/import?mode=merge` — plus an audit report of every inferred and corrected value.

**Architecture:** The 24 recipes live as declarative Python data (`scripts/summer_recipes_data.py`), separate from the code that renders them (`scripts/build_summer_import.py`). Rendering is mechanical: scaling arithmetic, id lookup and report generation all read the one table, so no number is typed twice. Tests run the generated file through the real `crud.import_data` against a database seeded from a snapshot of the account, which is the only check that proves the file is importable.

**Tech Stack:** Python 3.11, SQLAlchemy, pytest, PostgreSQL (test DB via `docker start mp_test_pg`), flake8.

**Spec:** `docs/superpowers/specs/2026-09-07-summer-recipe-import-design.md`

---

## Before You Start

Run every command from `backend/`. Start the test database first:

```bash
docker start mp_test_pg
```

Lint with `python -m flake8` (not bare `flake8`). Max line length 120. `scripts/` is **not** in the flake8 exclude list, so both new modules must lint clean; `tests/` is excluded.

## File Structure

| File | Responsibility |
|---|---|
| `backend/tests/data/account_snapshot.json` | Create. The minimal facts about the live account the tests need: existing ingredient ids with names and conversions, and existing recipe titles. No procedures, no meal plans, no scores. |
| `backend/scripts/summer_recipes_data.py` | Create. `PANTRY`, `SKIPPED` and `RECIPES` — pure data, no logic. |
| `backend/scripts/build_summer_import.py` | Create. Renders `RECIPES` into the export-shaped JSON and the Markdown report. |
| `backend/tests/test_summer_recipes_import.py` | Create. Structural checks on the data, plausibility checks on the quantities, and the end-to-end import. |
| `docs/recipes/summer-recipes-import.json` | Generated output. The deliverable. |
| `docs/recipes/summer-recipes-report.md` | Generated output. The audit trail. |

---

### Task 1: The account snapshot

The tests need to know what the account already holds, without committing the user's whole export (procedures, scores and meal plans are not needed to check for duplicates).

**Files:**
- Create: `backend/tests/data/account_snapshot.json`
- Test: `backend/tests/test_summer_recipes_import.py`

- [ ] **Step 1: Write the snapshot file**

Create `backend/tests/data/account_snapshot.json`. `ingredients` holds every id the new recipes reference plus the ones whose names they must avoid colliding with; `recipe_titles` holds all 52 existing titles so the duplicate check is real.

```json
{
  "ingredients": [
    {"id": 911, "name": "Potato", "season_months": [9, 10, 11, 12, 1], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 913, "name": "Carrot", "season_months": [], "grams_per_ml": null, "grams_per_piece": 60, "preferred_dimension": "piece"},
    {"id": 914, "name": "Onion", "season_months": [], "grams_per_ml": null, "grams_per_piece": 150, "preferred_dimension": "piece"},
    {"id": 915, "name": "Red Onion", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 917, "name": "Garlic", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 919, "name": "Tomato", "season_months": [6, 7, 8, 9], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 920, "name": "Cherry Tomato", "season_months": [6, 7, 8, 9], "grams_per_ml": null, "grams_per_piece": 15, "preferred_dimension": null},
    {"id": 923, "name": "Bell Pepper", "season_months": [7, 8, 9, 10], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 925, "name": "Cucumber", "season_months": [6, 7, 8, 9], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 926, "name": "Zucchini", "season_months": [6, 7, 8, 9], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 927, "name": "Eggplant", "season_months": [7, 8, 9, 10], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 932, "name": "Spinach", "season_months": [3, 4, 5, 9, 10], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 935, "name": "Rocket", "season_months": [5, 6, 7, 8, 9], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 953, "name": "Lemon", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 990, "name": "Egg", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 992, "name": "Greek Yogurt", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 997, "name": "Parmesan", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1018, "name": "Chickpeas", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1019, "name": "Lentils", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1022, "name": "Cannellini Beans", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1025, "name": "Basil", "season_months": [5, 6, 7, 8, 9], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1026, "name": "Parsley", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1028, "name": "Rosemary", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1030, "name": "Oregano", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1034, "name": "Cumin", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1035, "name": "Paprika", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1037, "name": "Nutmeg", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1039, "name": "Black Pepper", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1040, "name": "Salt", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1044, "name": "Olive Oil", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1048, "name": "White Wine Vinegar", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1056, "name": "Passata", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1058, "name": "Vegetable Stock", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1068, "name": "Sugar", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1085, "name": "Olives", "season_months": [], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1108, "name": "Capers", "season_months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "grams_per_ml": null, "grams_per_piece": null, "preferred_dimension": null},
    {"id": 1109, "name": "garlic cloves", "season_months": [], "grams_per_ml": null, "grams_per_piece": 5, "preferred_dimension": null}
  ],
  "recipe_titles": [
    "Sicilian-Style Swordfish", "Mozzarelle", "Pasta alla Norma",
    "Pasta with Smoked Tofu and Eggplant", "Spaghetti Carbonara",
    "Bulgur with Zucchini, Peas and Lemon", "Pasta al Ragu", "Mushroom Risotto",
    "Pea and Leek Tart with Lemon Zest", "Chickpea and Caramelised Leek Tart",
    "Pasta with Cauliflower Miso Cream", "Tuna and Cherry Tomato Pasta",
    "Chickpea Hummus Tart with Caramelised Onion",
    "Pasta with Chickpea Cream and Confit Tomatoes", "Potato, Leek and Kale Soup",
    "Pasta with Fresh Tomato Sauce", "Spaghetti Aglio, Olio e Peperoncino",
    "Minestrone", "Lentils Stew", "Baked Salmon with Herbs", "Shakshuka",
    "Mashed Potatoes", "Steamed Broccoli", "Sauteed Spinach with Garlic",
    "Green Salad", "Classic Hummus", "Chana Masala", "Pan-Seared Steak",
    "Rosemary Roasted Potatoes", "Boiled Potatoes with Olive Oil",
    "Roasted Carrots with Cumin", "Tomato and Cucumber Salad",
    "Lentil Hummus with Sun-dried Tomatoes", "Summer Rolls with Marinated Tofu",
    "Peperonata", "Babaganoush", "Zucchini Frittata", "Golden Soy Chunks",
    "Caramelised Onions and Peppers", "Roasted Chickpea Hummus",
    "Pizza Margherita", "Roast Chicken Thighs with Lemon",
    "Seitan Kebab with Yogurt Sauce", "Tomato salad", "Boiled Eggs", "Falafel",
    "Caponata", "Green Beans", "Pan-Fried Zucchini", "Red lentil soup",
    "Cannellini and Cherry Tomato Tart", "Coconut Chicken Curry"
  ]
}
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_summer_recipes_import.py`:

```python
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
```

- [ ] **Step 3: Run the test**

Run: `python -m pytest tests/test_summer_recipes_import.py -v`
Expected: PASS once Step 1's file exists; `FileNotFoundError` if it does not.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/data/account_snapshot.json backend/tests/test_summer_recipes_import.py
git commit -m "Snapshot what the account already holds

The duplicate and pantry checks need existing ingredient ids and recipe
titles, and nothing else -- not procedures, scores or meal plans."
```

---

### Task 2: The pantry table

**Files:**
- Create: `backend/scripts/summer_recipes_data.py`
- Test: `backend/tests/test_summer_recipes_import.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_summer_recipes_import.py`:

```python
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_summer_recipes_import.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.summer_recipes_data'`

- [ ] **Step 3: Write the pantry**

Create `backend/scripts/summer_recipes_data.py`:

```python
"""The 24 summer recipes, as data.

Quantities are written for **four** portions. Where the source document gave
six, the number here is the source's times 2/3, rounded; where it gave none,
the number was chosen and is recorded in ``notes`` so the report can list it.

Nothing in this module does anything -- ``build_summer_import.py`` is what
turns it into a file. Keeping the two apart means a number can be checked by
reading it, without following any logic.
"""

# ``id`` is the ingredient's id in the account, or None for one that does not
# exist there yet. Import matches by id first and by exact name second, so a
# None here is a deliberate "create this by name"; an invented id would bind
# the line to an unrelated ingredient.
PANTRY = {
    # -- existing, referenced by id ------------------------------------------
    "Potato": {"id": 911, "season_months": [9, 10, 11, 12, 1], "grams_per_piece": None},
    "Onion": {"id": 914, "season_months": [], "grams_per_piece": 150},
    "Red Onion": {"id": 915, "season_months": [], "grams_per_piece": 120},
    "Garlic": {"id": 917, "season_months": [], "grams_per_piece": None},
    "Tomato": {"id": 919, "season_months": [6, 7, 8, 9], "grams_per_piece": 120},
    "Cherry Tomato": {"id": 920, "season_months": [6, 7, 8, 9], "grams_per_piece": 15},
    "Bell Pepper": {"id": 923, "season_months": [7, 8, 9, 10], "grams_per_piece": 150},
    "Cucumber": {"id": 925, "season_months": [6, 7, 8, 9], "grams_per_piece": 300},
    "Zucchini": {"id": 926, "season_months": [6, 7, 8, 9], "grams_per_piece": 200},
    "Eggplant": {"id": 927, "season_months": [7, 8, 9, 10], "grams_per_piece": 300},
    "Spinach": {"id": 932, "season_months": [3, 4, 5, 9, 10], "grams_per_piece": None},
    "Rocket": {"id": 935, "season_months": [5, 6, 7, 8, 9], "grams_per_piece": None},
    "Lemon": {"id": 953, "season_months": [], "grams_per_piece": 100},
    "Egg": {"id": 990, "season_months": [], "grams_per_piece": 60},
    "Greek Yogurt": {"id": 992, "season_months": [], "grams_per_piece": None},
    "Parmesan": {"id": 997, "season_months": [], "grams_per_piece": None},
    "Chickpeas": {"id": 1018, "season_months": [], "grams_per_piece": None},
    "Lentils": {"id": 1019, "season_months": [], "grams_per_piece": None},
    "Cannellini Beans": {"id": 1022, "season_months": [], "grams_per_piece": None},
    "Basil": {"id": 1025, "season_months": [5, 6, 7, 8, 9], "grams_per_piece": None},
    "Parsley": {"id": 1026, "season_months": [], "grams_per_piece": None},
    "Rosemary": {"id": 1028, "season_months": [], "grams_per_piece": None},
    "Oregano": {"id": 1030, "season_months": [], "grams_per_piece": None},
    "Cumin": {"id": 1034, "season_months": [], "grams_per_piece": None},
    "Paprika": {"id": 1035, "season_months": [], "grams_per_piece": None},
    "Nutmeg": {"id": 1037, "season_months": [], "grams_per_piece": None},
    "Black Pepper": {"id": 1039, "season_months": [], "grams_per_piece": None},
    "Salt": {"id": 1040, "season_months": [], "grams_per_piece": None},
    "Olive Oil": {"id": 1044, "season_months": [], "grams_per_piece": None},
    "White Wine Vinegar": {"id": 1048, "season_months": [], "grams_per_piece": None},
    "Passata": {"id": 1056, "season_months": [], "grams_per_piece": None},
    "Vegetable Stock": {"id": 1058, "season_months": [], "grams_per_piece": None},
    "Sugar": {"id": 1068, "season_months": [], "grams_per_piece": None},
    "Olives": {"id": 1085, "season_months": [], "grams_per_piece": None},
    # Seasonality is written, not backfilled: import assigns season_months
    # whenever the payload carries the key, so an empty list here would erase
    # what the account knows. Every existing entry repeats the account's value.
    "Capers": {"id": 1108, "season_months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
               "grams_per_piece": None},
    # -- created by this import, by name -------------------------------------
    "Feta": {"id": None, "season_months": [], "grams_per_piece": None},
    "Ricotta": {"id": None, "season_months": [], "grams_per_piece": None},
    "Phyllo Pastry": {"id": None, "season_months": [], "grams_per_piece": 40},
    "Farro": {"id": None, "season_months": [], "grams_per_piece": None},
    "Wholewheat Couscous": {"id": None, "season_months": [], "grams_per_piece": None},
    "Stale Bread": {"id": None, "season_months": [], "grams_per_piece": None},
    "Dill": {"id": None, "season_months": [5, 6, 7, 8, 9], "grams_per_piece": None},
    "Spring Onion": {"id": None, "season_months": [4, 5, 6, 7, 8, 9], "grams_per_piece": 40},
    "Dijon Mustard": {"id": None, "season_months": [], "grams_per_piece": None},
    "Red Wine Vinegar": {"id": None, "season_months": [], "grams_per_piece": None},
    # The account's "Lemon" (953) is stored as ``piece`` but holds millilitres
    # of juice. These recipes do not inherit that and do not correct it: juice
    # is its own ingredient in ml, and 953 is used only for whole fruit.
    "Lemon Juice": {"id": None, "season_months": [], "grams_per_piece": None},
}

NEW_INGREDIENTS = [name for name, e in PANTRY.items() if e["id"] is None]

# Recipes in the source document that the account already has. Importing a
# second row for one of these would split its score history and give the
# planner two candidates it cannot tell apart.
SKIPPED = [
    ("3. Hummus with crudites", "Classic Hummus (75)"),
    ("5. Baba ganoush", "Babaganoush (76)"),
    ("11. Baked courgette and onion frittata", "Zucchini Frittata (70)"),
    ("24. Tomato salad with oregano", "Tomato and Cucumber Salad (91)"),
    ("28. Green salad with lemon vinaigrette", "Green Salad (90)"),
]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_summer_recipes_import.py -v`
Expected: 3 passed.

- [ ] **Step 5: Lint and commit**

```bash
python -m flake8 scripts/summer_recipes_data.py
git add backend/scripts/summer_recipes_data.py backend/tests/test_summer_recipes_import.py
git commit -m "Map the recipes' ingredients onto the account's pantry

An id is asserted against the account snapshot rather than trusted: import
looks an ingredient up by id first, so a wrong one attaches a quantity to an
unrelated ingredient and nothing downstream would notice."
```

---

### Task 3: The 24 recipes

**Files:**
- Modify: `backend/scripts/summer_recipes_data.py` (append `RECIPES`)
- Test: `backend/tests/test_summer_recipes_import.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_summer_recipes_import.py`:

```python
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_summer_recipes_import.py -v`
Expected: FAIL with `ImportError: cannot import name 'RECIPES'`

- [ ] **Step 3: Append the recipes**

Append `RECIPES` to `backend/scripts/summer_recipes_data.py`. Each ingredient line is `(pantry name, quantity, unit)`. Transcribe all 24 from **Appendix A** of this plan — the quantities there are already scaled to four portions and are the authority; the `notes` list must carry every *(chosen)* and *(corrected)* mark from that appendix, because the report is generated from it. The first entry, complete, as the pattern for the other 23:

```python
# ``source`` is the recipe's number in ricettario-estivo-saziante.md.
# ``notes`` records anything the report must disclose: a quantity the source
# did not give, or one this file corrected.
RECIPES = [
    {
        "source": 1,
        "title": "Andalusian Gazpacho",
        "course": "first-course",
        "servings": 4,
        "bulk_prep": True,
        "tags": ["vegan", "no-cook", "make-ahead", "summer", "low calories"],
        "procedure": (
            "Soak the stale bread in the vinegar with a splash of water.\n"
            "Roughly chop the vegetables and blend them with the garlic and "
            "salt, adding water until it is as thick as you want it.\n"
            "With the blender running, pour in the oil.\n"
            "Chill at least two hours. Do not sieve it: the fibre is the point."
        ),
        "ingredients": [
            ("Tomato", 1000, "g"),
            ("Cucumber", 300, "g"),
            ("Bell Pepper", 150, "g"),
            ("Garlic", 5, "g"),
            ("Stale Bread", 50, "g"),
            ("Red Wine Vinegar", 30, "ml"),
            ("Olive Oil", 25, "ml"),
            ("Salt", 5, "g"),
        ],
        "notes": [
            "Cucumber and pepper given as '1 each'; taken as 300 g and 150 g.",
            "'2 tablespoons' of vinegar and oil taken as 30 ml and 25 ml.",
        ],
    },
    # ... the remaining 23, per Appendix A
]
```

Procedures are written fresh in English from the source's method — three to six
short lines each, keeping the technique the source insists on (squeeze the
grated courgettes, drain the roasted aubergine, add the basil off the heat) and
dropping its commentary.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_summer_recipes_import.py -v`
Expected: 8 passed.

- [ ] **Step 5: Lint and commit**

```bash
python -m flake8 scripts/summer_recipes_data.py
git add backend/scripts/summer_recipes_data.py backend/tests/test_summer_recipes_import.py
git commit -m "Transcribe the 24 recipes at four portions

Quantities are scaled from the source and, where it gave none, chosen and
recorded in notes so the report can disclose every invented number."
```

---

### Task 4: Plausibility of the quantities

A schema check passes a recipe that feeds twelve or two. This catches a scaling slip.

**Files:**
- Test: `backend/tests/test_summer_recipes_import.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_summer_recipes_import.py`:

```python
# What four portions of each kind of dish plausibly weighs, in grams, counting
# only the solid and liquid bulk -- seasonings are excluded because a recipe is
# not made implausible by three grams of oregano.
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
            per_piece = PANTRY[name]["grams_per_piece"]
            assert per_piece, f"{recipe['title']}: {name} in pieces with no weight"
            total += quantity * per_piece
    return total


@pytest.mark.parametrize("recipe", RECIPES, ids=lambda r: r["title"])
def test_each_recipe_feeds_four(recipe):
    low, high = SANE_TOTAL_GRAMS[recipe["course"]]
    total = _bulk_grams(recipe)
    assert low <= total <= high, f"{recipe['title']} is {total:.0f} g for four"


def test_oil_is_measured_by_the_spoon():
    """The document's central claim: the oil is what decides whether a plate of
    vegetables is light. Past 40 ml for four, this is not that cookbook."""
    for recipe in RECIPES:
        oil = sum(q for n, q, _ in recipe["ingredients"] if n == "Olive Oil")
        assert oil <= 40, f"{recipe['title']} uses {oil} ml of oil"
```

- [ ] **Step 2: Run it**

Run: `python -m pytest tests/test_summer_recipes_import.py -v`
Expected: 24 parametrised cases plus the oil check, all PASS. If one fails, the quantity in `RECIPES` is wrong — fix the data, not the band.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_summer_recipes_import.py
git commit -m "Check each recipe actually feeds four

Every quantity can be individually legal while the dish as a whole feeds
twelve. The band is on the bulk only, so a gram of oregano cannot move it."
```

---

### Task 5: The builder

**Files:**
- Create: `backend/scripts/build_summer_import.py`
- Test: `backend/tests/test_summer_recipes_import.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_summer_recipes_import.py`:

```python
from scripts.build_summer_import import build_payload


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


def test_existing_ingredients_keep_their_account_id(snapshot):
    by_name = {ing["name"]: ing["id"] for ing in snapshot["ingredients"]}
    for recipe in build_payload()["recipes"]:
        for line in recipe["ingredients"]:
            if line["name"] in by_name:
                assert line["id"] == by_name[line["name"]]
            else:
                assert line["id"] is None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_summer_recipes_import.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.build_summer_import'`

- [ ] **Step 3: Write the builder**

Create `backend/scripts/build_summer_import.py`:

```python
"""Render the summer recipes into an import file and an audit report.

Run from ``backend/``::

    python -m scripts.build_summer_import

Writes ``docs/recipes/summer-recipes-import.json`` (for
``POST /data/import?mode=merge``) and ``docs/recipes/summer-recipes-report.md``.
Both come from ``summer_recipes_data.py``, so a quantity is written once and
the report can never disagree with the file it describes.
"""

import json
from pathlib import Path

from scripts.summer_recipes_data import PANTRY, RECIPES, SKIPPED

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO_ROOT / "docs" / "recipes"
JSON_PATH = OUT_DIR / "summer-recipes-import.json"
REPORT_PATH = OUT_DIR / "summer-recipes-report.md"

# Ids local to this file. Import in merge mode assigns fresh ones and matches
# tags by name, so these only have to be internally consistent -- but they sit
# well clear of the account's range so no reader mistakes them for real ones.
FIRST_RECIPE_ID = 9001
FIRST_TAG_ID = 9101


def _tag_ids():
    """Every tag used, in first-use order, mapped to a local id."""
    order = []
    for recipe in RECIPES:
        for tag in recipe["tags"]:
            if tag not in order:
                order.append(tag)
    return {name: FIRST_TAG_ID + i for i, name in enumerate(order)}


def _ingredient_line(name, quantity, unit):
    entry = PANTRY[name]
    return {
        "id": entry["id"],
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "season_months": entry["season_months"],
        "grams_per_ml": None,
        "grams_per_piece": entry["grams_per_piece"],
        "preferred_dimension": None,
    }


def build_payload():
    tag_ids = _tag_ids()
    recipes = []
    for offset, recipe in enumerate(RECIPES):
        recipes.append({
            "id": FIRST_RECIPE_ID + offset,
            "title": recipe["title"],
            "procedure": recipe["procedure"],
            "bulk_prep": recipe["bulk_prep"],
            "course": recipe["course"],
            "image_url": None,
            "servings": recipe["servings"],
            # Unscored and never eaten: the planner should meet these the way
            # it meets any new recipe, not with a history invented here.
            "score": None,
            "date_last_consumed": None,
            "ingredients": [_ingredient_line(*line) for line in recipe["ingredients"]],
            "tags": [tag_ids[t] for t in recipe["tags"]],
            "favorite_side_ids": [],
        })
    return {
        "recipes": recipes,
        "tags": [{"id": i, "name": n} for n, i in tag_ids.items()],
        "meal_plans": [],
    }


def build_report():
    lines = [
        "# Summer recipes - import report",
        "",
        f"{len(RECIPES)} recipes, written for four portions, for "
        "`POST /data/import?mode=merge`.",
        "",
        "## Skipped as already in the book",
        "",
        "| Source recipe | Already have |",
        "| --- | --- |",
    ]
    lines += [f"| {source} | {existing} |" for source, existing in SKIPPED]
    lines += [
        "",
        "## New pantry entries",
        "",
        ", ".join(n for n, e in PANTRY.items() if e["id"] is None),
        "",
        "## Per recipe",
        "",
    ]
    for recipe in RECIPES:
        lines.append(f"### {recipe['title']}")
        lines.append("")
        keeps = ", keeps (bulk prep)" if recipe["bulk_prep"] else ""
        lines.append(f"Source #{recipe['source']} - {recipe['course']}{keeps}")
        lines.append("")
        lines += [f"- {note}" for note in recipe["notes"]]
        if not recipe["notes"]:
            lines.append("- Taken from the source unchanged.")
        lines.append("")
    return "\n".join(lines)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(
        json.dumps(build_payload(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(build_report(), encoding="utf-8")
    print(f"wrote {JSON_PATH}")
    print(f"wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
```

The module imports its data as `scripts.summer_recipes_data`, matching how the
tests import it, so both need `backend/` on `sys.path` — which `tests/conftest.py`
already arranges for pytest. Run the script as a module from `backend/`:
`python -m scripts.build_summer_import`. If that raises `ModuleNotFoundError:
scripts`, create an empty `backend/scripts/__init__.py` and try again.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_summer_recipes_import.py -v`
Expected: all PASS.

- [ ] **Step 5: Generate the files**

Run: `python -m scripts.build_summer_import`
Expected: two `wrote ...` lines.

- [ ] **Step 6: Lint and commit**

```bash
python -m flake8 scripts/
git add backend/scripts/build_summer_import.py backend/tests/test_summer_recipes_import.py docs/recipes/
git commit -m "Render the recipes into an import file and a report

Both are generated from the one table, so the report cannot drift from the
file it describes."
```

---

### Task 6: Import it for real

The only check that proves the file works is the import path itself.

**Files:**
- Test: `backend/tests/test_summer_recipes_import.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_summer_recipes_import.py`:

```python
import io

import crud
from models import Ingredient, Recipe


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
```

- [ ] **Step 2: Run it**

Run: `docker start mp_test_pg && python -m pytest tests/test_summer_recipes_import.py -v`
Expected: all PASS. A failure here names the exact defect — a duplicate ingredient, an unmeasurable line, or a bad id.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_summer_recipes_import.py
git commit -m "Import the file for real, into a populated account

Structural checks pass files the importer rejects. This runs the actual
crud.import_data merge path against a database holding the account's
ingredients and titles, which is the only thing that proves the file works."
```

---

### Task 7: Full suite, lint, and simplify

- [ ] **Step 1: Run the whole backend suite**

Run: `docker start mp_test_pg && python -m pytest`
Expected: no new failures. Nothing here touches application code, so any failure is either the new test file or pre-existing — check with `git stash` if unsure.

- [ ] **Step 2: Lint**

Run: `python -m flake8 .`
Expected: no output.

- [ ] **Step 3: Confirm the deliverable is current**

```bash
python -m scripts.build_summer_import
git diff --exit-code docs/recipes/
```
Expected: no diff. A diff means the committed file is stale — commit it.

- [ ] **Step 4: Run `/simplify`**

Per `CLAUDE.md`, the last step of every plan. Apply the findings, re-run `python -m pytest tests/test_summer_recipes_import.py` and `python -m flake8 .`, and commit.

- [ ] **Step 5: Hand over**

Report to the user: the path to `docs/recipes/summer-recipes-import.json`, the path to the report, the five skipped recipes, and the reminder that the import must be run with **mode = merge** — `overwrite` would clear the existing 52 recipes.

---

## Appendix A: the 24 recipes at four portions

Quantities are grams unless the unit says otherwise. `Lemon` is whole fruit in pieces; juice is `Lemon Juice` in ml. Every number the source did not give is marked *(chosen)*; every one this file changed is marked *(corrected)*. Both marks must appear in that recipe's `notes`.

### first-course (5)

**1. Andalusian Gazpacho** — bulk_prep · vegan, no-cook, make-ahead, summer, low calories
Tomato 1000 · Cucumber 300 *(chosen: "1 cucumber")* · Bell Pepper 150 *(chosen: "1 pepper")* · Garlic 5 · Stale Bread 50 · Red Wine Vinegar 30 ml · Olive Oil 25 ml · Salt 5

**2. Chilled Courgette and Basil Soup** — vegetarian, summer, make-ahead, low calories
Zucchini 1000 · Onion 150 · Potato 100 · Vegetable Stock 700 ml · Basil 15 · Olive Oil 12 ml · Salt 5 · Greek Yogurt 60

**21. Farro Salad with Roasted Vegetables** — vegetarian, make-ahead, summer, mediterranean
Farro 200 · Eggplant 200 · Zucchini 200 · Bell Pepper 200 · Feta 100 · Basil 5 · Lemon 0.5 piece · Olive Oil 12 ml
*(corrected: the source cross-references "recipe 7" for its roasted vegetables; recipe 7 is a bean purée and the tray is recipe 10. The vegetables are listed here directly.)*

**22. Panzanella** — vegetarian, no-cook, summer, cheap, mediterranean
Stale Bread 150 · Tomato 800 · Cucumber 300 · Red Onion 100 · Basil 10 · Olive Oil 25 ml · Red Wine Vinegar 20 ml · Salt 5

**23. Wholewheat Couscous with Chickpeas and Lemon** — vegan, no-cook, make-ahead, legumes, high-protein
Wholewheat Couscous 180 · Chickpeas 300 · Tomato 250 · Cucumber 300 · Bell Pepper 150 · Spring Onion 40 · Parsley 10 · Basil 8 · Lemon Juice 80 ml · Olive Oil 25 ml · Cumin 3
*(corrected: the source hydrates with "an equal volume of water", a volume-for-weight slip; 180 g of couscous takes about 270 ml. The water is a step in the procedure, not an ingredient line.)*

### main (7)

**9. Aubergines Stuffed with Lentils** — bulk_prep · vegetarian, oven, legumes, high-protein, make-ahead
Eggplant 1200 · Lentils 250 · Onion 150 · Passata 300 · Cumin 3 · Oregano 2 · Olive Oil 25 ml · Feta 40

**10. Tray of Roasted Summer Vegetables** — bulk_prep · vegan, oven, make-ahead, summer, cheap
Eggplant 400 · Zucchini 400 · Bell Pepper 300 · Red Onion 200 · Cherry Tomato 300 · Olive Oil 35 ml · Oregano 3 · Salt 5
*(chosen: the source says "free quantities, fill two trays". These are four portions of it.)*

**12. Courgette and Feta Burek** — vegetarian, oven, phyllo, make-ahead
Phyllo Pastry 4 pieces · Zucchini 533 · Onion 100 · Feta 100 · Ricotta 67 · Egg 1 piece · Dill 5 · Black Pepper 2 · Greek Yogurt 45 · Olive Oil 8 ml
*(corrected: scaling six portions to four gives 0.67 of an egg; rounded up to one.)*

**13. Light Spanakopita** — vegetarian, oven, phyllo, high-protein, make-ahead
Phyllo Pastry 4 pieces · Spinach 533 · Spring Onion 100 · Feta 100 · Ricotta 100 · Egg 1 piece · Dill 7 · Nutmeg 0.5 · Black Pepper 2 · Greek Yogurt 45 · Olive Oil 8 ml
*(corrected: 1.33 eggs rounded down to one.)*

**14. Phyllo Cigars with Aubergine and Feta** — vegetarian, oven, phyllo
Phyllo Pastry 6 pieces · Eggplant 500 · Bell Pepper 150 · Onion 150 · Feta 100 · Parsley 8 · Paprika 3 · Olive Oil 12 ml
*(corrected: this appendix first said 3 sheets. The source recipe is already written for four portions and calls for six sheets cut in half — the twelve cigars its own heading names. Three would have halved the yield.)*

**15. Light Krompirusa** — vegetarian, oven, phyllo, cheap
Phyllo Pastry 4 pieces · Potato 400 · Onion 200 · Zucchini 133 · Parmesan 27 · Black Pepper 4 · Olive Oil 8 ml

**16. Aubergine and Ricotta Involtini** — vegetarian, oven, high-protein, make-ahead
Eggplant 900 · Ricotta 250 · Parmesan 40 · Lemon 0.5 piece · Basil 5 · Passata 400 · Onion 150 · Olive Oil 12 ml

### side (12)

**4. Tzatziki** — vegetarian, no-cook, quick, high-protein, low calories
Greek Yogurt 330 · Cucumber 400 · Garlic 3 · Dill 7 · Olive Oil 8 ml · Salt 3 · Red Wine Vinegar 7 ml

**6. Roasted Pepper and Feta Cream** — bulk_prep · vegetarian, oven, make-ahead, high-protein
Bell Pepper 400 · Feta 100 · Greek Yogurt 67 · Paprika 3 · Red Wine Vinegar 7 ml · Olive Oil 8 ml · Black Pepper 1.5

**7. Cannellini Cream with Garlic and Rosemary** — bulk_prep · vegan, make-ahead, legumes, cheap, high-protein
Cannellini Beans 333 · Garlic 3 · Rosemary 2 · Lemon Juice 13 ml · Olive Oil 10 ml · Salt 2 · Black Pepper 1

**8. Roasted Courgette and Ricotta Cream** — vegetarian, oven, make-ahead
Zucchini 533 · Spring Onion 40 · Ricotta 100 · Parmesan 20 · Lemon 0.5 piece · Basil 5 · Olive Oil 10 ml · Salt 2

**17. Courgettes in Scapece** — bulk_prep · vegan, make-ahead, summer, low calories, cheap
Zucchini 800 · Garlic 10 · White Wine Vinegar 100 ml · Basil 10 · Olive Oil 25 ml · Salt 5

**18. Mediterranean Chickpea Salad** — vegan, no-cook, legumes, high-protein, mediterranean
Chickpeas 500 · Cherry Tomato 300 · Cucumber 300 · Red Onion 80 · Olives 60 · Oregano 2 · Parsley 8 · Lemon Juice 40 ml · Olive Oil 25 ml

**19. Lentil Salad with Red Onion** — bulk_prep · vegan, make-ahead, legumes, high-protein, cheap
Lentils 400 · Red Onion 100 · Cherry Tomato 300 · Parsley 10 · Dijon Mustard 12 · Olive Oil 25 ml · Red Wine Vinegar 20 ml

**20. Cannellini, Rocket and Cherry Tomatoes** — vegan, no-cook, quick, legumes, high-protein
Cannellini Beans 500 · Rocket 100 · Cherry Tomato 300 · Spring Onion 40 · Lemon 0.5 piece · Olive Oil 25 ml · Black Pepper 2

**25. Quick Pickled Cucumbers** — bulk_prep · vegan, no-cook, quick, make-ahead, low calories
Cucumber 600 · White Wine Vinegar 45 ml · Sugar 5 · Salt 3 · Black Pepper 1 · Dill 5

**26. Raw Courgette Ribbons** — vegetarian, no-cook, quick, summer, low calories
Zucchini 500 · Lemon Juice 30 ml · Parmesan 30 · Basil 5 · Olive Oil 10 ml · Salt 3 · Black Pepper 1

**27. Roasted Peppers in Salad** — bulk_prep · vegan, oven, make-ahead, mediterranean, low calories
Bell Pepper 800 · Garlic 8 · Capers 20 · Parsley 8 · Red Wine Vinegar 15 ml · Olive Oil 15 ml · Salt 3
*(note: `Capers` is `ml` in one existing recipe and `g` in another; these lines use `g`.)*

**29. Quick Confit Cherry Tomatoes** — bulk_prep · vegan, oven, make-ahead, summer, cheap
Cherry Tomato 600 · Olive Oil 15 ml · Oregano 2 · Salt 3

### Tag vocabulary

Reused from the account by name: `vegetarian`, `vegan`, `quick`, `cheap`, `low calories`, `mediterranean`.
New: `make-ahead`, `no-cook`, `phyllo`, `high-protein`, `legumes`, `summer`, `oven`.
