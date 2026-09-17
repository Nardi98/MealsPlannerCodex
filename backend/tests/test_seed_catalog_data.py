"""SEED-1..9: the testing seed must populate the system recipe catalog.

CLAUDE.md makes updating ``seed_testing_data.py`` part of any schema change, so
these assertions are the executable form of that rule for the catalog work,
modelled on ``test_seed_sharing_data.py``.

Adoption counts are computed here with a grouped ``COUNT(DISTINCT user_id)``
rather than through ``catalog.py``: the service is built in parallel, and a
seed test built on the service would not notice the two disagreeing.
"""

import pytest
from sqlalchemy import func, select

import scripts.seed_testing_data as seed
from models import CatalogEntry, Ingredient, Recipe, Tag, User
from scripts.seed_testing_data import DEMO_USER_EMAIL, populate


def _system(session):
    return session.execute(select(User).where(User.is_system.is_(True))).scalar_one()


def _entries(session, status):
    """Catalog entries in ``status`` whose recipe the system account owns."""
    system = _system(session)
    return session.execute(
        select(CatalogEntry)
        .join(Recipe, Recipe.id == CatalogEntry.recipe_id)
        .where(CatalogEntry.status == status, Recipe.user_id == system.id)
    ).scalars().all()


def _adoption_counts(session):
    """``{catalog recipe id: distinct adopters}``, the system account excluded (POP-1/3)."""
    system = _system(session)
    rows = session.execute(
        select(Recipe.source_recipe_id, func.count(func.distinct(Recipe.user_id)))
        .join(CatalogEntry, CatalogEntry.recipe_id == Recipe.source_recipe_id)
        .where(Recipe.user_id != system.id)
        .group_by(Recipe.source_recipe_id)
    ).all()
    return dict(rows)


# --- SEED-1 / SEED-2 ---------------------------------------------------------

def test_the_seed_creates_exactly_one_system_account_with_no_login_path(db_session):
    """SEED-1 with the SYS-3, SYS-5 and SYS-12 field values."""
    populate(db_session)

    accounts = db_session.execute(
        select(User).where(User.is_system.is_(True))
    ).scalars().all()
    assert len(accounts) == 1
    system = accounts[0]
    assert system.username == "mealplanner"
    assert system.email == "mealplanner@localhost"
    assert system.hashed_password is None
    assert system.google_sub is None
    assert system.auth_provider == "local"
    assert system.email_verified is False
    assert system.username_changed_at is not None
    assert system.is_admin is False


def test_the_system_account_owns_its_own_tags_and_ingredients(db_session):
    """SEED-2 / SYS-8."""
    populate(db_session)
    system = _system(db_session)

    n_tags = db_session.execute(
        select(func.count()).select_from(Tag).where(Tag.user_id == system.id)
    ).scalar_one()
    n_ingredients = db_session.execute(
        select(func.count()).select_from(Ingredient).where(Ingredient.user_id == system.id)
    ).scalar_one()
    assert n_tags > 0
    assert n_ingredients > 0


# --- SEED-3 / SEED-4 ---------------------------------------------------------

def test_the_seed_publishes_system_owned_catalog_recipes(db_session):
    """SEED-3: at least six published entries, each owned by the system account."""
    populate(db_session)

    assert len(_entries(db_session, "published")) >= 6


def test_every_seeded_catalog_recipe_could_be_published(db_session):
    """CAT-10 and P2-2: a title, a procedure, ingredients -- and private.

    Its ingredients and tags live in the system namespace, never a demo user's.
    """
    populate(db_session)
    system = _system(db_session)

    entries = _entries(db_session, "published") + _entries(db_session, "retired")
    assert entries
    for entry in entries:
        recipe = entry.recipe
        assert recipe.title
        assert recipe.procedure and recipe.procedure.strip()
        assert recipe.ingredients
        assert recipe.visibility == "private"
        assert {link.ingredient.user_id for link in recipe.ingredients} == {system.id}
        assert {tag.user_id for tag in recipe.tags} <= {system.id}


def test_the_seed_retires_at_least_one_entry(db_session):
    """SEED-4, with DM-4's timestamp."""
    populate(db_session)

    retired = _entries(db_session, "retired")
    assert retired
    assert all(entry.retired_at is not None for entry in retired)


def test_a_catalog_recipe_whose_ingredient_the_system_pantry_lacks_is_resolved(db_session):
    """An ingredient absent from ``system_ingredients.json`` is created in the
    system namespace from the seed's own metadata, not borrowed from demo_chef."""
    populate(db_session)
    system = _system(db_session)

    pork = db_session.execute(
        select(Ingredient).where(
            Ingredient.name == "Pork Loin", Ingredient.user_id == system.id
        )
    ).scalar_one()
    assert pork.categories == ["Meat", "Protein"]


# --- SEED-5 ------------------------------------------------------------------

def test_adoptions_by_demo_users_produce_at_least_three_distinct_counts(db_session):
    """SEED-5: the popularity sort must be visibly exercised."""
    populate(db_session)

    counts = _adoption_counts(db_session)
    assert len(set(counts.values())) >= 3


def test_every_demo_account_adopts_something(db_session):
    populate(db_session)
    system = _system(db_session)

    adopters = set(
        db_session.execute(
            select(Recipe.user_id)
            .join(CatalogEntry, CatalogEntry.recipe_id == Recipe.source_recipe_id)
            .where(Recipe.user_id != system.id)
        ).scalars()
    )
    handles = {db_session.get(User, uid).username for uid in adopters}
    assert handles == {"demo_chef", "friend_cook", "guest_cook"}


def test_adoption_copies_carry_attribution_and_the_sources_bulk_prep(db_session):
    """ADO-8 and D2; the source counts each copy (ADO-16)."""
    populate(db_session)
    system = _system(db_session)

    copies = db_session.execute(
        select(Recipe)
        .join(CatalogEntry, CatalogEntry.recipe_id == Recipe.source_recipe_id)
        .where(Recipe.user_id != system.id)
    ).scalars().all()
    assert copies
    assert any(copy.bulk_prep for copy in copies), "bulk_prep=True must be exercised"

    per_source = _adoption_counts(db_session)
    for copy in copies:
        source = db_session.get(Recipe, copy.source_recipe_id)
        assert copy.source_user_id == system.id
        assert copy.source_author_username == system.username
        assert copy.source_recipe_title == source.title
        assert copy.copied_at is not None
        assert copy.visibility == "private"
        assert copy.bulk_prep == source.bulk_prep
        assert source.copy_count == per_source[source.id]


# --- SEED-6 / SEED-7 ---------------------------------------------------------

def test_exactly_one_admin_the_demo_account(db_session):
    """SEED-6."""
    populate(db_session)

    admins = db_session.execute(
        select(User).where(User.is_admin.is_(True))
    ).scalars().all()
    assert [a.email for a in admins] == [DEMO_USER_EMAIL]
    assert DEMO_USER_EMAIL == "demo@mealplanner.test"


def test_the_script_still_refuses_to_run_without_the_flag(monkeypatch):
    """SEED-7: the entry point, not only ``reset_database``, refuses."""
    monkeypatch.delenv(seed.ALLOW_DESTRUCTIVE_SEED_ENV, raising=False)

    with pytest.raises(RuntimeError):
        seed.main()


# --- The user dataset is untouched -----------------------------------------

def test_demo_chef_still_owns_the_full_testing_dataset(db_session):
    """The catalog is added beside demo_chef's book, not carved out of it."""
    populate(db_session)
    demo = db_session.execute(
        select(User).where(User.email == DEMO_USER_EMAIL)
    ).scalar_one()

    own_recipes = db_session.execute(
        select(func.count()).select_from(Recipe).where(
            Recipe.user_id == demo.id, Recipe.source_recipe_id.is_(None)
        )
    ).scalar_one()
    n_ingredients = db_session.execute(
        select(func.count()).select_from(Ingredient).where(Ingredient.user_id == demo.id)
    ).scalar_one()
    n_tags = db_session.execute(
        select(func.count()).select_from(Tag).where(Tag.user_id == demo.id)
    ).scalar_one()
    assert own_recipes == len(seed.RECIPES)
    assert n_ingredients >= 50
    assert n_tags >= 10
