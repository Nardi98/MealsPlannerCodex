"""Render the summer recipes into an import file and an audit report.

A one-off, unlike its neighbours in this directory: ``seed_testing_data.py``
and friends are operational tooling that docker-compose and CI run, while this
exists to produce one file for one account and then be left alone.

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
