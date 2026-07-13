"""Wipe and repopulate the database with a rich set of testing data.

This script is intended to run **every time the Docker containers are
composed** (see ``docker-compose.yml``). It performs a *complete* reset:

1. Drops every table known to ``Base.metadata`` and recreates them, so no
   stale rows (recipes, plans, feedback, ...) survive between runs.
2. Inserts a coherent, self-contained dataset with **at least 40 recipes,
   50 ingredients and 10 tags**, wired together through the
   ``RecipeIngredient`` association objects and the recipe/tag many-to-many.

The data is deterministic (no randomness) so tests and manual QA see the same
database on every ``docker compose up``.

IMPORTANT (for maintainers): whenever the database schema or the domain model
changes, this script MUST be updated so the seeded data stays coherent with the
models. See CLAUDE.md ("Testing data seed") for the rule.

Run from the ``backend/`` directory::

    python scripts/seed_testing_data.py
"""

from __future__ import annotations

import os
import sys

# Allow ``python scripts/seed_testing_data.py`` to resolve the top-level
# ``database`` / ``models`` modules that live at the backend root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import Base, SessionLocal, engine  # noqa: E402
from models import (  # noqa: E402
    Ingredient,
    Recipe,
    RecipeIngredient,
    Tag,
    UnitEnum,
)

# ---------------------------------------------------------------------------
# Ingredients: (name, unit, season_months, categories)  -- 56 entries
# ``season_months`` uses 1-12; an empty list means "available year round".
# ``categories`` are drawn from ``models.CATEGORIES``; an empty list renders
# under the synthetic "Uncategorized" section in the UI.
# NOTE: "Tomato" and "Tomatoes" are an intentional near-duplicate pair (with
# differing units) so the merge tool has something to find in a fresh DB.
# ---------------------------------------------------------------------------
INGREDIENTS: list[tuple[str, UnitEnum, list[int], list[str]]] = [
    ("Spaghetti", UnitEnum.G, [], ["Grains & Pasta", "Carbs"]),
    ("Penne", UnitEnum.G, [], ["Grains & Pasta", "Carbs"]),
    ("Rice", UnitEnum.G, [], ["Grains & Pasta", "Carbs"]),
    ("Arborio Rice", UnitEnum.G, [], ["Grains & Pasta", "Carbs"]),
    ("Bread", UnitEnum.PIECE, [], ["Grains & Pasta", "Carbs"]),
    ("Flour", UnitEnum.G, [], ["Grains & Pasta", "Carbs"]),
    ("Oats", UnitEnum.G, [], ["Grains & Pasta", "Carbs", "Fiber"]),
    ("Potato", UnitEnum.G, [9, 10, 11, 12, 1], ["Vegetables", "Carbs"]),
    ("Sweet Potato", UnitEnum.G, [10, 11, 12], ["Vegetables", "Carbs", "Fiber"]),
    ("Tomato", UnitEnum.G, [6, 7, 8, 9], ["Vegetables"]),
    ("Tomatoes", UnitEnum.PIECE, [6, 7, 8, 9], ["Vegetables"]),
    ("Cherry Tomato", UnitEnum.G, [6, 7, 8, 9], ["Vegetables"]),
    ("Onion", UnitEnum.G, [], ["Vegetables"]),
    ("Garlic", UnitEnum.G, [], ["Vegetables", "Herbs & Spices"]),
    ("Carrot", UnitEnum.G, [], ["Vegetables", "Fiber"]),
    ("Celery", UnitEnum.G, [], ["Vegetables", "Fiber"]),
    ("Zucchini", UnitEnum.G, [6, 7, 8, 9], ["Vegetables"]),
    ("Eggplant", UnitEnum.G, [7, 8, 9], ["Vegetables"]),
    ("Bell Pepper", UnitEnum.G, [7, 8, 9], ["Vegetables"]),
    ("Spinach", UnitEnum.G, [3, 4, 5, 10, 11], ["Vegetables", "Fiber"]),
    ("Broccoli", UnitEnum.G, [10, 11, 12, 1, 2], ["Vegetables", "Fiber"]),
    ("Cauliflower", UnitEnum.G, [10, 11, 12, 1], ["Vegetables", "Fiber"]),
    ("Green Beans", UnitEnum.G, [6, 7, 8], ["Vegetables", "Fiber"]),
    ("Peas", UnitEnum.G, [4, 5, 6], ["Legumes", "Fiber", "Plant-based"]),
    ("Mushroom", UnitEnum.G, [9, 10, 11], ["Vegetables"]),
    ("Pumpkin", UnitEnum.G, [10, 11, 12], ["Vegetables", "Fiber"]),
    ("Lettuce", UnitEnum.G, [4, 5, 6, 9, 10], ["Vegetables"]),
    ("Cucumber", UnitEnum.G, [6, 7, 8], ["Vegetables"]),
    ("Cabbage", UnitEnum.G, [11, 12, 1, 2], ["Vegetables", "Fiber"]),
    ("Chickpeas", UnitEnum.G, [], ["Legumes", "Protein", "Fiber", "Plant-based"]),
    ("Lentils", UnitEnum.G, [], ["Legumes", "Protein", "Fiber", "Plant-based"]),
    ("Black Beans", UnitEnum.G, [], ["Legumes", "Protein", "Fiber", "Plant-based"]),
    ("Kidney Beans", UnitEnum.G, [], ["Legumes", "Protein", "Fiber", "Plant-based"]),
    ("Chicken Breast", UnitEnum.G, [], ["Meat", "Protein"]),
    ("Chicken Thigh", UnitEnum.G, [], ["Meat", "Protein"]),
    ("Ground Beef", UnitEnum.G, [], ["Meat", "Protein", "High-calorie"]),
    ("Beef Steak", UnitEnum.G, [], ["Meat", "Protein", "High-calorie"]),
    ("Pork Loin", UnitEnum.G, [], ["Meat", "Protein"]),
    ("Sausage", UnitEnum.G, [], ["Meat", "Protein", "High-calorie"]),
    ("Bacon", UnitEnum.G, [], ["Meat", "Protein", "High-calorie"]),
    ("Salmon", UnitEnum.G, [], ["Fish", "Protein"]),
    ("Tuna", UnitEnum.G, [], ["Fish", "Protein"]),
    ("Shrimp", UnitEnum.G, [], ["Fish", "Protein"]),
    ("Egg", UnitEnum.PIECE, [], ["Dairy & Eggs", "Protein"]),
    ("Milk", UnitEnum.ML, [], ["Dairy & Eggs", "Beverages"]),
    ("Butter", UnitEnum.G, [], ["Dairy & Eggs", "High-calorie"]),
    ("Cheddar Cheese", UnitEnum.G, [], ["Dairy & Eggs", "Protein", "High-calorie"]),
    ("Parmesan", UnitEnum.G, [], ["Dairy & Eggs", "Protein", "High-calorie"]),
    ("Mozzarella", UnitEnum.G, [], ["Dairy & Eggs", "Protein"]),
    ("Yogurt", UnitEnum.G, [], ["Dairy & Eggs", "Protein"]),
    ("Olive Oil", UnitEnum.ML, [], ["Condiments & Oils", "High-calorie"]),
    ("Basil", UnitEnum.G, [6, 7, 8, 9], ["Herbs & Spices", "Plant-based"]),
    ("Parsley", UnitEnum.G, [], ["Herbs & Spices", "Plant-based"]),
    ("Soy Sauce", UnitEnum.ML, [], ["Condiments & Oils"]),
    ("Coconut Milk", UnitEnum.ML, [], ["Beverages", "High-calorie", "Plant-based"]),
    ("Curry Paste", UnitEnum.G, [], []),
    ("Baking Soda", UnitEnum.G, [], []),
]

# ---------------------------------------------------------------------------
# Tags: (name, penalize_repetition, is_system)  -- 14 entries (>= 10 required)
# "Format" tags carry the recency repetition penalty; attribute tags do not.
# ---------------------------------------------------------------------------
TAGS: list[tuple[str, bool, bool]] = [
    ("pasta", True, True),
    ("soup", True, True),
    ("risotto", True, True),
    ("rice", True, True),
    ("salad", True, True),
    ("stew", True, True),
    ("roast", True, True),
    ("curry", True, True),
    ("vegetarian", False, True),
    ("vegan", False, True),
    ("quick", False, True),
    ("cheap", False, True),
    ("spicy", False, True),
    ("breakfast", False, True),
]

# ---------------------------------------------------------------------------
# Recipes: (title, servings, course, bulk_prep, ingredients, tags)
#   ingredients: list of (ingredient_name, quantity, unit)
# 44 entries (>= 40 required). Ingredient names must exist in INGREDIENTS.
# ---------------------------------------------------------------------------
RECIPES: list[tuple[str, int, str, bool, list[tuple[str, float, UnitEnum]], list[str]]] = [
    ("Spaghetti Pomodoro", 2, "first-course", False,
     [("Spaghetti", 200, UnitEnum.G), ("Tomato", 300, UnitEnum.G),
      ("Garlic", 10, UnitEnum.G), ("Basil", 10, UnitEnum.G),
      ("Olive Oil", 20, UnitEnum.ML)], ["pasta", "vegetarian"]),
    ("Penne Arrabbiata", 2, "first-course", False,
     [("Penne", 200, UnitEnum.G), ("Tomato", 300, UnitEnum.G),
      ("Garlic", 10, UnitEnum.G)], ["pasta", "vegetarian", "spicy"]),
    ("Spaghetti Carbonara", 2, "first-course", False,
     [("Spaghetti", 200, UnitEnum.G), ("Egg", 2, UnitEnum.PIECE),
      ("Bacon", 100, UnitEnum.G), ("Parmesan", 50, UnitEnum.G)], ["pasta"]),
    ("Mushroom Risotto", 2, "first-course", False,
     [("Arborio Rice", 200, UnitEnum.G), ("Mushroom", 200, UnitEnum.G),
      ("Onion", 50, UnitEnum.G), ("Parmesan", 40, UnitEnum.G)],
     ["risotto", "vegetarian"]),
    ("Pumpkin Risotto", 2, "first-course", False,
     [("Arborio Rice", 200, UnitEnum.G), ("Pumpkin", 250, UnitEnum.G),
      ("Onion", 50, UnitEnum.G)], ["risotto", "vegetarian"]),
    ("Minestrone Soup", 4, "first-course", True,
     [("Carrot", 100, UnitEnum.G), ("Celery", 100, UnitEnum.G),
      ("Potato", 150, UnitEnum.G), ("Cabbage", 100, UnitEnum.G),
      ("Kidney Beans", 150, UnitEnum.G)], ["soup", "vegetarian", "cheap"]),
    ("Lentil Soup", 4, "first-course", True,
     [("Lentils", 250, UnitEnum.G), ("Carrot", 100, UnitEnum.G),
      ("Onion", 50, UnitEnum.G)], ["soup", "vegan", "cheap"]),
    ("Chicken Noodle Soup", 4, "first-course", True,
     [("Chicken Breast", 200, UnitEnum.G), ("Carrot", 100, UnitEnum.G),
      ("Celery", 80, UnitEnum.G), ("Spaghetti", 100, UnitEnum.G)], ["soup"]),
    ("Grilled Chicken Breast", 2, "main", False,
     [("Chicken Breast", 300, UnitEnum.G), ("Olive Oil", 15, UnitEnum.ML)],
     ["quick"]),
    ("Roast Chicken", 4, "main", True,
     [("Chicken Thigh", 600, UnitEnum.G), ("Potato", 400, UnitEnum.G),
      ("Garlic", 20, UnitEnum.G)], ["roast"]),
    ("Beef Stew", 4, "main", True,
     [("Beef Steak", 500, UnitEnum.G), ("Carrot", 150, UnitEnum.G),
      ("Potato", 300, UnitEnum.G), ("Onion", 100, UnitEnum.G)],
     ["stew", "cheap"]),
    ("Beef Chili", 4, "main", True,
     [("Ground Beef", 400, UnitEnum.G), ("Kidney Beans", 200, UnitEnum.G),
      ("Tomato", 300, UnitEnum.G)], ["stew", "spicy"]),
    ("Chicken Curry", 4, "main", True,
     [("Chicken Thigh", 400, UnitEnum.G), ("Coconut Milk", 200, UnitEnum.ML),
      ("Curry Paste", 40, UnitEnum.G), ("Onion", 80, UnitEnum.G)],
     ["curry", "spicy"]),
    ("Chickpea Curry", 4, "main", True,
     [("Chickpeas", 300, UnitEnum.G), ("Coconut Milk", 200, UnitEnum.ML),
      ("Curry Paste", 40, UnitEnum.G), ("Spinach", 100, UnitEnum.G)],
     ["curry", "vegan", "spicy"]),
    ("Pork Loin Roast", 4, "main", True,
     [("Pork Loin", 600, UnitEnum.G), ("Potato", 400, UnitEnum.G)], ["roast"]),
    ("Grilled Salmon", 2, "main", False,
     [("Salmon", 300, UnitEnum.G), ("Olive Oil", 15, UnitEnum.ML)], ["quick"]),
    ("Tuna Salad", 2, "main", False,
     [("Tuna", 150, UnitEnum.G), ("Lettuce", 100, UnitEnum.G),
      ("Cherry Tomato", 100, UnitEnum.G)], ["salad", "quick"]),
    ("Shrimp Stir Fry", 2, "main", False,
     [("Shrimp", 250, UnitEnum.G), ("Bell Pepper", 100, UnitEnum.G),
      ("Soy Sauce", 30, UnitEnum.ML), ("Rice", 150, UnitEnum.G)], ["quick"]),
    ("Fried Rice", 2, "main", False,
     [("Rice", 250, UnitEnum.G), ("Egg", 2, UnitEnum.PIECE),
      ("Peas", 80, UnitEnum.G), ("Soy Sauce", 30, UnitEnum.ML)],
     ["rice", "quick", "cheap"]),
    ("Vegetable Curry", 4, "main", True,
     [("Cauliflower", 200, UnitEnum.G), ("Potato", 200, UnitEnum.G),
      ("Peas", 100, UnitEnum.G), ("Curry Paste", 40, UnitEnum.G)],
     ["curry", "vegan"]),
    ("Caprese Salad", 2, "side", False,
     [("Tomato", 200, UnitEnum.G), ("Mozzarella", 150, UnitEnum.G),
      ("Basil", 10, UnitEnum.G)], ["salad", "vegetarian", "quick"]),
    ("Greek Salad", 2, "side", False,
     [("Cucumber", 150, UnitEnum.G), ("Tomato", 150, UnitEnum.G),
      ("Lettuce", 80, UnitEnum.G)], ["salad", "vegetarian"]),
    ("Roasted Vegetables", 4, "side", False,
     [("Zucchini", 150, UnitEnum.G), ("Eggplant", 150, UnitEnum.G),
      ("Bell Pepper", 150, UnitEnum.G)], ["roast", "vegan"]),
    ("Mashed Potatoes", 4, "side", False,
     [("Potato", 500, UnitEnum.G), ("Butter", 40, UnitEnum.G),
      ("Milk", 100, UnitEnum.ML)], ["vegetarian"]),
    ("Steamed Broccoli", 2, "side", False,
     [("Broccoli", 250, UnitEnum.G)], ["vegan", "quick"]),
    ("Garlic Green Beans", 2, "side", False,
     [("Green Beans", 250, UnitEnum.G), ("Garlic", 10, UnitEnum.G)],
     ["vegan", "quick"]),
    ("Oatmeal", 1, "first-course", False,
     [("Oats", 100, UnitEnum.G), ("Milk", 250, UnitEnum.ML)],
     ["breakfast", "vegetarian"]),
    ("Scrambled Eggs", 1, "main", False,
     [("Egg", 3, UnitEnum.PIECE), ("Butter", 15, UnitEnum.G)],
     ["breakfast", "quick", "vegetarian"]),
    ("Grilled Cheese", 1, "main", False,
     [("Bread", 2, UnitEnum.PIECE), ("Cheddar Cheese", 60, UnitEnum.G),
      ("Butter", 15, UnitEnum.G)], ["quick", "vegetarian"]),
    ("Yogurt Parfait", 1, "first-course", False,
     [("Yogurt", 200, UnitEnum.G), ("Oats", 40, UnitEnum.G)],
     ["breakfast", "vegetarian", "quick"]),
    ("Pasta Primavera", 2, "first-course", False,
     [("Penne", 200, UnitEnum.G), ("Zucchini", 100, UnitEnum.G),
      ("Peas", 80, UnitEnum.G), ("Parmesan", 30, UnitEnum.G)],
     ["pasta", "vegetarian"]),
    ("Eggplant Parmigiana", 4, "main", True,
     [("Eggplant", 400, UnitEnum.G), ("Tomato", 300, UnitEnum.G),
      ("Mozzarella", 150, UnitEnum.G), ("Parmesan", 50, UnitEnum.G)],
     ["vegetarian"]),
    ("Stuffed Bell Peppers", 4, "main", True,
     [("Bell Pepper", 400, UnitEnum.G), ("Rice", 150, UnitEnum.G),
      ("Ground Beef", 200, UnitEnum.G)], ["stew"]),
    ("Black Bean Tacos", 2, "main", False,
     [("Black Beans", 200, UnitEnum.G), ("Bread", 2, UnitEnum.PIECE),
      ("Bell Pepper", 80, UnitEnum.G)], ["vegan", "quick", "cheap"]),
    ("Sausage and Peppers", 2, "main", False,
     [("Sausage", 300, UnitEnum.G), ("Bell Pepper", 200, UnitEnum.G),
      ("Onion", 100, UnitEnum.G)], ["quick"]),
    ("Salmon Rice Bowl", 2, "main", False,
     [("Salmon", 250, UnitEnum.G), ("Rice", 200, UnitEnum.G),
      ("Soy Sauce", 20, UnitEnum.ML)], ["rice"]),
    ("Pumpkin Soup", 4, "first-course", True,
     [("Pumpkin", 500, UnitEnum.G), ("Onion", 80, UnitEnum.G),
      ("Coconut Milk", 150, UnitEnum.ML)], ["soup", "vegan"]),
    ("Broccoli Cheddar Soup", 4, "first-course", True,
     [("Broccoli", 300, UnitEnum.G), ("Cheddar Cheese", 100, UnitEnum.G),
      ("Milk", 200, UnitEnum.ML)], ["soup", "vegetarian"]),
    ("Spinach Risotto", 2, "first-course", False,
     [("Arborio Rice", 200, UnitEnum.G), ("Spinach", 150, UnitEnum.G),
      ("Parmesan", 40, UnitEnum.G)], ["risotto", "vegetarian"]),
    ("Beef Steak with Potatoes", 2, "main", False,
     [("Beef Steak", 300, UnitEnum.G), ("Potato", 300, UnitEnum.G)], ["roast"]),
    ("Cauliflower Curry", 4, "main", True,
     [("Cauliflower", 300, UnitEnum.G), ("Chickpeas", 150, UnitEnum.G),
      ("Curry Paste", 40, UnitEnum.G)], ["curry", "vegan", "spicy"]),
    ("Coleslaw", 4, "side", False,
     [("Cabbage", 300, UnitEnum.G), ("Carrot", 100, UnitEnum.G),
      ("Yogurt", 80, UnitEnum.G)], ["salad", "vegetarian"]),
    ("Sweet Potato Mash", 4, "side", False,
     [("Sweet Potato", 500, UnitEnum.G), ("Butter", 30, UnitEnum.G)],
     ["vegetarian"]),
    ("Tomato Basil Soup", 4, "first-course", True,
     [("Tomato", 500, UnitEnum.G), ("Basil", 15, UnitEnum.G),
      ("Onion", 80, UnitEnum.G)], ["soup", "vegan", "cheap"]),
]


def reset_database() -> None:
    """Drop every table and recreate a clean schema from the models."""

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def populate(session) -> None:
    """Insert the full testing dataset into an empty database."""

    tags: dict[str, Tag] = {}
    for name, penalize, is_system in TAGS:
        tag = Tag(name=name, penalize_repetition=penalize, is_system=is_system)
        session.add(tag)
        tags[name] = tag

    ingredients: dict[str, Ingredient] = {}
    for name, unit, months, categories in INGREDIENTS:
        ing = Ingredient(
            name=name, unit=unit, season_months=months, categories=categories
        )
        session.add(ing)
        ingredients[name] = ing

    for title, servings, course, bulk, ing_list, tag_list in RECIPES:
        recipe = Recipe(
            title=title,
            servings_default=servings,
            procedure=f"Prepare {title.lower()}.",
            course=course,
            bulk_prep=bulk,
        )
        for ing_name, qty, unit in ing_list:
            recipe.ingredients.append(
                RecipeIngredient(
                    ingredient=ingredients[ing_name], quantity=qty, unit=unit
                )
            )
        for tag_name in tag_list:
            recipe.tags.append(tags[tag_name])
        session.add(recipe)

    session.commit()


def main() -> None:
    reset_database()
    session = SessionLocal()
    try:
        populate(session)
        n_r = session.query(Recipe).count()
        n_i = session.query(Ingredient).count()
        n_t = session.query(Tag).count()
    finally:
        session.close()
    print(
        f"[seed_testing_data] Database reset and populated: "
        f"{n_r} recipes, {n_i} ingredients, {n_t} tags."
    )


if __name__ == "__main__":
    main()
