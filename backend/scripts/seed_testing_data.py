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

import hashlib
import os
import sys
from datetime import datetime, timedelta
from typing import NamedTuple

# Allow ``python scripts/seed_testing_data.py`` to resolve the top-level
# ``database`` / ``models`` modules that live at the backend root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import Base, SessionLocal, engine  # noqa: E402
from models import (  # noqa: E402
    Ingredient,
    Recipe,
    RecipeIngredient,
    RecipeShare,
    Tag,
    User,
    UnitEnum,
)
from auth_users import hash_password  # noqa: E402
import usernames  # noqa: E402

# Default seed account. It owns the recipe catalogue below; it starts on the
# shared ``DEFAULT_PLAN_SETTINGS`` (``User.plan_settings`` stays NULL until the
# account overrides something).
DEMO_USER_EMAIL = "demo@mealplanner.test"
DEMO_USER_PASSWORD = "demo1234"
DEMO_USER_USERNAME = "demo_chef"

# Two further accounts so the sharing states below have somewhere to point
# (DM-1). ``friend`` receives a person-mode share and holds the copy; ``guest``
# exists so "a different signed-in account" (SH-24) is reproducible by hand.
FRIEND_USER_EMAIL = "friend@mealplanner.test"
FRIEND_USER_USERNAME = "friend_cook"
GUEST_USER_EMAIL = "guest@mealplanner.test"
GUEST_USER_USERNAME = "guest_cook"

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
    ("meat", False, True),
    ("quick", False, True),
    ("cheap", False, True),
    ("spicy", False, True),
    ("breakfast", False, True),
]

# ---------------------------------------------------------------------------
# Recipes. 44 entries (>= 40 required). Ingredient names must exist in
# INGREDIENTS. Rows are a NamedTuple so consumers (notably
# ``seed_user_data.py``) read fields by name and survive a field being added
# here -- the schema mandate in CLAUDE.md makes that a routine edit.
# ---------------------------------------------------------------------------


def link_favorite_sides(recipes_by_title: dict[str, "Recipe"]) -> None:
    """Wire up :data:`FAVORITE_SIDES` across the recipes actually inserted.

    Runs after every recipe exists, since a pairing points at another recipe.
    Titles absent from ``recipes_by_title`` are skipped rather than raising: a
    profile seeding a subset of the catalogue (the vegetarian one drops the meat
    mains) must still end up with a coherent set of pairings.
    """
    for main_title, side_titles in FAVORITE_SIDES.items():
        main = recipes_by_title.get(main_title)
        if main is None:
            continue
        main.favorite_sides = [
            recipes_by_title[side_title]
            for side_title in side_titles
            if side_title in recipes_by_title
        ]


class SeedShare(NamedTuple):
    """One row of :data:`SHARES`, resolved against the inserted recipes.

    ``token`` is the plaintext a QA walkthrough pastes into the browser; only
    its SHA-256 digest is stored (SH-3, D-5), exactly as the runtime path will
    do. These are seed fixtures, not credentials to anything real.

    ``expires_in_days`` and ``revoked_days_ago`` are relative so a database
    seeded weeks ago still shows the same active / expired / revoked mix.
    """

    recipe_title: str
    token: str
    mode: str
    recipient: str | None = None       # username of the recipient account
    recipient_email: str | None = None
    expires_in_days: int | None = None
    revoked_days_ago: int | None = None


class SeedCopy(NamedTuple):
    """One copy of a shared recipe, carrying its AT-1 attribution snapshot."""

    source_title: str
    copier: str        # username of the copying account
    new_title: str


# DM-1's required states, one row each. Kept beside ``RECIPES`` rather than as
# extra tuple fields for the same reason as ``FAVORITE_SIDES``: the 44 catalogue
# rows stay untouched and readable, and adding a share means adding one line.
SHARES: list[SeedShare] = [
    # Active link share: anyone holding the URL can read it (SH-4).
    SeedShare("Beef Stew", "seed-link-token-beef-stew", "link"),
    # Active person share to an account, so it lands in their Shared-with-me.
    SeedShare(
        "Chicken Curry",
        "seed-person-token-chicken-curry",
        "person",
        recipient=FRIEND_USER_USERNAME,
    ),
    # Active person share to an address with no account: openable only once
    # that address signs up and verifies (the accepted residual of SH-4).
    SeedShare(
        "Pumpkin Soup",
        "seed-person-token-pumpkin-soup",
        "person",
        recipient_email="nobody@mealplanner.test",
    ),
    # Expired: treated exactly as revoked (SH-21).
    SeedShare(
        "Lentil Soup", "seed-expired-token-lentil-soup", "link", expires_in_days=-3
    ),
    # Revoked: the recipe is back to ``private`` (VIS-7).
    SeedShare(
        "Fried Rice", "seed-revoked-token-fried-rice", "link", revoked_days_ago=2
    ),
]

# One copy, so attribution (AT-1/AT-3) and the owner's "copied N times" counter
# (AT-7) are both demoable from a fresh database.
COPIES: list[SeedCopy] = [
    SeedCopy("Chicken Curry", FRIEND_USER_USERNAME, "Chicken Curry"),
]


def _digest(token: str) -> str:
    """The stored form of a share token: a SHA-256 hex digest (D-5)."""
    return hashlib.sha256(token.encode()).hexdigest()


def link_shares(
    session,
    recipes_by_title: dict[str, "Recipe"],
    users_by_username: dict[str, "User"],
    owner: "User",
    now: datetime | None = None,
) -> None:
    """Insert :data:`SHARES` and promote every actively-shared recipe (VIS-6).

    Runs after every recipe exists, like :func:`link_favorite_sides`. Titles the
    caller did not insert are skipped rather than raising.
    """
    now = now or datetime.utcnow()
    for spec in SHARES:
        recipe = recipes_by_title.get(spec.recipe_title)
        if recipe is None:
            continue
        recipient = users_by_username.get(spec.recipient or "")
        expires_at = (
            now + timedelta(days=spec.expires_in_days)
            if spec.expires_in_days is not None
            else None
        )
        revoked_at = (
            now - timedelta(days=spec.revoked_days_ago)
            if spec.revoked_days_ago is not None
            else None
        )
        session.add(
            RecipeShare(
                recipe=recipe,
                created_by_user_id=owner.id,
                token_hash=_digest(spec.token),
                mode=spec.mode,
                recipient_user_id=recipient.id if recipient else None,
                recipient_email=spec.recipient_email,
                expires_at=expires_at,
                revoked_at=revoked_at,
                last_viewed_at=None,
            )
        )
        # VIS-6: an active share promotes a private recipe to unlisted. An
        # expired or revoked one does not (VIS-7 leaves it private).
        active = revoked_at is None and (expires_at is None or expires_at > now)
        if active:
            recipe.visibility = "unlisted"


def link_copies(
    session,
    recipes_by_title: dict[str, "Recipe"],
    users_by_username: dict[str, "User"],
    ingredients: dict[str, "Ingredient"],
    owner: "User",
    now: datetime | None = None,
) -> None:
    """Insert :data:`COPIES` as independent recipes carrying attribution.

    Mirrors what the Phase 2A copy path will do: the copy is private (CP-4),
    owned by the copier with its own ingredient rows in *their* namespace
    (CP-2/CP-3), carries no planner history (CP-7), snapshots the immediate
    source (AT-1), and bumps the source's counter (AT-7).
    """
    now = now or datetime.utcnow()
    for spec in COPIES:
        source = recipes_by_title.get(spec.source_title)
        copier = users_by_username.get(spec.copier)
        if source is None or copier is None:
            continue

        copy = Recipe(
            title=spec.new_title,
            procedure=source.procedure,
            course=source.course,
            bulk_prep=source.bulk_prep,
            # Quantities below are copied verbatim, so their basis comes too.
            servings=source.servings,
            user_id=copier.id,
            visibility="private",
            copy_count=0,
            source_recipe_id=source.id,
            source_user_id=owner.id,
            source_author_username=owner.username,
            source_recipe_title=source.title,
            copied_at=now,
        )
        for item in source.ingredients:
            name = item.ingredient.name
            # CP-3: resolve by *name* inside the copier's namespace. Reusing the
            # source owner's ``Ingredient`` row would be the cross-user leak the
            # requirement exists to prevent.
            own = session.query(Ingredient).filter_by(
                name=name, user_id=copier.id
            ).one_or_none()
            if own is None:
                template = ingredients[name]
                own = Ingredient(
                    name=name,
                    unit=template.unit,
                    season_months=template.season_months,
                    categories=template.categories,
                    user_id=copier.id,
                )
                session.add(own)
            copy.ingredients.append(
                RecipeIngredient(
                    ingredient=own, quantity=item.quantity, unit=item.unit
                )
            )
        session.add(copy)
        source.copy_count += 1


class SeedRecipe(NamedTuple):
    title: str
    course: str
    bulk_prep: bool
    ingredients: list[tuple[str, float, UnitEnum]]
    tags: list[str]
    # How many people the quantities above are written for. Most rows are
    # authored per person and so leave this at 1; the few written for a family
    # say so, which is what real recipes look like and what readers divide by.
    servings: int = 1


# The sides each main is habitually served with. Kept beside ``RECIPES`` rather
# than as another tuple field so the pairings stay readable and adding one
# doesn't mean touching every recipe row. Titles are resolved against whatever
# recipes a given seed actually inserts, so a profile owning a slice of the
# catalogue simply gets fewer pairings.
FAVORITE_SIDES: dict[str, tuple[str, ...]] = {
    "Roast Chicken": ("Roasted Vegetables", "Mashed Potatoes"),
    "Pork Loin Roast": ("Mashed Potatoes", "Steamed Broccoli"),
    "Grilled Chicken Breast": ("Greek Salad", "Steamed Broccoli"),
    "Grilled Salmon": ("Garlic Green Beans", "Steamed Broccoli"),
    "Beef Stew": ("Mashed Potatoes",),
    "Beef Chili": ("Coleslaw",),
    "Sausage and Peppers": ("Mashed Potatoes", "Coleslaw"),
    "Eggplant Parmigiana": ("Caprese Salad", "Greek Salad"),
    "Stuffed Bell Peppers": ("Greek Salad", "Roasted Vegetables"),
    "Chicken Curry": ("Sweet Potato Mash",),
    "Chickpea Curry": ("Sweet Potato Mash", "Steamed Broccoli"),
    "Black Bean Tacos": ("Coleslaw",),
}


RECIPES: list[SeedRecipe] = [SeedRecipe(*row) for row in [
    ('Spaghetti Pomodoro', 'first-course', False,
     [("Spaghetti", 100, UnitEnum.G), ("Tomato", 150, UnitEnum.G),
      ("Garlic", 5, UnitEnum.G), ("Basil", 5, UnitEnum.G),
      ("Olive Oil", 10, UnitEnum.ML)],
     ['pasta', 'vegetarian']),
    ('Penne Arrabbiata', 'first-course', False,
     [("Penne", 100, UnitEnum.G), ("Tomato", 150, UnitEnum.G),
      ("Garlic", 5, UnitEnum.G)],
     ['pasta', 'vegetarian', 'spicy']),
    # Written for four: a quarter of an egg is not a thing anyone measures.
    ('Spaghetti Carbonara', 'first-course', False,
     [("Spaghetti", 400, UnitEnum.G), ("Egg", 4, UnitEnum.PIECE),
      ("Bacon", 200, UnitEnum.G), ("Parmesan", 100, UnitEnum.G)],
     ['pasta'], 4),
    ('Mushroom Risotto', 'first-course', False,
     [("Arborio Rice", 100, UnitEnum.G), ("Mushroom", 100, UnitEnum.G),
      ("Onion", 25, UnitEnum.G), ("Parmesan", 20, UnitEnum.G)],
     ['risotto', 'vegetarian']),
    ('Pumpkin Risotto', 'first-course', False,
     [("Arborio Rice", 100, UnitEnum.G), ("Pumpkin", 125, UnitEnum.G),
      ("Onion", 25, UnitEnum.G)],
     ['risotto', 'vegetarian']),
    ('Minestrone Soup', 'first-course', True,
     [("Carrot", 25, UnitEnum.G), ("Celery", 25, UnitEnum.G),
      ("Potato", 37.5, UnitEnum.G), ("Cabbage", 25, UnitEnum.G),
      ("Kidney Beans", 37.5, UnitEnum.G)],
     ['soup', 'vegetarian', 'cheap']),
    ('Lentil Soup', 'first-course', True,
     [("Lentils", 62.5, UnitEnum.G), ("Carrot", 25, UnitEnum.G),
      ("Onion", 12.5, UnitEnum.G)],
     ['soup', 'vegan', 'cheap']),
    ('Chicken Noodle Soup', 'first-course', True,
     [("Chicken Breast", 50, UnitEnum.G), ("Carrot", 25, UnitEnum.G),
      ("Celery", 20, UnitEnum.G), ("Spaghetti", 25, UnitEnum.G)],
     ['soup']),
    ('Grilled Chicken Breast', 'main', False,
     [("Chicken Breast", 150, UnitEnum.G), ("Olive Oil", 7.5, UnitEnum.ML)],
     ['quick']),
    ('Roast Chicken', 'main', True,
     [("Chicken Thigh", 150, UnitEnum.G), ("Potato", 100, UnitEnum.G),
      ("Garlic", 5, UnitEnum.G)],
     ['roast']),
    # A pot dish, written for the pot rather than in awkward fractions.
    ('Beef Stew', 'main', True,
     [("Beef Steak", 500, UnitEnum.G), ("Carrot", 150, UnitEnum.G),
      ("Potato", 300, UnitEnum.G), ("Onion", 100, UnitEnum.G)],
     ['stew', 'cheap'], 4),
    ('Beef Chili', 'main', True,
     [("Ground Beef", 100, UnitEnum.G), ("Kidney Beans", 50, UnitEnum.G),
      ("Tomato", 75, UnitEnum.G)],
     ['stew', 'spicy']),
    ('Chicken Curry', 'main', True,
     [("Chicken Thigh", 100, UnitEnum.G), ("Coconut Milk", 50, UnitEnum.ML),
      ("Curry Paste", 10, UnitEnum.G), ("Onion", 20, UnitEnum.G)],
     ['curry', 'spicy']),
    ('Chickpea Curry', 'main', True,
     [("Chickpeas", 75, UnitEnum.G), ("Coconut Milk", 50, UnitEnum.ML),
      ("Curry Paste", 10, UnitEnum.G), ("Spinach", 25, UnitEnum.G)],
     ['curry', 'vegan', 'spicy']),
    ('Pork Loin Roast', 'main', True,
     [("Pork Loin", 150, UnitEnum.G), ("Potato", 100, UnitEnum.G)],
     ['roast']),
    ('Grilled Salmon', 'main', False,
     [("Salmon", 150, UnitEnum.G), ("Olive Oil", 7.5, UnitEnum.ML)],
     ['quick']),
    ('Tuna Salad', 'main', False,
     [("Tuna", 75, UnitEnum.G), ("Lettuce", 50, UnitEnum.G),
      ("Cherry Tomato", 50, UnitEnum.G)],
     ['salad', 'quick']),
    ('Shrimp Stir Fry', 'main', False,
     [("Shrimp", 125, UnitEnum.G), ("Bell Pepper", 50, UnitEnum.G),
      ("Soy Sauce", 15, UnitEnum.ML), ("Rice", 75, UnitEnum.G)],
     ['quick']),
    ('Fried Rice', 'main', False,
     [("Rice", 125, UnitEnum.G), ("Egg", 1, UnitEnum.PIECE),
      ("Peas", 40, UnitEnum.G), ("Soy Sauce", 15, UnitEnum.ML)],
     ['rice', 'quick', 'cheap']),
    ('Vegetable Curry', 'main', True,
     [("Cauliflower", 50, UnitEnum.G), ("Potato", 50, UnitEnum.G),
      ("Peas", 25, UnitEnum.G), ("Curry Paste", 10, UnitEnum.G)],
     ['curry', 'vegan']),
    ('Caprese Salad', 'side', False,
     [("Tomato", 100, UnitEnum.G), ("Mozzarella", 75, UnitEnum.G),
      ("Basil", 5, UnitEnum.G)],
     ['salad', 'vegetarian', 'quick']),
    ('Greek Salad', 'side', False,
     [("Cucumber", 75, UnitEnum.G), ("Tomato", 75, UnitEnum.G),
      ("Lettuce", 40, UnitEnum.G)],
     ['salad', 'vegetarian']),
    ('Roasted Vegetables', 'side', False,
     [("Zucchini", 37.5, UnitEnum.G), ("Eggplant", 37.5, UnitEnum.G),
      ("Bell Pepper", 37.5, UnitEnum.G)],
     ['roast', 'vegan']),
    ('Mashed Potatoes', 'side', False,
     [("Potato", 125, UnitEnum.G), ("Butter", 10, UnitEnum.G),
      ("Milk", 25, UnitEnum.ML)],
     ['vegetarian']),
    ('Steamed Broccoli', 'side', False,
     [("Broccoli", 125, UnitEnum.G)],
     ['vegan', 'quick']),
    ('Garlic Green Beans', 'side', False,
     [("Green Beans", 125, UnitEnum.G), ("Garlic", 5, UnitEnum.G)],
     ['vegan', 'quick']),
    ('Oatmeal', 'first-course', False,
     [("Oats", 100, UnitEnum.G), ("Milk", 250, UnitEnum.ML)],
     ['breakfast', 'vegetarian']),
    ('Scrambled Eggs', 'main', False,
     [("Egg", 3, UnitEnum.PIECE), ("Butter", 15, UnitEnum.G)],
     ['breakfast', 'quick', 'vegetarian']),
    ('Grilled Cheese', 'main', False,
     [("Bread", 2, UnitEnum.PIECE), ("Cheddar Cheese", 60, UnitEnum.G),
      ("Butter", 15, UnitEnum.G)],
     ['quick', 'vegetarian']),
    ('Yogurt Parfait', 'first-course', False,
     [("Yogurt", 200, UnitEnum.G), ("Oats", 40, UnitEnum.G)],
     ['breakfast', 'vegetarian', 'quick']),
    ('Pasta Primavera', 'first-course', False,
     [("Penne", 100, UnitEnum.G), ("Zucchini", 50, UnitEnum.G),
      ("Peas", 40, UnitEnum.G), ("Parmesan", 15, UnitEnum.G)],
     ['pasta', 'vegetarian']),
    ('Eggplant Parmigiana', 'main', True,
     [("Eggplant", 100, UnitEnum.G), ("Tomato", 75, UnitEnum.G),
      ("Mozzarella", 37.5, UnitEnum.G), ("Parmesan", 12.5, UnitEnum.G)],
     ['vegetarian']),
    ('Stuffed Bell Peppers', 'main', True,
     [("Bell Pepper", 100, UnitEnum.G), ("Rice", 37.5, UnitEnum.G),
      ("Ground Beef", 50, UnitEnum.G)],
     ['stew']),
    ('Black Bean Tacos', 'main', False,
     [("Black Beans", 100, UnitEnum.G), ("Bread", 1, UnitEnum.PIECE),
      ("Bell Pepper", 40, UnitEnum.G)],
     ['vegan', 'quick', 'cheap']),
    ('Sausage and Peppers', 'main', False,
     [("Sausage", 150, UnitEnum.G), ("Bell Pepper", 100, UnitEnum.G),
      ("Onion", 50, UnitEnum.G)],
     ['quick']),
    ('Salmon Rice Bowl', 'main', False,
     [("Salmon", 125, UnitEnum.G), ("Rice", 100, UnitEnum.G),
      ("Soy Sauce", 10, UnitEnum.ML)],
     ['rice']),
    ('Pumpkin Soup', 'first-course', True,
     [("Pumpkin", 125, UnitEnum.G), ("Onion", 20, UnitEnum.G),
      ("Coconut Milk", 37.5, UnitEnum.ML)],
     ['soup', 'vegan']),
    ('Broccoli Cheddar Soup', 'first-course', True,
     [("Broccoli", 75, UnitEnum.G), ("Cheddar Cheese", 25, UnitEnum.G),
      ("Milk", 50, UnitEnum.ML)],
     ['soup', 'vegetarian']),
    ('Spinach Risotto', 'first-course', False,
     [("Arborio Rice", 100, UnitEnum.G), ("Spinach", 75, UnitEnum.G),
      ("Parmesan", 20, UnitEnum.G)],
     ['risotto', 'vegetarian']),
    ('Beef Steak with Potatoes', 'main', False,
     [("Beef Steak", 150, UnitEnum.G), ("Potato", 150, UnitEnum.G)],
     ['roast']),
    ('Cauliflower Curry', 'main', True,
     [("Cauliflower", 75, UnitEnum.G), ("Chickpeas", 37.5, UnitEnum.G),
      ("Curry Paste", 10, UnitEnum.G)],
     ['curry', 'vegan', 'spicy']),
    ('Coleslaw', 'side', False,
     [("Cabbage", 75, UnitEnum.G), ("Carrot", 25, UnitEnum.G),
      ("Yogurt", 20, UnitEnum.G)],
     ['salad', 'vegetarian']),
    ('Sweet Potato Mash', 'side', False,
     [("Sweet Potato", 125, UnitEnum.G), ("Butter", 7.5, UnitEnum.G)],
     ['vegetarian']),
    ('Tomato Basil Soup', 'first-course', True,
     [("Tomato", 125, UnitEnum.G), ("Basil", 3.75, UnitEnum.G),
      ("Onion", 20, UnitEnum.G)],
     ['soup', 'vegan', 'cheap']),
]]


# Dropping every table is irreversible, and ``DATABASE_URL`` points at whatever
# database the process was handed -- on Railway, the deployed one. Requiring an
# explicit opt-in means the destruction can only happen where someone put the
# flag there on purpose: ``docker-compose.yml`` sets it, no deployment does.
ALLOW_DESTRUCTIVE_SEED_ENV = "ALLOW_DESTRUCTIVE_SEED"


def reset_database() -> None:
    """Drop every table and recreate a clean schema from the models.

    Raises ``RuntimeError`` unless ``ALLOW_DESTRUCTIVE_SEED=1``. The check is an
    equality test rather than a truthiness one: a leftover ``0`` or ``false`` in
    a deployment's variables must not read as permission to wipe it.
    """

    if os.environ.get(ALLOW_DESTRUCTIVE_SEED_ENV) != "1":
        raise RuntimeError(
            "seed_testing_data drops every table. Set "
            f"{ALLOW_DESTRUCTIVE_SEED_ENV}=1 to confirm you are pointing at a "
            "disposable database -- never at a deployment."
        )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def populate(session) -> None:
    """Insert the full testing dataset into an empty database."""

    def _account(email: str, username: str, display_name: str) -> User:
        return User(
            email=email,
            # UN-1 is NOT NULL, and these are constructed directly rather than
            # through ``crud.create_user``, so the handle is explicit.
            username=username,
            # UN-5: a seeded local account has a deliberately chosen handle, so
            # it counts as confirmed and skips the selection step (D-7).
            username_changed_at=datetime.utcnow(),
            hashed_password=hash_password(DEMO_USER_PASSWORD),
            display_name=display_name,
            auth_provider="local",
            default_people=2,
            # Seeded local accounts are pre-verified so they can log in
            # immediately -- and so ``friend`` satisfies SWM-4's verified-email
            # requirement for the person-mode share below.
            email_verified=True,
        )

    demo_user = _account(DEMO_USER_EMAIL, DEMO_USER_USERNAME, "Demo User")
    friend_user = _account(FRIEND_USER_EMAIL, FRIEND_USER_USERNAME, "Friend Cook")
    guest_user = _account(GUEST_USER_EMAIL, GUEST_USER_USERNAME, "Guest Cook")
    session.add_all([demo_user, friend_user, guest_user])
    # Flush so the ids are available to stamp ownership on every row.
    session.flush()

    users_by_username = {
        u.username: u for u in (demo_user, friend_user, guest_user)
    }

    # UN-4 must hold in a seeded database too, or a manual walkthrough of
    # acceptance criterion 1 would find ``admin`` claimable.
    usernames.seed_reserved(session)

    tags: dict[str, Tag] = {}
    for name, penalize, is_system in TAGS:
        tag = Tag(
            name=name,
            penalize_repetition=penalize,
            is_system=is_system,
            user_id=demo_user.id,
        )
        session.add(tag)
        tags[name] = tag

    ingredients: dict[str, Ingredient] = {}
    for name, unit, months, categories in INGREDIENTS:
        ing = Ingredient(
            name=name,
            unit=unit,
            season_months=months,
            categories=categories,
            user_id=demo_user.id,
        )
        session.add(ing)
        ingredients[name] = ing

    recipes_by_title: dict[str, Recipe] = {}
    for title, course, bulk, ing_list, tag_list, servings in RECIPES:
        recipe = Recipe(
            title=title,
            procedure=f"Prepare {title.lower()}.",
            course=course,
            bulk_prep=bulk,
            servings=servings,
            user_id=demo_user.id,
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
        recipes_by_title[title] = recipe

    link_favorite_sides(recipes_by_title)
    session.flush()
    link_shares(session, recipes_by_title, users_by_username, demo_user)
    link_copies(
        session, recipes_by_title, users_by_username, ingredients, demo_user
    )
    session.commit()


def main() -> None:
    reset_database()
    session = SessionLocal()
    try:
        populate(session)
        n_r = session.query(Recipe).count()
        n_i = session.query(Ingredient).count()
        n_t = session.query(Tag).count()
        n_s = session.query(RecipeShare).count()
        n_u = session.query(User).count()
    finally:
        session.close()
    print(
        f"[seed_testing_data] Database reset and populated: "
        f"{n_r} recipes, {n_i} ingredients, {n_t} tags, "
        f"{n_u} users, {n_s} shares."
    )


if __name__ == "__main__":
    main()
