"""Schema foundation for the system recipe catalog (spec §4, §5, §8, §10.3).

Covers the pieces every later catalog task builds on: the ``is_system`` /
``is_admin`` flags and the single-system-account guarantee (SYS-2), the
``catalog_entries`` table and its two named CHECKs (DM-1..4), the
``source_recipe_id`` index (DM-5), ``Recipe.from_library`` and the D7 handle
mask on ``RecipeOut`` (API-16), the public ``recipe_copy.duplicate`` (ADO-4)
now carrying ``bulk_prep`` (D2), and the ``catalog`` module's T1 symbols.
"""

from datetime import datetime

import pytest
from sqlalchemy import delete, func, inspect, select, text
from sqlalchemy.exc import IntegrityError

import catalog
import crud
import models
import ratelimit
import recipe_copy
import schemas
from conftest import client_as
from main import app
from mealplanner.seed import SYSTEM_INGREDIENTS, SYSTEM_TAGS


# --- users.is_system / users.is_admin (SYS-1, SYS-2, DM-6) -----------------

def test_new_users_are_neither_system_nor_admin(db_session, user):
    db_session.refresh(user)
    assert user.is_system is False
    assert user.is_admin is False


def test_the_flags_default_false_at_the_database_level(db_session):
    """A row inserted by raw SQL -- a seed script, a hand fix -- is still valid."""
    db_session.execute(
        text(
            "INSERT INTO users (email, username, auth_provider) "
            "VALUES ('raw@test.local', 'rawuser', 'local')"
        )
    )
    row = db_session.execute(
        text("SELECT is_system, is_admin FROM users WHERE username = 'rawuser'")
    ).one()
    assert tuple(row) == (False, False)


def test_a_second_system_account_is_refused_by_the_database(db_session, user, other_user):
    user.is_system = True
    db_session.flush()
    other_user.is_system = True
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_many_non_system_accounts_coexist(db_session, user, other_user):
    """The unique index is partial: ``false`` is not a value it constrains."""
    db_session.flush()
    count = db_session.scalar(
        select(func.count()).select_from(models.User).where(models.User.is_system.is_(False))
    )
    assert count >= 2


def test_the_single_system_index_is_partial_and_unique(engine):
    indexes = {ix["name"]: ix for ix in inspect(engine).get_indexes("users")}
    ix = indexes["uq_user_single_system"]
    assert ix["unique"] is True
    assert ix["column_names"] == ["is_system"]
    assert "is_system" in (ix.get("dialect_options", {}).get("postgresql_where") or "")


def test_mealplanner_is_a_reserved_handle():
    assert "mealplanner" in models.RESERVED_USERNAMES


# --- catalog_entries (DM-1..4, DM-9, DM-10) ---------------------------------

@pytest.fixture
def system_recipe(db_session, system_account):
    recipe = models.Recipe(title="Catalogued", course="main", user_id=system_account.id)
    db_session.add(recipe)
    db_session.flush()
    return recipe


def test_an_entry_defaults_to_published_now(db_session, system_recipe):
    entry = models.CatalogEntry(recipe_id=system_recipe.id)
    db_session.add(entry)
    db_session.flush()
    db_session.refresh(entry)
    assert entry.status == "published"
    assert entry.published_at is not None
    assert entry.retired_at is None


def test_an_unknown_status_is_refused(db_session, system_recipe):
    db_session.add(models.CatalogEntry(recipe_id=system_recipe.id, status="draft"))
    with pytest.raises(IntegrityError, match="ck_catalog_entry_status"):
        db_session.flush()


def test_retired_without_a_retired_at_is_refused(db_session, system_recipe):
    db_session.add(models.CatalogEntry(recipe_id=system_recipe.id, status="retired"))
    with pytest.raises(IntegrityError, match="ck_catalog_entry_retired_all_or_nothing"):
        db_session.flush()


def test_published_with_a_retired_at_is_refused(db_session, system_recipe):
    db_session.add(
        models.CatalogEntry(
            recipe_id=system_recipe.id, status="published", retired_at=datetime.utcnow()
        )
    )
    with pytest.raises(IntegrityError, match="ck_catalog_entry_retired_all_or_nothing"):
        db_session.flush()


def test_retired_with_a_retired_at_is_accepted(db_session, system_recipe):
    db_session.add(
        models.CatalogEntry(
            recipe_id=system_recipe.id, status="retired", retired_at=datetime.utcnow()
        )
    )
    db_session.flush()


def test_a_recipe_is_catalogued_at_most_once(db_session, system_recipe):
    db_session.add(models.CatalogEntry(recipe_id=system_recipe.id))
    db_session.flush()
    db_session.expunge_all()
    db_session.add(models.CatalogEntry(recipe_id=system_recipe.id))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_the_entry_has_exactly_the_specified_columns(engine):
    columns = {c["name"] for c in inspect(engine).get_columns("catalog_entries")}
    assert columns == {"recipe_id", "status", "published_at", "retired_at"}
    pk = inspect(engine).get_pk_constraint("catalog_entries")
    assert pk["constrained_columns"] == ["recipe_id"]


def test_deleting_a_recipe_deletes_its_entry(db_session, system_recipe):
    db_session.add(models.CatalogEntry(recipe_id=system_recipe.id))
    db_session.flush()
    recipe_id = system_recipe.id
    db_session.expunge_all()

    db_session.delete(db_session.get(models.Recipe, recipe_id))
    db_session.flush()

    remaining = db_session.scalar(
        select(func.count()).select_from(models.CatalogEntry).where(
            models.CatalogEntry.recipe_id == recipe_id
        )
    )
    assert remaining == 0


def test_a_recipe_exposes_its_catalog_entry(db_session, system_recipe):
    db_session.add(models.CatalogEntry(recipe_id=system_recipe.id))
    db_session.flush()
    recipe_id = system_recipe.id
    db_session.expunge_all()

    recipe = db_session.get(models.Recipe, recipe_id)
    assert recipe.catalog_entry is not None
    assert recipe.catalog_entry.status == "published"
    assert recipe.catalog_entry.recipe is recipe


def test_an_uncatalogued_recipe_has_no_entry(db_session, make_recipe):
    assert make_recipe("Mine").catalog_entry is None


def test_source_recipe_id_is_indexed(engine):
    indexed = {
        tuple(ix["column_names"]) for ix in inspect(engine).get_indexes("recipes")
    }
    assert ("source_recipe_id",) in indexed


# --- catalog module: T1 symbols (SYS-3/5/6/8/12, CAT-3) ---------------------

def test_catalog_constants():
    assert catalog.SYSTEM_ACCOUNT_USERNAME == "mealplanner"
    assert catalog.SYSTEM_ACCOUNT_EMAIL == "mealplanner@localhost"
    assert catalog.LISTING_CAP == 500
    assert catalog.ADOPT_BATCH_MAX >= 100
    assert issubclass(catalog.SystemAccountMissing, RuntimeError)
    assert issubclass(catalog.CatalogEntryNotFound, LookupError)
    assert issubclass(catalog.IncompleteRecipe, ValueError)


def test_system_user_raises_a_named_error_when_absent(db_session):
    db_session.execute(delete(models.User).where(models.User.is_system.is_(True)))
    with pytest.raises(catalog.SystemAccountMissing):
        catalog.system_user(db_session)


def test_system_user_resolves_by_flag_not_handle(db_session, system_account):
    system_account.username = "renamed"
    db_session.flush()
    assert catalog.system_user(db_session).id == system_account.id


def test_ensure_system_account_creates_the_specified_account(db_session):
    db_session.execute(delete(models.User).where(models.User.is_system.is_(True)))
    system = catalog.ensure_system_account(db_session)
    db_session.refresh(system)

    assert system.is_system is True
    assert system.is_admin is False
    assert system.username == "mealplanner"
    assert system.email == "mealplanner@localhost"
    assert system.hashed_password is None
    assert system.google_sub is None
    assert system.auth_provider == "local"
    assert system.email_verified is False
    assert system.username_changed_at is not None


def test_ensure_system_account_seeds_its_own_tags_and_ingredients(db_session):
    db_session.execute(delete(models.User).where(models.User.is_system.is_(True)))
    system = catalog.ensure_system_account(db_session)

    tag_names = set(
        db_session.execute(
            select(models.Tag.name).where(models.Tag.user_id == system.id)
        ).scalars()
    )
    ingredient_names = set(
        db_session.execute(
            select(models.Ingredient.name).where(models.Ingredient.user_id == system.id)
        ).scalars()
    )
    assert {t["name"] for t in SYSTEM_TAGS} <= tag_names
    assert {i["name"] for i in SYSTEM_INGREDIENTS} <= ingredient_names


def test_ensure_system_account_is_idempotent(db_session):
    db_session.execute(delete(models.User).where(models.User.is_system.is_(True)))
    first = catalog.ensure_system_account(db_session)
    tags_before = db_session.scalar(
        select(func.count()).select_from(models.Tag).where(models.Tag.user_id == first.id)
    )
    second = catalog.ensure_system_account(db_session)

    assert second.id == first.id
    assert db_session.scalar(
        select(func.count()).select_from(models.User).where(models.User.is_system.is_(True))
    ) == 1
    assert db_session.scalar(
        select(func.count()).select_from(models.Tag).where(models.Tag.user_id == first.id)
    ) == tags_before


# --- conftest fixtures ------------------------------------------------------

def test_the_system_account_fixture_starts_with_an_empty_catalog(db_session, system_account):
    assert system_account.is_system is True
    assert db_session.scalar(select(func.count()).select_from(models.CatalogEntry)) == 0


def test_make_catalog_recipe_builds_a_system_owned_entry(db_session, system_account, make_catalog_recipe):
    recipe = make_catalog_recipe("Carbonara", bulk_prep=True, servings=2)
    assert recipe.user_id == system_account.id
    assert recipe.bulk_prep is True
    assert recipe.servings == 2
    assert recipe.procedure == "Cook it."
    assert recipe.catalog_entry.status == "published"
    assert [(i.ingredient.name, i.quantity, i.unit) for i in recipe.ingredients] == [
        ("Pasta", 80, models.UnitEnum.G)
    ]
    assert all(i.ingredient.user_id == system_account.id for i in recipe.ingredients)
    assert [(t.name, t.user_id) for t in recipe.tags] == [("pasta", system_account.id)]


def test_make_catalog_recipe_can_build_a_retired_entry(make_catalog_recipe):
    recipe = make_catalog_recipe("Old", status="retired")
    assert recipe.catalog_entry.status == "retired"
    assert recipe.catalog_entry.retired_at is not None


def test_the_admin_user_fixture_is_an_admin(db_session, admin_user):
    db_session.refresh(admin_user)
    assert admin_user.is_admin is True
    assert admin_user.is_system is False


# --- Recipe.from_library and the D7 mask (API-16) ---------------------------

def _copy_of(db_session, source, copier):
    made = recipe_copy.duplicate(db_session, source, copier)
    db_session.flush()
    return made


def test_a_copy_of_a_system_recipe_is_from_the_library(
    db_session, make_catalog_recipe, user
):
    made = _copy_of(db_session, make_catalog_recipe("Pesto"), user)
    db_session.expire(made)
    assert made.from_library is True


def test_a_copy_of_a_users_recipe_is_not_from_the_library(
    db_session, system_account, make_recipe, other_user
):
    made = _copy_of(db_session, make_recipe("Ragu"), other_user)
    db_session.expire(made)
    assert made.from_library is False


def test_an_original_recipe_is_not_from_the_library(db_session, make_recipe):
    recipe = make_recipe("Mine")
    db_session.expire(recipe)
    assert recipe.from_library is False


def test_recipe_out_masks_the_handle_for_a_library_copy(
    db_session, make_catalog_recipe, user
):
    made = _copy_of(db_session, make_catalog_recipe("Pesto"), user)
    db_session.expire(made)
    assert made.source_author_username == "mealplanner"  # ADO-8 snapshot kept

    out = schemas.RecipeOut.model_validate(made)
    assert out.from_library is True
    assert out.source_author_username is None
    assert out.source_recipe_title == "Pesto"


def test_recipe_out_keeps_the_handle_for_a_user_copy(
    db_session, system_account, make_recipe, user, other_user
):
    made = _copy_of(db_session, make_recipe("Ragu"), other_user)
    db_session.expire(made)
    out = schemas.RecipeOut.model_validate(made)
    assert out.from_library is False
    assert out.source_author_username == user.username


def test_get_recipes_reports_from_library_without_the_handle(
    db_session, make_catalog_recipe, user
):
    made = _copy_of(db_session, make_catalog_recipe("Pesto"), user)
    try:
        body = client_as(db_session, user).get("/recipes").json()
    finally:
        app.dependency_overrides.clear()

    row = next(r for r in body if r["id"] == made.id)
    assert row["from_library"] is True
    assert row["source_author_username"] is None
    assert "mealplanner" not in str(body)


# --- recipe_copy.duplicate (ADO-4, D2) ---------------------------------------

def test_duplicate_is_public():
    assert "duplicate" in recipe_copy.__all__
    assert not hasattr(recipe_copy, "_duplicate")


def test_duplicate_copies_bulk_prep(db_session, make_catalog_recipe, user):
    made = _copy_of(db_session, make_catalog_recipe("Stew", bulk_prep=True), user)
    assert made.bulk_prep is True


def test_copy_recipe_copies_bulk_prep(db_session, make_recipe, other_user):
    source = make_recipe("Chili", bulk_prep=True)
    made = recipe_copy.copy_recipe(db_session, source, other_user)
    assert made.bulk_prep is True


def test_duplicate_does_not_copy_favourite_sides(db_session, make_recipe, user, other_user):
    main = make_recipe("Roast")
    main.favorite_sides.append(make_recipe("Potatoes", course="side"))
    db_session.flush()
    made = _copy_of(db_session, main, other_user)
    assert made.favorite_sides == []


# --- rate limits ------------------------------------------------------------

def test_catalog_rate_limits_have_defaults():
    assert ratelimit.CATALOG_ADOPT_RATE_LIMIT == "30/hour"
    assert ratelimit.CATALOG_ADMIN_RATE_LIMIT == "120/hour"
