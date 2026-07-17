"""The seeded catalogue must include coherent favorite-side pairings."""
from models import Recipe, takes_favorite_sides
from scripts.seed_testing_data import FAVORITE_SIDES, RECIPES, populate
from scripts.seed_user_data import PROFILES, get_or_create_user, seed_profiles


def _by_title():
    return {r.title: r for r in RECIPES}


def test_every_pairing_names_recipes_that_exist():
    recipes = _by_title()

    for main_title, side_titles in FAVORITE_SIDES.items():
        assert main_title in recipes, f"unknown main {main_title!r}"
        for side_title in side_titles:
            assert side_title in recipes, f"unknown side {side_title!r}"


def test_pairings_only_map_mains_to_actual_sides():
    recipes = _by_title()

    for main_title, side_titles in FAVORITE_SIDES.items():
        assert takes_favorite_sides(recipes[main_title].course), (
            f"{main_title!r} is not a course that takes sides"
        )
        for side_title in side_titles:
            assert recipes[side_title].course == "side", (
                f"{side_title!r} is not a side dish"
            )


def test_seeded_recipes_get_their_favorite_sides(db_session):
    populate(db_session)

    roast = db_session.query(Recipe).filter_by(title="Roast Chicken").one()
    assert {s.title for s in roast.favorite_sides} == set(
        FAVORITE_SIDES["Roast Chicken"]
    )


def test_the_seeded_pairings_are_never_empty(db_session):
    """Guards the feature being demoable at all from a fresh database."""
    populate(db_session)

    paired = [
        r for r in db_session.query(Recipe).all() if r.favorite_sides
    ]
    assert len(paired) >= 5


def test_per_user_seed_pairs_only_within_that_users_recipes(db_session):
    """The vegetarian profile drops meat mains; its pairings must still hold."""
    seed_profiles(db_session)

    for profile in PROFILES:
        user = get_or_create_user(db_session, profile.email, profile.password)
        owned = db_session.query(Recipe).filter_by(user_id=user.id).all()
        owned_ids = {r.id for r in owned}
        for recipe in owned:
            for side in recipe.favorite_sides:
                assert side.id in owned_ids, "paired across user boundaries"
                assert side.course == "side"
