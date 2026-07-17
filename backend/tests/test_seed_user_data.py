"""The per-user seed script must agree with the app on email casing."""
from scripts.seed_user_data import PROFILES, get_or_create_user, seed_profiles

import crud
from models import Ingredient, Recipe


def test_get_or_create_user_stores_email_lowercased(db_session):
    user = get_or_create_user(db_session, "Seed.User@Example.COM", "pw12345")

    assert user.email == "seed.user@example.com"


def test_get_or_create_user_reuses_account_when_case_differs(db_session):
    existing = crud.create_user(
        db_session, email="seed@example.com", hashed_password="hp"
    )

    found = get_or_create_user(db_session, "SEED@Example.com", "pw12345")

    assert found.id == existing.id
    assert db_session.query(crud.User).count() == 1, "must not create a duplicate"


def test_two_profiles_with_distinct_emails():
    assert len(PROFILES) == 2
    emails = {p.email for p in PROFILES}
    assert len(emails) == 2


def test_profiles_carry_different_recipe_sets():
    first, second = PROFILES
    titles_first = {r.title for r in first.recipes}
    titles_second = {r.title for r in second.recipes}

    assert titles_first != titles_second
    assert titles_first and titles_second


def test_vegetarian_profile_keeps_veg_recipes_and_drops_meat_ones():
    titles = {r.title for r in PROFILES[1].recipes}

    assert "Spaghetti Pomodoro" in titles
    assert "Roast Chicken" not in titles
    assert "Beef Stew" not in titles


def test_seed_profiles_gives_each_account_its_own_recipes(db_session):
    seed_profiles(db_session)

    for profile in PROFILES:
        user = get_or_create_user(db_session, profile.email, profile.password)
        titles = {
            t for (t,) in db_session.query(Recipe.title).filter_by(user_id=user.id)
        }
        assert titles == {r.title for r in profile.recipes}


def test_seed_profiles_only_inserts_ingredients_its_recipes_use(db_session):
    seed_profiles(db_session)

    veg = PROFILES[1]
    user = get_or_create_user(db_session, veg.email, veg.password)
    used = {name for r in veg.recipes for (name, _q, _u) in r.ingredients}
    seeded = {
        n for (n,) in db_session.query(Ingredient.name).filter_by(user_id=user.id)
    }

    assert seeded == used


def test_seed_profiles_is_idempotent(db_session):
    seed_profiles(db_session)
    seed_profiles(db_session)

    assert db_session.query(crud.User).count() == 2
    for profile in PROFILES:
        user = get_or_create_user(db_session, profile.email, profile.password)
        count = db_session.query(Recipe).filter_by(user_id=user.id).count()
        assert count == len(profile.recipes)
