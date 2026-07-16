"""Populate a *single existing* user's account with the standard testing data.

Unlike ``seed_testing_data.py`` (which drops every table and rebuilds a demo
database from scratch), this script is **non-destructive**: it never resets the
schema and only touches rows owned by the target user. It reuses the same
ingredient / tag / recipe catalogue as the full seed so an account ends up with
a coherent, ready-to-plan dataset.

The target user is created if it does not exist yet (local email/password
account). Running it repeatedly is safe: tags and ingredients are matched by
name (per user) and recipes by title, so nothing is duplicated.

Run from the ``backend/`` directory::

    python scripts/seed_user_data.py                       # default email below
    python scripts/seed_user_data.py someone@example.com   # any email
    python scripts/seed_user_data.py someone@example.com hunter2   # + password
"""

from __future__ import annotations

import os
import sys

# Allow ``python scripts/seed_user_data.py`` to resolve the top-level modules
# that live at the backend root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select  # noqa: E402

from database import SessionLocal  # noqa: E402
from models import Ingredient, Recipe, RecipeIngredient, Tag, User  # noqa: E402
from auth_users import hash_password  # noqa: E402
from scripts.seed_testing_data import INGREDIENTS, RECIPES, TAGS  # noqa: E402

DEFAULT_EMAIL = "alessandro.nardi1998@gmail.com"
DEFAULT_PASSWORD = "demo1234"


def get_or_create_user(session, email: str, password: str) -> User:
    """Return the user with ``email``, creating a local account if missing."""

    user = session.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            hashed_password=hash_password(password),
            display_name=email.split("@")[0],
            auth_provider="local",
        )
        session.add(user)
        session.flush()
    return user


def populate_for_user(session, user: User) -> dict[str, int]:
    """Insert the standard catalogue for ``user`` without touching other rows."""

    counts = {"tags": 0, "ingredients": 0, "recipes": 0}

    tags: dict[str, Tag] = {}
    for name, penalize, is_system in TAGS:
        tag = session.execute(
            select(Tag).where(Tag.name == name, Tag.user_id == user.id)
        ).scalar_one_or_none()
        if tag is None:
            tag = Tag(name=name, user_id=user.id)
            session.add(tag)
            counts["tags"] += 1
        tag.penalize_repetition = penalize
        tag.is_system = is_system
        tags[name] = tag

    ingredients: dict[str, Ingredient] = {}
    for name, unit, months, categories in INGREDIENTS:
        ing = session.execute(
            select(Ingredient).where(
                Ingredient.name == name, Ingredient.user_id == user.id
            )
        ).scalar_one_or_none()
        if ing is None:
            ing = Ingredient(
                name=name,
                unit=unit,
                season_months=months,
                categories=categories,
                user_id=user.id,
            )
            session.add(ing)
            counts["ingredients"] += 1
        ingredients[name] = ing

    for title, servings, course, bulk, ing_list, tag_list in RECIPES:
        exists = session.execute(
            select(Recipe).where(
                Recipe.title == title, Recipe.user_id == user.id
            )
        ).scalar_one_or_none()
        if exists is not None:
            continue
        recipe = Recipe(
            title=title,
            servings_default=servings,
            procedure=f"Prepare {title.lower()}.",
            course=course,
            bulk_prep=bulk,
            user_id=user.id,
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
        counts["recipes"] += 1

    session.commit()
    return counts


def main() -> None:
    email = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EMAIL
    password = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PASSWORD

    session = SessionLocal()
    try:
        user = get_or_create_user(session, email, password)
        counts = populate_for_user(session, user)
        total_r = session.query(Recipe).filter_by(user_id=user.id).count()
        total_i = session.query(Ingredient).filter_by(user_id=user.id).count()
        total_t = session.query(Tag).filter_by(user_id=user.id).count()
    finally:
        session.close()

    print(
        f"[seed_user_data] Populated {email!r} (added "
        f"{counts['recipes']} recipes, {counts['ingredients']} ingredients, "
        f"{counts['tags']} tags). Account now owns "
        f"{total_r} recipes, {total_i} ingredients, {total_t} tags."
    )


if __name__ == "__main__":
    main()
