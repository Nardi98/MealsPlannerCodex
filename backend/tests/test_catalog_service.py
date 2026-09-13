"""The catalog service: publish/retire, listing, popularity and adoption (spec §6-§8, §13).

Every test builds on the ``system_account`` fixture, which empties the catalog
inside the test's transaction, so assertions are about rows the test created and
never about global counts (the bootstrap may have loaded the pack).
"""

from contextlib import contextmanager
from datetime import date

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import sessionmaker

import catalog
import crud
import models
import recipe_copy


@pytest.fixture
def db_session(engine):
    """``conftest.db_session``, but with every ``commit``/``rollback`` scoped to a SAVEPOINT.

    ``adopt`` commits once and rolls back on failure. Under the default join
    mode a session ``rollback()`` rolls back the test's *outer* transaction, so
    an all-or-nothing test would pass vacuously -- the fixtures would vanish
    along with the half-built batch. ``create_savepoint`` makes the service's
    commit and rollback behave as they do in production while the test's outer
    transaction still discards everything afterwards.
    """
    connection = engine.connect()
    trans = connection.begin()
    session = sessionmaker(
        bind=connection,
        autoflush=False,
        autocommit=False,
        future=True,
        join_transaction_mode="create_savepoint",
    )()
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@contextmanager
def count_queries(engine):
    """Count the SQL statements the engine sends while the block runs."""
    statements = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", _record)


@pytest.fixture
def make_system_recipe(db_session, system_account):
    """A system-owned recipe with **no** catalog entry, for publish tests."""

    def _make(title="Risotto", procedure="Stir.", ingredients=(("Rice", 80, "g"),)):
        recipe = models.Recipe(
            user_id=system_account.id, title=title, course="main", procedure=procedure
        )
        for name, quantity, unit in ingredients:
            ingredient = crud.get_or_create_ingredient(db_session, None, name, system_account.id)
            recipe.ingredients.append(
                models.RecipeIngredient(
                    ingredient=ingredient, quantity=quantity, unit=models.UnitEnum(unit)
                )
            )
        db_session.add(recipe)
        db_session.flush()
        return recipe

    return _make


# --- publish / retire (CAT-6..10, FC-2, FC-5, FC-8) -------------------------

def test_publish_creates_a_published_entry(db_session, make_system_recipe):
    recipe = make_system_recipe()

    catalog.publish(db_session, recipe)

    entry = db_session.get(models.CatalogEntry, recipe.id)
    assert entry is not None
    assert entry.status == "published"
    assert entry.published_at is not None
    assert entry.retired_at is None


def test_publish_and_retire_flush_but_never_commit(db_session, make_system_recipe, monkeypatch):
    """FC-5: the caller owns the transaction, so a future publish flow can reuse both."""
    recipe = make_system_recipe()
    commits = []
    monkeypatch.setattr(db_session, "commit", lambda: commits.append(1))

    catalog.publish(db_session, recipe)
    catalog.retire(db_session, recipe)

    assert commits == []
    status = db_session.execute(
        select(models.CatalogEntry.status).where(models.CatalogEntry.recipe_id == recipe.id)
    ).scalar_one()
    assert status == "retired"


def test_publishing_twice_keeps_published_at(db_session, make_system_recipe):
    recipe = make_system_recipe()
    catalog.publish(db_session, recipe)
    first = db_session.get(models.CatalogEntry, recipe.id).published_at

    catalog.publish(db_session, recipe)

    entry = db_session.get(models.CatalogEntry, recipe.id)
    assert entry.published_at == first
    assert entry.status == "published"


def test_retire_sets_status_and_retired_at_and_keeps_the_recipe(db_session, make_catalog_recipe):
    recipe = make_catalog_recipe("Lasagne")
    title_before = recipe.title

    catalog.retire(db_session, recipe)
    db_session.expire_all()

    entry = db_session.get(models.CatalogEntry, recipe.id)
    assert entry.status == "retired"
    assert entry.retired_at is not None
    kept = db_session.get(models.Recipe, recipe.id)
    assert kept is not None
    assert kept.title == title_before


def test_republishing_clears_retired_at_and_keeps_the_original_published_at(
    db_session, make_system_recipe
):
    recipe = make_system_recipe()
    catalog.publish(db_session, recipe)
    first = db_session.get(models.CatalogEntry, recipe.id).published_at
    catalog.retire(db_session, recipe)

    catalog.publish(db_session, recipe)

    entry = db_session.get(models.CatalogEntry, recipe.id)
    assert entry.status == "published"
    assert entry.retired_at is None
    assert entry.published_at == first


def test_retiring_an_uncatalogued_recipe_is_not_found(make_system_recipe, db_session):
    with pytest.raises(catalog.CatalogEntryNotFound):
        catalog.retire(db_session, make_system_recipe())


def test_retiring_a_retired_entry_is_a_no_op(db_session, make_catalog_recipe):
    recipe = make_catalog_recipe("Old", status="retired")
    retired_at = recipe.catalog_entry.retired_at

    catalog.retire(db_session, recipe)

    assert recipe.catalog_entry.status == "retired"
    assert recipe.catalog_entry.retired_at == retired_at


def test_publishing_a_user_owned_recipe_is_forbidden(db_session, system_account, make_recipe):
    recipe = make_recipe("Mine", procedure="Mix.")

    with pytest.raises(PermissionError):
        catalog.publish(db_session, recipe)

    assert db_session.get(models.CatalogEntry, recipe.id) is None


@pytest.mark.parametrize(
    "overrides, part",
    [
        ({"title": ""}, "title"),
        ({"title": "   "}, "title"),
        ({"ingredients": ()}, "ingredients"),
        ({"procedure": None}, "procedure"),
        ({"procedure": "  "}, "procedure"),
    ],
)
def test_publishing_an_incomplete_recipe_names_the_missing_part(
    db_session, make_system_recipe, overrides, part
):
    recipe = make_system_recipe(**overrides)

    with pytest.raises(catalog.IncompleteRecipe, match=part):
        catalog.publish(db_session, recipe)

    assert db_session.get(models.CatalogEntry, recipe.id) is None
