"""Populate a *single existing* user's account with the standard testing data.

Unlike ``seed_testing_data.py`` (which drops every table and rebuilds a demo
database from scratch), this script is **non-destructive**: it never resets the
schema and only touches rows owned by the target user. It reuses the same
ingredient / tag / recipe catalogue as the full seed so an account ends up with
a coherent, ready-to-plan dataset.

The target user is created if it does not exist yet (local email/password
account). Running it repeatedly is safe: tags and ingredients are matched by
name (per user) and recipes by title, so nothing is duplicated.

With no arguments both :data:`PROFILES` are seeded: an omnivore account owning
the whole catalogue and a meat-free one owning only its vegetarian/vegan
recipes, so the two accounts hold visibly different data.

Run from the ``backend/`` directory::

    python scripts/seed_user_data.py                       # both profiles
    python scripts/seed_user_data.py someone@example.com   # one account
    python scripts/seed_user_data.py someone@example.com hunter2   # + password
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

# Allow ``python scripts/seed_user_data.py`` to resolve the top-level modules
# that live at the backend root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select  # noqa: E402

from crud import normalize_email  # noqa: E402
from database import SessionLocal  # noqa: E402
from models import Ingredient, Recipe, RecipeIngredient, Tag, User  # noqa: E402
from auth_users import hash_password  # noqa: E402
from scripts.seed_testing_data import (  # noqa: E402
    INGREDIENTS,
    RECIPES,
    TAGS,
    SeedRecipe,
)

DEFAULT_EMAIL = "alessandro.nardi1998@gmail.com"
DEFAULT_PASSWORD = "demo1234"


MEAT_FREE_TAGS = {"vegetarian", "vegan"}


@dataclass(frozen=True)
class Profile:
    """A demo account together with the slice of the catalogue it owns."""

    email: str
    password: str
    recipes: list[SeedRecipe]


def _meat_free(recipes: list[SeedRecipe]) -> list[SeedRecipe]:
    return [r for r in recipes if MEAT_FREE_TAGS & set(r.tags)]


PROFILES: list[Profile] = [
    Profile(email=DEFAULT_EMAIL, password=DEFAULT_PASSWORD, recipes=RECIPES),
    Profile(
        email="veggie.demo@example.com",
        password=DEFAULT_PASSWORD,
        recipes=_meat_free(RECIPES),
    ),
]


def get_or_create_user(session, email: str, password: str) -> User:
    """Return the user with ``email``, creating a local account if missing."""

    email = normalize_email(email)
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


def populate_for_user(session, user: User, recipes: list[SeedRecipe]) -> dict[str, int]:
    """Insert ``recipes`` for ``user``.

    Only the tags and ingredients those recipes reference are inserted, so a
    profile owning a slice of the catalogue gets a coherent dataset rather than
    a pantry full of items it can never cook with. Other users' rows are never
    touched.
    """

    wanted_tags = {name for r in recipes for name in r.tags}
    wanted_ingredients = {name for r in recipes for (name, _q, _u) in r.ingredients}

    counts = {"tags": 0, "ingredients": 0, "recipes": 0}

    tags: dict[str, Tag] = {}
    for name, penalize, is_system in TAGS:
        if name not in wanted_tags:
            continue
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
        if name not in wanted_ingredients:
            continue
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

    for title, servings, course, bulk, ing_list, tag_list in recipes:
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


def seed_profiles(session, profiles: list[Profile] | None = None) -> list[tuple[User, dict[str, int]]]:
    """Create each profile's account and populate the catalogue it owns."""

    seeded = []
    for profile in PROFILES if profiles is None else profiles:
        user = get_or_create_user(session, profile.email, profile.password)
        counts = populate_for_user(session, user, profile.recipes)
        seeded.append((user, counts))
    return seeded


def _report(session, user: User, counts: dict[str, int]) -> str:
    total_r = session.query(Recipe).filter_by(user_id=user.id).count()
    total_i = session.query(Ingredient).filter_by(user_id=user.id).count()
    total_t = session.query(Tag).filter_by(user_id=user.id).count()
    # Report the stored address rather than the raw argument, so the operator
    # sees which account was actually touched.
    return (
        f"[seed_user_data] Populated {user.email!r} (added "
        f"{counts['recipes']} recipes, {counts['ingredients']} ingredients, "
        f"{counts['tags']} tags). Account now owns "
        f"{total_r} recipes, {total_i} ingredients, {total_t} tags."
    )


def profile_for_email(email: str, password: str) -> Profile:
    """The named profile if ``email`` is one, else a full-catalogue account."""

    email = normalize_email(email)
    for profile in PROFILES:
        if normalize_email(profile.email) == email:
            return profile
    return Profile(email=email, password=password, recipes=RECIPES)


def main() -> None:
    if len(sys.argv) > 1:
        password = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PASSWORD
        profiles = [profile_for_email(sys.argv[1], password)]
    else:
        profiles = PROFILES

    session = SessionLocal()
    try:
        seeded = seed_profiles(session, profiles)
        lines = [_report(session, user, counts) for user, counts in seeded]
    finally:
        session.close()

    print("\n".join(lines))


if __name__ == "__main__":
    main()
