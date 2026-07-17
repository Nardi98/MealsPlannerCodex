"""Populate the configured database with a dataset for exercising diversity penalties.

Run from ``backend/``::

    python seed_test_data.py

The dataset is deliberately built so the new ingredient- and tag-repetition
penalties are observable: many recipes share the same summer ingredients
(tomato, zucchini, basil) and the same *format* tags (pasta, soup, risotto,
salad, ...), so a good plan should spread those out across the week rather than
serving pasta-with-tomato five times.
"""

from __future__ import annotations

from sqlalchemy import select

from database import SessionLocal, engine
import models
from models import Ingredient, Recipe, RecipeIngredient, UnitEnum
from mealplanner.seed import seed_system_tags, _get_or_create_tag


# Ingredients with July-centric seasonality (today is high summer). A few
# pantry staples are available all year (empty season list).
INGREDIENTS = {
    "Tomato": [6, 7, 8, 9],
    "Zucchini": [6, 7, 8],
    "Basil": [6, 7, 8],
    "Eggplant": [7, 8, 9],
    "Bell Pepper": [7, 8, 9],
    "Green Beans": [6, 7, 8],
    "Potato": [],
    "Onion": [],
    "Garlic": [],
    "Rice": [],
    "Pasta": [],
    "Bread": [],
    "Parmesan": [],
    "Mozzarella": [],
    "Chickpeas": [],
    "Lentils": [],
    "Chicken": [],
    "Beef": [],
    "Olive Oil": [],
    "Lettuce": [5, 6, 7, 8, 9],
    "Cucumber": [6, 7, 8],
    "Egg": [],
}


# (title, course, score, bulk_prep, [ingredient names], [tags])
RECIPES = [
    # --- pasta format, heavy tomato/zucchini overlap ---
    ("Pasta al Pomodoro", "first-course", 4.5, False,
     ["Pasta", "Tomato", "Basil", "Garlic", "Olive Oil"], ["pasta", "vegetarian"]),
    ("Pasta alle Zucchine", "first-course", 4.2, False,
     ["Pasta", "Zucchini", "Parmesan", "Olive Oil"], ["pasta", "vegetarian"]),
    ("Pasta alla Norma", "first-course", 4.0, False,
     ["Pasta", "Tomato", "Eggplant", "Basil"], ["pasta", "vegetarian"]),
    ("Chicken Pasta Bake", "main", 4.3, True,
     ["Pasta", "Chicken", "Tomato", "Mozzarella"], ["pasta"]),

    # --- risotto / rice format ---
    ("Zucchini Risotto", "first-course", 4.1, True,
     ["Rice", "Zucchini", "Onion", "Parmesan"], ["risotto", "vegetarian"]),
    ("Tomato Risotto", "first-course", 3.8, True,
     ["Rice", "Tomato", "Onion", "Basil"], ["risotto", "vegetarian"]),

    # --- soups ---
    ("Minestrone", "first-course", 3.9, True,
     ["Tomato", "Zucchini", "Green Beans", "Potato", "Onion"],
     ["soup", "vegetarian", "vegan"]),
    ("Lentil Soup", "first-course", 3.7, True,
     ["Lentils", "Onion", "Garlic", "Potato"], ["soup", "vegetarian", "vegan"]),

    # --- salads ---
    ("Caprese Salad", "main", 3.6, False,
     ["Tomato", "Mozzarella", "Basil", "Olive Oil"], ["salad", "vegetarian", "quick"]),
    ("Greek Salad", "main", 3.5, False,
     ["Cucumber", "Tomato", "Lettuce", "Olive Oil"], ["salad", "vegetarian", "quick"]),

    # --- mains, mixed formats ---
    ("Roast Chicken", "main", 4.4, True,
     ["Chicken", "Potato", "Garlic", "Olive Oil"], ["roast"]),
    ("Beef Stew", "main", 4.2, True,
     ["Beef", "Potato", "Onion", "Tomato"], ["stew"]),
    ("Chickpea Curry", "main", 4.0, True,
     ["Chickpeas", "Tomato", "Onion", "Garlic"], ["curry", "vegetarian", "vegan"]),
    ("Eggplant Parmigiana", "main", 4.1, True,
     ["Eggplant", "Tomato", "Mozzarella", "Parmesan"], ["vegetarian"]),
    ("Frittata", "main", 3.4, False,
     ["Egg", "Zucchini", "Parmesan"], ["vegetarian", "quick"]),
    ("Grilled Chicken", "main", 3.8, False,
     ["Chicken", "Olive Oil", "Garlic"], ["quick"]),

    # --- sides ---
    ("Green Beans Almondine", "side", 3.2, False,
     ["Green Beans", "Garlic", "Olive Oil"], ["vegetarian", "vegan"]),
    ("Roasted Potatoes", "side", 3.5, False,
     ["Potato", "Olive Oil", "Garlic"], ["vegetarian", "vegan"]),
    ("Bruschetta", "side", 3.0, False,
     ["Bread", "Tomato", "Basil", "Garlic"], ["vegetarian", "quick"]),
    ("Mixed Green Salad", "side", 3.1, False,
     ["Lettuce", "Cucumber", "Olive Oil"], ["salad", "vegetarian", "vegan", "quick"]),
]


def _get_or_create_ingredient(session, name: str) -> Ingredient:
    ing = session.execute(
        select(Ingredient).where(Ingredient.name == name)
    ).scalar_one_or_none()
    if ing is None:
        ing = Ingredient(
            name=name,
            season_months=INGREDIENTS.get(name, []),
            unit=UnitEnum.G,
        )
        session.add(ing)
    return ing


def seed_test_data(session) -> None:
    seed_system_tags(session)  # ensures format tags carry penalize_repetition

    for title, course, score, bulk, ingredients, tags in RECIPES:
        exists = session.execute(
            select(Recipe).where(Recipe.title == title)
        ).scalar_one_or_none()
        if exists is not None:
            continue
        recipe = Recipe(
            title=title,
            servings_default=4,
            procedure=f"Prepare {title}.",
            score=score,
            bulk_prep=bulk,
            course=course,
        )
        session.add(recipe)
        for name in ingredients:
            ing = _get_or_create_ingredient(session, name)
            recipe.ingredients.append(
                RecipeIngredient(ingredient=ing, quantity=100.0, unit=UnitEnum.G)
            )
        for tag_name in tags:
            recipe.tags.append(_get_or_create_tag(session, tag_name))

    session.commit()


if __name__ == "__main__":
    models.Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_test_data(session)
        n_recipes = session.query(Recipe).count()
        n_ing = session.query(Ingredient).count()
    print(f"Seeded database: {n_recipes} recipes, {n_ing} ingredients.")
